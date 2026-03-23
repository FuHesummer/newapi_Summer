"""Exa 自动注册 — Camoufox 浏览器 + DuckMail OTP 验证"""
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
    EXA_AUTH_URL, EXA_DASHBOARD_URL, EXA_API_BASE,
    REGISTER_HEADLESS, EMAIL_CODE_TIMEOUT, API_KEY_TIMEOUT,
)

logger = logging.getLogger(__name__)


def _run_sync_in_clean_thread(fn, *args, **kwargs):
    """在没有 asyncio event loop 的干净线程中运行同步函数。

    Playwright/Camoufox Sync API 检测当前线程是否有 asyncio loop，
    如果有就报错。FastAPI/uvicorn 的线程池继承了主线程的 loop，
    所以 asyncio.to_thread 也不行。

    解决方案：手动创建新线程，在新线程里清除 event loop 后再运行。
    """
    result = [None]
    error = [None]

    def worker():
        # 清除当前线程的 event loop（新线程默认没有，但以防万一）
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
    t.join(timeout=300)  # 最多等 5 分钟

    if error[0]:
        raise error[0]
    return result[0]


def _fill_first_input(page, selectors: list[str], value: str) -> str | None:
    """尝试多个 selector 填写输入框，返回成功的 selector"""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.fill(value)
                return sel
        except Exception:
            continue
    return None


def _click_first(page, selectors: list[str]) -> bool:
    """尝试多个 selector 点击按钮"""
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                el.click()
                return True
        except Exception:
            continue
    return False


def _wait_for_api_key(page, timeout: int = 20) -> str | None:
    """在 dashboard 页面等待 API Key 出现"""
    for _ in range(timeout):
        try:
            content = page.content()
            # Exa key 格式通常以特定前缀开头
            match = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', content)
            if match:
                return match.group(0)
            # 也可能是其他格式
            match2 = re.search(r'(exa-[A-Za-z0-9]{20,})', content)
            if match2:
                return match2.group(1)
            # 尝试从页面元素获取
            key_els = page.query_selector_all('[data-testid*="key"], [class*="api-key"], input[readonly]')
            for el in key_els:
                val = el.get_attribute("value") or el.inner_text()
                if val and len(val) > 10:
                    return val.strip()
        except Exception:
            pass
        time.sleep(1)
    return None


def _verify_api_key(api_key: str) -> bool:
    """验证 Exa API Key 可用性"""
    import httpx
    try:
        r = httpx.post(
            f"{EXA_API_BASE}/search",
            json={"query": "test", "numResults": 1},
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            timeout=15,
        )
        if r.status_code == 200:
            logger.info(f"API Key verified OK")
            return True
        logger.warning(f"API Key verify failed: HTTP {r.status_code}")
        return False
    except Exception as e:
        logger.warning(f"API Key verify error: {e}")
        return False


