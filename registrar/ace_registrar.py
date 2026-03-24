"""Augment Code (ACE) 自动注册 — Camoufox 浏览器 + DuckMail OTP 验证

ACE 登录流程：
1. 打开 app.augmentcode.com → 跳转 login.augmentcode.com (Auth0)
2. 填写邮箱 → 点击 Continue
3. 收取 OTP 验证码 → 填入 → 点击 Continue
4. 登录成功 → 跳转 app.augmentcode.com
5. 导航到 Settings → Service Accounts → 创建 Token → 提取

也支持 Google OAuth（和 Tavily 类似）。
"""
import re
import time
import random
import asyncio
import logging
import threading

from duckmail_client import DuckMailClient
from domain_breaker import DomainBreaker
from config import (
    REGISTRATION_PROXY, COOLDOWN_BASE, COOLDOWN_JITTER,
    REGISTER_HEADLESS, EMAIL_CODE_TIMEOUT, API_KEY_TIMEOUT,
)

logger = logging.getLogger(__name__)

ACE_LOGIN_URL = "https://app.augmentcode.com"
ACE_DASHBOARD_URL = "https://app.augmentcode.com"
ACE_SERVICE_ACCOUNTS_URL = "https://app.augmentcode.com/settings/service-accounts"


def _run_sync_in_clean_thread(fn, *args, **kwargs):
    """在没有 asyncio event loop 的干净线程中运行同步函数。"""
    result = [None]
    error = [None]

    def worker():
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass
        try:
            result[0] = fn(*args, **kwargs)
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout=300)

    if error[0]:
        raise error[0]
    return result[0]


def _build_proxy_cfg(proxy: str | None) -> dict | None:
    """将代理 URL 解析为 Playwright 格式 {server, username, password}"""
    if not proxy:
        return None
    from urllib.parse import urlparse
    parsed = urlparse(proxy)
    if parsed.username:
        cfg = {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            "username": parsed.username,
            "password": parsed.password or "",
        }
    else:
        cfg = {"server": proxy}
    logger.info(f"Using proxy: {parsed.scheme}://{parsed.hostname}:{parsed.port}")
    return cfg