def register_exa(email: str, password: str, get_code_fn=None,
                 headless: bool = True) -> str | None:
    """
    使用 Camoufox 浏览器完成 Exa 注册。

    Args:
        email: 邮箱地址
        password: 未使用（Exa 为纯 OTP 验证，无密码）
        get_code_fn: 获取邮箱验证码的回调函数 (email) -> str
        headless: 是否无头模式

    Returns:
        api_key 或 None
    """
    logger.info(f"Starting Exa registration: {email}")

    try:
        # 在函数内部导入 Camoufox，确保在独立进程中使用
        from camoufox.sync_api import Camoufox
        from camoufox import DefaultAddons

        with Camoufox(headless=headless, exclude_addons=[DefaultAddons.UBO]) as browser:
            page = browser.new_page()

            # Step 1: 打开 Exa 登录页
            logger.info("Step 1: Navigating to Exa auth page...")
            page.goto(EXA_AUTH_URL, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Step 2: 填写邮箱（Exa 用 placeholder="Email" 的 input）
            logger.info(f"Step 2: Filling email {email}...")
            email_sel = _fill_first_input(
                page,
                ['input[placeholder="Email"]', 'input[type="email"]',
                 'input[aria-label="Email"]', 'input[name="email"]'],
                email,
            )
            if not email_sel:
                logger.error("Email input not found on Exa auth page")
                return None

            # Step 3: 点击 Continue（等待按钮启用，需要输入有效邮箱后才会启用）
            logger.info("Step 3: Clicking Continue...")
            time.sleep(1)
            if not _click_first(page, ['button:text-is("Continue")',
                                       'button[type="submit"]']):
                # 尝试按 Enter
                page.press('input[placeholder="Email"]', "Enter")

            # Step 4: 等待验证码页面
            logger.info("Step 4: Waiting for verification code page...")
            try:
                page.wait_for_selector(
                    'input[placeholder*="verification" i], '
                    'input[aria-label*="verification" i], '
                    'input[placeholder*="code" i]',
                    timeout=30000,
                )
                logger.info("Verification code page loaded")
            except Exception:
                logger.error("Verification code page not loaded in time")
                return None

            # Step 5: 获取邮箱验证码
            logger.info("Step 5: Waiting for OTP email...")
            if not get_code_fn:
                logger.error("No get_code_fn provided")
                return None

            code = get_code_fn(email)
            if not code:
                logger.error("Failed to get OTP code")
                return None
            logger.info(f"Got OTP: {code}")

            # Step 6: 填写验证码
            logger.info("Step 6: Filling verification code...")
            code_sel = _fill_first_input(
                page,
                ['input[placeholder*="verification" i]',
                 'input[aria-label*="verification" i]',
                 'input[placeholder*="code" i]'],
                code,
            )
            if not code_sel:
                logger.error("Verification code input not found")
                return None

            # Step 7: 点击验证按钮
            logger.info("Step 7: Clicking Verify...")
            if not _click_first(page, [
                'button:text-is("VERIFY CODE")',
                'button:text-is("Verify Code")',
                'button:text-is("Verify")',
                'button[type="submit"]',
            ]):
                # 回退：按 Enter
                page.press(code_sel, "Enter")

            # Step 8: 等待跳转到 dashboard
            logger.info("Step 8: Waiting for dashboard redirect...")
            try:
                page.wait_for_url(
                    "**/dashboard.exa.ai/**",
                    timeout=30000,
                    wait_until="domcontentloaded",
                )
                logger.info("Exa dashboard loaded")
            except Exception:
                logger.warning(f"Dashboard redirect timeout, current URL: {page.url}")
                # 尝试手动导航
                try:
                    page.goto(EXA_DASHBOARD_URL, wait_until="domcontentloaded", timeout=15000)
                    time.sleep(3)
                except Exception:
                    pass

            # Step 9: 提取 API Key
            logger.info("Step 9: Extracting API Key...")
            api_key = _wait_for_api_key(page, timeout=API_KEY_TIMEOUT)

            if not api_key:
                logger.warning("API Key not found on dashboard, trying API keys page...")
                try:
                    page.goto(f"{EXA_DASHBOARD_URL}/api-keys",
                              wait_until="domcontentloaded", timeout=15000)
                    time.sleep(3)
                    api_key = _wait_for_api_key(page, timeout=10)
                except Exception:
                    pass

            if api_key:
                logger.info(f"API Key extracted: {api_key[:15]}...")
                if _verify_api_key(api_key):
                    logger.info("Exa registration SUCCESS")
                    return api_key
                else:
                    logger.warning("API Key extracted but verification failed")
                    return api_key  # 仍然返回，可能是验证 API 暂时不可用
            else:
                logger.error("Failed to extract API Key")
                return None

    except Exception as e:
        logger.error(f"Exa registration failed: {e}")
        return None


class ExaRegistrar:
    """Exa 自动注册（Camoufox + DuckMail OTP）"""

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
        password = mail_account["password"]
        mail_token = mail_account["token"]
        mail_account_id = mail_account["account_id"]

        logger.info(f"Created temp email: {email}")

        try:
            # OTP 回调（同步版本，在 Camoufox 同步线程中调用）
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
                                # Exa 专用匹配
                                if "exa" in combined and ("verification code" in combined or "sign in" in combined):
                                    import re as _re
                                    m = _re.search(
                                        r'verification code(?:\s+for\s+exa)?(?:\s+is)?[^0-9]*(\d{6})',
                                        content, _re.IGNORECASE,
                                    )
                                    if m:
                                        return m.group(1)
                                # 通用 6 位 OTP
                                import re as _re
                                content_clean = _re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', content)
                                otp = _re.search(r'(?<!\d)(\d{6})(?!\d)', content_clean)
                                if otp:
                                    return otp.group(1)
                    except Exception as e:
                        logger.warning(f"Poll error: {e}")
                    import time as _time
                    _time.sleep(3)
                    elapsed += 3
                return None

            # Camoufox Sync API 不能在有 asyncio event loop 的线程中运行
            # 使用干净线程来执行，避免 "Playwright Sync API inside asyncio loop" 错误
            api_key = await asyncio.get_event_loop().run_in_executor(
                None,
                _run_sync_in_clean_thread,
                register_exa, email, password, get_code_fn, REGISTER_HEADLESS
            )

            if api_key:
                self.breaker.record_success(domain)
                logger.info(f"Successfully registered: {email}, key={api_key[:15]}...")
                return {
                    "email": email,
                    "api_key": api_key,
                    "provider": "exa",
                }
            else:
                self.breaker.record_failure(domain)
                raise Exception(f"Failed to register Exa for {email}")

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