def register_ace_with_email(email: str, get_code_fn=None,
                            headless: bool = True,
                            proxy: str | None = None) -> str | None:
    """
    使用邮箱 OTP 方式注册/登录 ACE，提取 API Token。

    Args:
        email: 邮箱地址
        get_code_fn: 获取验证码的回调函数 (email) -> str
        headless: 是否无头模式
        proxy: 代理地址

    Returns:
        api_token 或 None
    """
    logger.info(f"Starting ACE registration: {email}")

    proxy_cfg = _build_proxy_cfg(proxy)

    try:
        from camoufox.sync_api import Camoufox
        from camoufox import DefaultAddons

        with Camoufox(headless=headless, exclude_addons=[DefaultAddons.UBO],
                      proxy=proxy_cfg) as browser:
            page = browser.new_page()

            # ── Step 1: 打开 ACE 登录页 ──
            logger.info("Step 1: Navigating to ACE login page...")
            page.goto(ACE_LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # 应该跳转到 login.augmentcode.com
            current_url = page.url
            logger.info(f"Current URL: {current_url[:80]}")

            # ── Step 2: 填写邮箱 ──
            logger.info(f"Step 2: Filling email {email}...")
            try:
                email_input = page.wait_for_selector(
                    'input[type="email"], input[name="email"], '
                    'input[placeholder*="email" i], input[inputmode="email"]',
                    timeout=15000,
                )
                email_input.click()
                time.sleep(0.3)
                page.keyboard.type(email, delay=random.randint(30, 80))
                time.sleep(0.5 + random.random())
            except Exception as e:
                logger.error(f"Email input failed: {e}")
                return None

            # ── Step 3: 处理 Cloudflare Turnstile ──
            logger.info("Step 3: Handling Turnstile verification...")
            try:
                # Turnstile checkbox 在 iframe 中
                turnstile_frame = None
                for frame in page.frames:
                    if "challenges.cloudflare.com" in frame.url:
                        turnstile_frame = frame
                        break

                if turnstile_frame:
                    logger.info("Found Turnstile iframe, clicking checkbox...")
                    try:
                        checkbox = turnstile_frame.wait_for_selector(
                            'input[type="checkbox"], .ctp-checkbox-label, #challenge-stage',
                            timeout=5000,
                        )
                        if checkbox:
                            checkbox.click()
                            time.sleep(3)
                    except Exception:
                        # 有时直接点 iframe 区域即可
                        turnstile_frame.click("body")
                        time.sleep(3)

                    # 等待 Turnstile 验证完成（checkbox 变绿 / 消失）
                    for _ in range(10):
                        try:
                            # 检查是否已验证（隐藏的 response input 有值）
                            response = page.evaluate("""() => {
                                const el = document.querySelector('[name="cf-turnstile-response"], input[name*="turnstile"]');
                                return el ? el.value : '';
                            }""")
                            if response:
                                logger.info("Turnstile verified!")
                                break
                        except Exception:
                            pass
                        time.sleep(1)
                else:
                    logger.info("No Turnstile iframe found, proceeding...")
                    # 也可能是直接嵌入的 widget，尝试点击
                    turnstile_div = page.query_selector('[class*="turnstile"], [class*="cf-"], iframe[src*="turnstile"]')
                    if turnstile_div:
                        turnstile_div.click()
                        time.sleep(3)
            except Exception as e:
                logger.warning(f"Turnstile handling: {e}")

            time.sleep(1)

            # ── Step 4: 点击 Continue ──
            logger.info("Step 4: Clicking Continue...")
            try:
                continue_btn = page.wait_for_selector(
                    'button:text-is("Continue"), button[type="submit"]',
                    timeout=5000,
                )
                continue_btn.click()
            except Exception:
                page.keyboard.press("Enter")
            time.sleep(3)

            # ── Step 5: 等待验证码页面 ──
            logger.info("Step 5: Waiting for OTP page...")
            try:
                page.wait_for_selector(
                    'input[placeholder*="code" i], '
                    'input[aria-label*="code" i], '
                    'input[inputmode="numeric"], '
                    'input[name*="code" i]',
                    timeout=30000,
                )
                logger.info("OTP input page loaded")
            except Exception:
                # 检查是否已经直接登录了（之前注册过的邮箱）
                if "app.augmentcode.com" in page.url and "login" not in page.url:
                    logger.info("Already logged in, skipping OTP")
                else:
                    logger.error(f"OTP page not loaded, current URL: {page.url}")
                    return None

            # ── Step 6: 获取 OTP 验证码 ──
            if "login" in page.url:
                logger.info("Step 6: Waiting for OTP email...")
                if not get_code_fn:
                    logger.error("No get_code_fn provided")
                    return None

                code = get_code_fn(email)
                if not code:
                    logger.error("Failed to get OTP code")
                    return None
                logger.info(f"Got OTP: {code}")

                # ── Step 7: 填写验证码 ──
                logger.info("Step 7: Filling OTP code...")
                code_input = page.query_selector(
                    'input[placeholder*="code" i], '
                    'input[aria-label*="code" i], '
                    'input[inputmode="numeric"]'
                )
                if code_input:
                    code_input.fill(code)
                else:
                    logger.error("OTP input not found")
                    return None
                time.sleep(0.5)

                # ── Step 8: 点击 Continue 验证 ──
                logger.info("Step 8: Clicking Continue to verify...")
                try:
                    btn = page.query_selector(
                        'button:text-is("Continue"), button[type="submit"]'
                    )
                    if btn:
                        btn.click()
                    else:
                        page.keyboard.press("Enter")
                except Exception:
                    page.keyboard.press("Enter")

                # 等待跳转到 dashboard
                time.sleep(5)

            # ── Step 9: 确认已登录，等待完整 OAuth 回调 ──
            logger.info(f"Step 9: Post-login URL: {page.url[:80]}")

            # 等待 OAuth 回调链完成：auth.augmentcode.com → app.augmentcode.com/auth/callback → app.augmentcode.com
            for attempt in range(6):
                current = page.url
                if "app.augmentcode.com" in current and "auth/callback" not in current and "login" not in current:
                    logger.info("ACE dashboard loaded")
                    break
                logger.info(f"Waiting for OAuth callback... ({current[:60]})")
                time.sleep(5)
            else:
                # 手动导航
                logger.warning("OAuth callback chain slow, navigating manually...")
                try:
                    page.goto(ACE_DASHBOARD_URL, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(5)
                except Exception:
                    pass

            logger.info(f"Dashboard URL: {page.url[:80]}")
            # 再等 SPA 完全加载（Auth0 SPA SDK 会异步获取 token）
            time.sleep(5)

            # ── Step 9: 提取 API Token ──
            # ACE 的 token 通过 Service Accounts 创建
            # 但新用户可能没有 organization，先尝试从页面提取已有的 token
            logger.info("Step 9: Extracting API Token...")

            api_token = _extract_ace_token(page)
            if api_token:
                logger.info(f"ACE API Token extracted: {api_token[:20]}...")
                return api_token

            # 如果没有现成的 token，尝试创建 service account
            logger.info("No existing token found, trying to create service account...")
            api_token = _create_service_account_token(page)
            if api_token:
                logger.info(f"ACE API Token created: {api_token[:20]}...")
                return api_token

            # 最后尝试从 auggie CLI 的方式获取 token（通过 cookie/session）
            logger.info("Trying to extract session token...")
            api_token = _extract_session_token(page)
            if api_token:
                logger.info(f"ACE session token extracted: {api_token[:20]}...")
                return api_token

            logger.error("Failed to extract ACE API Token")
            return None

    except Exception as e:
        logger.error(f"ACE registration failed: {e}")
        return None


def _extract_ace_token(page) -> str | None:
    """从页面中提取已有的 API token"""
    try:
        content = page.content()
        # ACE token 格式：通常是长字符串
        # 尝试匹配各种 token 格式
        patterns = [
            r'ace_[A-Za-z0-9]{30,}',           # ace_ 前缀
            r'aug_[A-Za-z0-9]{30,}',           # aug_ 前缀
            r'AUGMENT_API_TOKEN["\s:=]+([A-Za-z0-9_-]{20,})',  # 环境变量引用
        ]
        for pat in patterns:
            m = re.search(pat, content)
            if m:
                return m.group(1) if m.lastindex else m.group(0)
    except Exception:
        pass
    return None


def _create_service_account_token(page) -> str | None:
    """导航到 Service Accounts 页面创建 token"""
    try:
        logger.info("Navigating to Service Accounts page...")
        page.goto(ACE_SERVICE_ACCOUNTS_URL,
                  wait_until="domcontentloaded", timeout=15000)
        time.sleep(3)

        # 查找 "Add Service Account" 按钮
        add_btn = page.query_selector(
            'button:text-is("Add Service Account"), '
            'button:has-text("Add Service"), '
            'button:has-text("Create")'
        )
        if not add_btn:
            logger.warning("Add Service Account button not found (may need org)")
            return None

        add_btn.click()
        time.sleep(2)

        # 填写 Service Account 名称
        name_input = page.query_selector(
            'input[placeholder*="name" i], '
            'input[name="name"], '
            'input[aria-label*="name" i]'
        )
        if name_input:
            sa_name = f"auto-reg-{random.randint(1000, 9999)}"
            name_input.fill(sa_name)
            time.sleep(0.5)

        # 点击 Create
        create_btn = page.query_selector(
            'button:text-is("Create"), button[type="submit"]'
        )
        if create_btn:
            create_btn.click()
            time.sleep(3)

        # 查找 "Create Token" 按钮
        token_btn = page.query_selector(
            'button:text-is("Create Token"), '
            'button:has-text("Create Token")'
        )
        if not token_btn:
            logger.warning("Create Token button not found")
            return None

        token_btn.click()
        time.sleep(2)

        # 填写 Token Description
        desc_input = page.query_selector(
            'input[placeholder*="description" i], '
            'input[name="description"], '
            'textarea'
        )
        if desc_input:
            desc_input.fill("auto-generated")
            time.sleep(0.5)

        # 点击 Create
        create_btn2 = page.query_selector(
            'button:text-is("Create"), button[type="submit"]'
        )
        if create_btn2:
            create_btn2.click()
            time.sleep(3)

        # 提取显示的 token（只显示一次！）
        # 查找包含 token 的元素
        token = page.evaluate("""() => {
            // 查找所有可能包含 token 的元素
            const els = document.querySelectorAll('input[readonly], code, pre, [class*="token"], [data-testid*="token"]');
            for (const el of els) {
                const val = el.value || el.textContent || '';
                if (val.length > 20 && !val.includes(' ')) {
                    return val.trim();
                }
            }
            // 尝试从剪贴板按钮旁边的元素获取
            const copyBtns = document.querySelectorAll('button[aria-label*="copy" i], button:has(svg)');
            for (const btn of copyBtns) {
                const parent = btn.parentElement;
                if (parent) {
                    const sibling = parent.querySelector('input, code, span');
                    if (sibling) {
                        const val = sibling.value || sibling.textContent || '';
                        if (val.length > 20) return val.trim();
                    }
                }
            }
            return null;
        }""")

        if token:
            return token

    except Exception as e:
        logger.warning(f"Service account creation failed: {e}")

    return None


def _extract_session_token(page) -> str | None:
    """从浏览器 session/cookie/localStorage 中提取 Augment accessToken。

    acemcp-relay 需要的 AUGMENT_API_TOKEN 是 Augment 的 accessToken，
    通过 auggie CLI `auggie token print` 可以拿到：
    {"accessToken": "ABC-XYZ-123", "tenantURL": "https://..."}

    这个 token 在 Auth0 OAuth 完成后存在 localStorage 或通过 token endpoint 获取。
    """
    try:
        # 方法1：从 localStorage 获取 Auth0 缓存的 token
        token = page.evaluate("""() => {
            // Auth0 SPA SDK 在 localStorage 中存 token
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                const val = localStorage.getItem(key);
                // Auth0 通常用 @@auth0spajs@@ 前缀
                if (key && (key.includes('auth0') || key.includes('augment') || key.includes('token'))) {
                    try {
                        const obj = JSON.parse(val);
                        // Auth0 SPA cache 结构: {body: {access_token: "...", ...}}
                        if (obj.body && obj.body.access_token) return obj.body.access_token;
                        if (obj.accessToken) return obj.accessToken;
                        if (obj.access_token) return obj.access_token;
                        // 递归查找
                        const str = JSON.stringify(obj);
                        const m = str.match(/"access_token":"([^"]+)"/);
                        if (m) return m[1];
                    } catch (e) {}
                }
            }
            // sessionStorage 也检查
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                const val = sessionStorage.getItem(key);
                if (key && (key.includes('auth0') || key.includes('augment') || key.includes('token'))) {
                    try {
                        const obj = JSON.parse(val);
                        if (obj.body && obj.body.access_token) return obj.body.access_token;
                        if (obj.accessToken) return obj.accessToken;
                        if (obj.access_token) return obj.access_token;
                    } catch (e) {}
                }
            }
            return null;
        }""")

        if token:
            logger.info(f"Got accessToken from storage ({len(token)} chars)")
            return token

        # 方法2：通过拦截网络请求从 API 调用中获取 token
        # 导航到一个需要认证的页面，触发 token refresh
        token = page.evaluate("""() => {
            return new Promise((resolve) => {
                const origFetch = window.fetch;
                window.fetch = function(...args) {
                    const result = origFetch.apply(this, args);
                    result.then(resp => {
                        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
                        if (url.includes('token') || url.includes('oauth')) {
                            resp.clone().json().then(data => {
                                if (data.access_token) resolve(data.access_token);
                            }).catch(() => {});
                        }
                    }).catch(() => {});
                    return result;
                };
                // 触发一个需要 token 的请求
                setTimeout(() => resolve(null), 10000);
            });
        }""")

        if token:
            logger.info(f"Got accessToken from fetch intercept ({len(token)} chars)")
            return token

        # 方法3：从 cookie 中获取（fallback）
        cookies = page.context.cookies()
        for c in cookies:
            name = c['name'].lower()
            val = c['value']
            # Augment 可能用 appSession / _session 等 cookie
            if ('token' in name or 'session' in name or 'auth' in name) and len(val) > 50:
                # 尝试解码（可能是 base64 的 JWT 或 session 数据）
                logger.info(f"Got token from cookie: {c['name']} ({len(val)} chars)")
                return val

    except Exception as e:
        logger.warning(f"Session token extraction failed: {e}")

    return None


class AceRegistrar:
    """Augment Code 自动注册（Camoufox + DuckMail OTP）"""

    def __init__(self, breaker: DomainBreaker):
        self.mail = DuckMailClient()
        self.breaker = breaker

    async def register(self, proxy: str | None = None) -> dict | None:
        proxy = proxy or REGISTRATION_PROXY or None

        # 1. 获取可用域名
        domains = await self.mail.get_available_domains()
        if not domains:
            raise Exception("No available domains from DuckMail")

        domain = self.breaker.get_available_domain(domains)
        if not domain:
            raise Exception("All domains are circuit-broken")

        # 2. 创建临时邮箱
        mail_account = await self.mail.create_account(domain)
        email = mail_account["email"]
        mail_token = mail_account["token"]
        mail_account_id = mail_account["account_id"]

        logger.info(f"Created temp email: {email}")

        try:
            # OTP 回调（同步版本）
            def get_code_fn(addr: str) -> str | None:
                import httpx as _httpx
                elapsed = 0
                seen_ids: set[str] = set()
                while elapsed < EMAIL_CODE_TIMEOUT:
                    try:
                        resp = _httpx.get(
                            f"{self.mail.base_url}/messages?page=1",
                            headers={"Authorization": f"Bearer {mail_token}"},
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            msgs = resp.json().get("hydra:member", [])
                            for msg in msgs:
                                msg_id = str(msg.get("id", ""))
                                if not msg_id or msg_id in seen_ids:
                                    continue
                                seen_ids.add(msg_id)
                                detail = _httpx.get(
                                    f"{self.mail.base_url}/messages/{msg_id}",
                                    headers={"Authorization": f"Bearer {mail_token}"},
                                    timeout=15,
                                )
                                if detail.status_code != 200:
                                    continue
                                d = detail.json()
                                text = d.get("text", "")
                                html_list = d.get("html", [])
                                html = html_list[0] if html_list else ""
                                subject = d.get("subject", "")
                                content = f"{subject} {text} {html}"
                                combined = content.lower()
                                # ACE 专用匹配 — "Your one-time code" 或 "verification code"
                                if "augment" in combined or "one-time" in combined or "verification" in combined:
                                    import re as _re
                                    # 匹配 6-8 位数字验证码
                                    m = _re.search(
                                        r'(?:code|码)[^0-9]{0,20}(\d{6,8})',
                                        content, _re.IGNORECASE,
                                    )
                                    if m:
                                        return m.group(1)
                                    # 通用 6 位 OTP
                                    content_clean = _re.sub(
                                        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', content
                                    )
                                    otp = _re.search(r'(?<!\d)(\d{6})(?!\d)', content_clean)
                                    if otp:
                                        return otp.group(1)
                    except Exception as e:
                        logger.warning(f"Poll error: {e}")
                    import time as _time
                    _time.sleep(3)
                    elapsed += 3
                return None

            # 在干净线程中运行 Camoufox
            api_token = await asyncio.get_event_loop().run_in_executor(
                None,
                _run_sync_in_clean_thread,
                register_ace_with_email, email, get_code_fn, REGISTER_HEADLESS, proxy
            )

            if api_token:
                self.breaker.record_success(domain)
                logger.info(f"Successfully registered: {email}, token={api_token[:15]}...")
                return {
                    "email": email,
                    "api_key": api_token,
                    "provider": "augment",
                }
            else:
                self.breaker.record_failure(domain)
                raise Exception(f"Failed to register ACE for {email}")

        except Exception as e:
            logger.error(f"Registration failed for {email}: {e}")
            raise
        finally:
            await self.mail.cleanup(mail_account_id, mail_token)

    async def batch_register(self, count: int = 1,
                             proxy: str | None = None) -> list[dict]:
        results = []
        for i in range(count):
            try:
                result = await self.register(proxy)
                if result:
                    results.append(result)
                if i < count - 1:
                    delay = COOLDOWN_BASE + random.randint(0, COOLDOWN_JITTER)
                    logger.info(f"Cooling down for {delay}s...")
                    await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"Registration {i+1}/{count} failed: {e}")
                results.append({"error": str(e), "index": i})
        return results
