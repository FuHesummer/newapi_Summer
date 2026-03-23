"""Tavily 自动注册 — Google OAuth 批量登录 (Camoufox + Google 账号)"""
import re
import time
import random
import asyncio
import logging
import threading

from domain_breaker import DomainBreaker
from config import REGISTRATION_PROXY, COOLDOWN_BASE, COOLDOWN_JITTER, REGISTER_HEADLESS

logger = logging.getLogger(__name__)

TAVILY_SIGNIN_URL = "https://app.tavily.com/sign-in"


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


def _parse_google_accounts(text: str) -> list[dict]:
    """
    解析 Google 账号列表，格式：
    email|password|recovery_email|2fa_secret|region
    """
    accounts = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|")
        if len(parts) < 2:
            continue
        accounts.append({
            "email": parts[0].strip(),
            "password": parts[1].strip(),
            "recovery_email": parts[2].strip() if len(parts) > 2 else "",
            "totp_secret": parts[3].strip() if len(parts) > 3 else "",
            "region": parts[4].strip() if len(parts) > 4 else "",
        })
    return accounts


def _generate_totp(secret: str) -> str:
    """根据 TOTP secret 生成 6 位验证码"""
    import hmac
    import hashlib
    import struct
    import base64

    # 清理 secret
    secret = secret.strip().upper().replace(" ", "")
    # 补齐 padding
    missing_padding = len(secret) % 8
    if missing_padding:
        secret += "=" * (8 - missing_padding)

    key = base64.b32decode(secret)
    counter = int(time.time()) // 30
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(code % 1000000).zfill(6)


def _handle_2fa_method_selection(page):
    """
    处理 Google 可能显示的 2FA 方式选择页面。
    如果当前页面不是 TOTP 输入页面，而是 2FA 方式选择页面，
    尝试点击 "Google Authenticator" / "Use your authenticator app" 选项。
    """
    try:
        # 检查是否已经在 TOTP 输入页面
        totp_input = page.query_selector('input#totpPin, input[name="totpPin"]')
        if totp_input:
            return  # 已经在 TOTP 页面

        # 检查是否在 2FA 方式选择页面（"Try another way" 或类似的页面）
        # Google 有时会列出多种验证方式
        current_url = page.url
        if "challenge/selection" in current_url or "selectchallenge" in current_url:
            logger.info("2FA method selection page detected, looking for TOTP option...")
            # 尝试找到包含 "Authenticator" 或 "Use your authenticator" 的选项
            for selector in [
                'div[data-challengetype="6"]',  # TOTP challenge type
                'li[data-challengetype="6"]',
                'button:has-text("Authenticator")',
                'div:has-text("authenticator app")',
                'div:has-text("Google Authenticator")',
            ]:
                opt = page.query_selector(selector)
                if opt and opt.is_visible():
                    logger.info(f"Found TOTP option: {selector}")
                    opt.click()
                    time.sleep(3)
                    return
            logger.warning("TOTP option not found on 2FA selection page")
    except Exception as e:
        logger.warning(f"2FA method selection handling: {e}")


def _extract_page_error(page) -> str:
    """提取 Google 页面上的错误信息文本"""
    try:
        # Google 通常在 class 包含 error 的元素中显示错误
        for selector in [
            'div[jsname="B34EJ"]',       # 常见的 Google 错误容器
            'div[class*="error"]',
            'span[class*="error"]',
            'div[class*="LXRPh"]',       # Google "Wrong code" 消息
            'div[role="alert"]',
            'c-wiz div[jsslot] span',
        ]:
            el = page.query_selector(selector)
            if el and el.is_visible():
                text = el.inner_text().strip()
                if text:
                    return text
        # 尝试提取所有可见文本的一部分
        body_text = page.inner_text('body')
        # 截取前 500 字符作为调试信息
        return body_text[:500] if body_text else "No error text found"
    except Exception as e:
        return f"Error extracting page text: {e}"


def _extract_api_key(page, timeout: int = 20) -> str | None:
    """从 Tavily dashboard 提取 API Key

    Tavily 的 API Key 在页面上默认是遮蔽的 (tvly-dev-*****)，
    存放在一个 readonly 的 textbox/input 中。
    需要先点击"眼睛"按钮（Show）来显示完整 key，
    然后从 input.value 中读取。
    """
    # 等页面加载完
    time.sleep(3)

    # 策略1: 直接用 JavaScript 点击眼睛按钮并读取 input value
    for attempt in range(3):
        try:
            api_key = page.evaluate("""
                () => {
                    // 找到 API Keys 表格中的 input（包含 tvly- 前缀）
                    const inputs = document.querySelectorAll('input');
                    for (const input of inputs) {
                        const val = input.value || '';
                        if (val.startsWith('tvly-')) {
                            // 如果 key 是遮蔽的（含 *），尝试点击眼睛按钮
                            if (val.includes('*')) {
                                // 眼睛按钮在同一行 cell[Options] 中，是第1个 button
                                const row = input.closest('tr');
                                if (row) {
                                    const buttons = row.querySelectorAll('button');
                                    if (buttons.length > 0) {
                                        buttons[0].click();  // 第1个按钮 = 眼睛/Show
                                        return '__CLICKED_SHOW__';
                                    }
                                }
                            } else {
                                return val;
                            }
                        }
                    }
                    return null;
                }
            """)

            if api_key == '__CLICKED_SHOW__':
                # 点击了 Show 按钮，等待 key 显示
                logger.info("Clicked Show button, waiting for key to reveal...")
                time.sleep(2)
                # 重新读取
                api_key = page.evaluate("""
                    () => {
                        const inputs = document.querySelectorAll('input');
                        for (const input of inputs) {
                            const val = input.value || '';
                            if (val.startsWith('tvly-') && !val.includes('*')) {
                                return val;
                            }
                        }
                        return null;
                    }
                """)

            if api_key and api_key.startswith("tvly-") and "*" not in api_key:
                logger.info(f"Got API key: {api_key[:20]}...")
                return api_key

        except Exception as e:
            logger.warning(f"API key extraction attempt {attempt+1} failed: {e}")

        time.sleep(3)

    # 策略2: 页面 HTML 中搜索（如果 key 已经显示）
    try:
        content = page.content()
        match = re.search(r"tvly-[A-Za-z0-9_-]{20,}", content)
        if match:
            logger.info(f"Got API key from HTML: {match.group(0)[:20]}...")
            return match.group(0)
    except Exception:
        pass

    # 策略3: 导航到 /home 重试
    try:
        page.goto("https://app.tavily.com/home",
                  wait_until="domcontentloaded", timeout=15000)
        time.sleep(5)
        api_key = page.evaluate("""
            () => {
                // 先点击 Show
                const inputs = document.querySelectorAll('input');
                for (const input of inputs) {
                    const val = input.value || '';
                    if (val.startsWith('tvly-') && val.includes('*')) {
                        const row = input.closest('tr');
                        if (row) {
                            const buttons = row.querySelectorAll('button');
                            if (buttons.length > 0) buttons[0].click();
                        }
                    }
                }
                return null;
            }
        """)
        time.sleep(2)
        api_key = page.evaluate("""
            () => {
                const inputs = document.querySelectorAll('input');
                for (const input of inputs) {
                    const val = input.value || '';
                    if (val.startsWith('tvly-') && !val.includes('*') && val.length > 20) {
                        return val;
                    }
                }
                return null;
            }
        """)
        if api_key:
            logger.info(f"Got API key on retry: {api_key[:20]}...")
            return api_key
    except Exception:
        pass

    return None


def register_tavily_with_google(account: dict,
                                headless: bool = True) -> dict | None:
    """
    使用 Google 账号通过 OAuth 注册/登录 Tavily，提取 API Key。

    Args:
        account: {"email", "password", "totp_secret", ...}
        headless: 是否无头模式

    Returns:
        {"email": ..., "api_key": ..., "provider": "tavily"} 或 None
    """
    email = account["email"]
    password = account["password"]
    totp_secret = account.get("totp_secret", "")

    logger.info(f"Starting Tavily registration via Google: {email}")

    try:
        from camoufox.sync_api import Camoufox

        with Camoufox(headless=headless) as browser:
            page = browser.new_page()

            # ── Step 1: 打开 Tavily sign-in 页面 ──
            logger.info("Step 1: Opening Tavily sign-in...")
            page.goto(TAVILY_SIGNIN_URL, wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)

            # ── Step 2: 点击 "Continue with Google" ──
            logger.info("Step 2: Clicking Continue with Google...")
            google_btn = page.query_selector('button[data-provider="google"]')
            if not google_btn:
                # 回退：按文本查找
                google_btn = page.query_selector('button:has-text("Google")')
            if not google_btn:
                logger.error("Google login button not found")
                return None
            google_btn.click()
            time.sleep(5)

            # ── Step 3: Google 登录 - 填邮箱 ──
            logger.info(f"Step 3: Filling Google email {email}...")
            current_url = page.url
            logger.info(f"Current URL: {current_url[:100]}")

            # Google 登录页的邮箱输入框
            try:
                email_input = page.wait_for_selector(
                    'input[type="email"], input[name="identifier"]',
                    timeout=15000,
                )
                # 使用 type 逐字输入，更自然地模拟人类行为
                email_input.click()
                time.sleep(0.3)
                page.keyboard.type(email, delay=random.randint(30, 80))
                time.sleep(0.5 + random.random())

                # 点击 Next
                next_btn = page.query_selector('#identifierNext, button:has-text("Next")')
                if next_btn:
                    next_btn.click()
                else:
                    page.keyboard.press("Enter")
                time.sleep(3 + random.random() * 2)
            except Exception as e:
                logger.error(f"Google email step failed: {e}")
                return None

            # ── Step 4: Google 登录 - 填密码 ──
            logger.info("Step 4: Filling Google password...")
            try:
                pwd_input = page.wait_for_selector(
                    'input[type="password"], input[name="Passwd"]',
                    timeout=15000,
                )
                # 使用 type 逐字输入
                pwd_input.click()
                time.sleep(0.3)
                page.keyboard.type(password, delay=random.randint(30, 80))
                time.sleep(0.5 + random.random())

                # 点击 Next
                next_btn = page.query_selector('#passwordNext, button:has-text("Next")')
                if next_btn:
                    next_btn.click()
                else:
                    page.keyboard.press("Enter")
                time.sleep(5 + random.random() * 2)
            except Exception as e:
                logger.error(f"Google password step failed: {e}")
                return None

            # ── Step 5: 处理 2FA（如果需要） ──
            current_url = page.url
            logger.info(f"After password: {current_url[:100]}")

            if "challenge" in current_url or "signin" in current_url.split("?")[0]:
                if totp_secret:
                    logger.info("Step 5: Handling 2FA with TOTP...")
                    try:
                        # 检查是否 Google 要求选择 2FA 方式（可能不直接在 TOTP 页面）
                        # 有时 Google 会先询问"Try another way"
                        _handle_2fa_method_selection(page)

                        # 在填入 TOTP 之前重新生成，确保使用最新的时间窗口
                        totp_code = _generate_totp(totp_secret)
                        logger.info(f"Generated TOTP: {totp_code}")

                        # Google 直接显示 TOTP 输入框 input#totpPin
                        totp_input = page.wait_for_selector(
                            'input#totpPin, input[name="totpPin"], '
                            'input[type="tel"][aria-label*="code" i]',
                            timeout=15000,
                        )
                        # 使用 type 逐字输入 TOTP 码，不用 fill
                        totp_input.click()
                        time.sleep(0.3)
                        page.keyboard.type(totp_code, delay=random.randint(50, 120))
                        time.sleep(0.5 + random.random())

                        # 点击 Next
                        next_btn = page.query_selector(
                            '#totpNext, button:has-text("Next")'
                        )
                        if next_btn:
                            next_btn.click()
                        else:
                            page.keyboard.press("Enter")
                        time.sleep(5 + random.random() * 2)

                        # 检查 TOTP 是否被接受
                        post_totp_url = page.url
                        logger.info(f"After TOTP submit: {post_totp_url[:120]}")

                        # 如果仍在 challenge 页面，可能是页面还在跳转中
                        # 等待页面跳转完成（TOTP 实际已通过，只是页面还在加载）
                        if "challenge" in post_totp_url and "totp" in post_totp_url:
                            # 先等待看是否会自动跳转
                            logger.info("Still on TOTP page, waiting for redirect...")
                            for wait_i in range(15):
                                time.sleep(1)
                                current = page.url
                                if "challenge" not in current or "totp" not in current:
                                    logger.info(f"Redirected to: {current[:120]}")
                                    break
                            else:
                                # 确实还在 TOTP 页面，尝试重新输入
                                error_text = _extract_page_error(page)
                                logger.error(f"TOTP may have been rejected. Error: {error_text}")
                                logger.info("Retrying TOTP with fresh code...")
                                time.sleep(2)
                                totp_code2 = _generate_totp(totp_secret)
                                logger.info(f"Retry TOTP: {totp_code2}")
                                try:
                                    totp_input2 = page.query_selector(
                                        'input#totpPin, input[name="totpPin"], '
                                        'input[type="tel"][aria-label*="code" i]'
                                    )
                                    if totp_input2:
                                        totp_input2.click()
                                        page.keyboard.press("Control+a")
                                        time.sleep(0.1)
                                        page.keyboard.type(totp_code2, delay=random.randint(50, 120))
                                        time.sleep(0.5)
                                        next_btn2 = page.query_selector(
                                            '#totpNext, button:has-text("Next")'
                                        )
                                        if next_btn2:
                                            next_btn2.click()
                                        else:
                                            page.keyboard.press("Enter")
                                        time.sleep(5 + random.random() * 2)
                                except Exception as retry_e:
                                    logger.warning(f"TOTP retry failed: {retry_e}")
                    except Exception as e:
                        logger.error(f"2FA step failed: {e}")
                        return None
                else:
                    logger.error("2FA required but no TOTP secret provided")
                    return None

            # ── Step 6: 处理 Google OAuth 同意页面 ──
            current_url = page.url

            logger.info(f"Step 6: After 2FA, current URL: {current_url[:120]}")

            # Google OAuth 同意页面处理
            # 可能需要多次点击 Continue（有时有多个步骤）
            for attempt in range(5):
                current_url = page.url

                if "app.tavily.com" in current_url or "tavily.com/home" in current_url:
                    logger.info("Already redirected to Tavily!")
                    break

                # 尝试在当前页面查找并点击同意按钮
                clicked = False
                for selector in [
                    'button:has-text("Continue")',
                    'button:has-text("Allow")',
                    '#submit_approve_access',
                    'button[data-idom-class*="submit"]',
                    'input[type="submit"]',
                    'button[type="submit"]',
                ]:
                    try:
                        btn = page.query_selector(selector)
                        if btn and btn.is_visible():
                            logger.info(f"Clicking consent/continue button: {selector}")
                            btn.click()
                            clicked = True
                            time.sleep(5 + random.random() * 2)
                            break
                    except Exception:
                        continue

                if not clicked:
                    logger.info(f"No button found (attempt {attempt+1}), waiting for page load...")
                    time.sleep(3)

                # 检查页面文本，提供更多调试信息
                try:
                    page_text = page.inner_text('body')[:300]
                    logger.info(f"Page text (first 300 chars): {page_text}")
                except Exception:
                    pass

            # ── Step 7: 等待回调到 Tavily ──
            logger.info("Step 7: Waiting for Tavily callback...")
            for i in range(45):
                current_url = page.url
                if "app.tavily.com" in current_url or "tavily.com/home" in current_url:
                    logger.info(f"Redirected to Tavily: {current_url[:100]}")
                    break
                time.sleep(1)
                if i % 10 == 9:
                    logger.info(f"Still waiting... URL: {current_url[:100]}")
            else:
                logger.error(f"Tavily callback timeout, stuck at: {page.url[:100]}")
                return None

            time.sleep(3)

            # ── Step 7.5: 处理 Tavily 首次登录的 "Stay updated" 欢迎弹窗 ──
            # Tavily 使用 Chakra UI，弹窗是 dialog 元素
            # checkbox 是 chakra-checkbox__input，真正的 input 在视口外隐藏
            # 必须通过 JavaScript 强制勾选，或点击其外层 label
            try:
                time.sleep(3)  # 等待弹窗加载
                logger.info("Step 7.5: Checking for 'Stay Updated' modal...")

                # 查找 dialog 元素（Chakra UI 弹窗）
                dialog = page.query_selector('[role="dialog"]')
                if dialog and dialog.is_visible():
                    logger.info("'Stay Updated' dialog found, handling...")

                    # ===== 核心修复 =====
                    # Chakra UI checkbox 的 input 被 CSS 隐藏在视口外 (position: absolute, left: -9999px 等)
                    # Playwright/Camoufox 的 .click() 无法点击 "视口外" 的元素
                    # 解决方案：用 JavaScript 直接触发 click，或者点击 label 容器
                    checkbox_clicked = False

                    # 方法1: 用 JavaScript 强制点击 dialog 内 checkbox 的 label
                    try:
                        result = page.evaluate("""
                            () => {
                                const dialog = document.querySelector('[role="dialog"]');
                                if (!dialog) return 'no dialog';
                                // 找到 label 元素（Chakra checkbox 的可点击区域）
                                const label = dialog.querySelector('label');
                                if (label) {
                                    label.click();
                                    return 'clicked label';
                                }
                                // 备用：找到 checkbox input 并直接改状态
                                const cb = dialog.querySelector('input[type="checkbox"]');
                                if (cb) {
                                    cb.click();
                                    return 'clicked input';
                                }
                                return 'not found';
                            }
                        """)
                        logger.info(f"Checkbox JS click result: {result}")
                        if "clicked" in result:
                            checkbox_clicked = True
                            time.sleep(1)
                    except Exception as e:
                        logger.warning(f"JS checkbox click failed: {e}")

                    # 方法2: 如果 JS 方法失败，尝试 force click
                    if not checkbox_clicked:
                        try:
                            cb_input = dialog.query_selector('input[type="checkbox"]')
                            if cb_input:
                                cb_input.dispatch_event("click")
                                checkbox_clicked = True
                                logger.info("Clicked checkbox via dispatch_event")
                                time.sleep(1)
                        except Exception as e:
                            logger.warning(f"dispatch_event failed: {e}")

                    # 点击 Continue 按钮（不管 checkbox 是否成功）
                    time.sleep(1)
                    try:
                        # 用 JavaScript 点击 Continue 按钮
                        result = page.evaluate("""
                            () => {
                                const dialog = document.querySelector('[role="dialog"]');
                                if (!dialog) return 'no dialog';
                                const buttons = dialog.querySelectorAll('button');
                                for (const btn of buttons) {
                                    if (btn.textContent.trim() === 'Continue') {
                                        btn.click();
                                        return 'clicked Continue';
                                    }
                                }
                                return 'Continue not found';
                            }
                        """)
                        logger.info(f"Continue button result: {result}")
                        time.sleep(3)
                    except Exception as e:
                        logger.warning(f"Continue button click failed: {e}")
                        # 最后尝试关闭弹窗
                        page.keyboard.press("Escape")
                        time.sleep(2)

                else:
                    logger.info("No dialog modal found, proceeding...")

                time.sleep(2)

            except Exception as e:
                logger.warning(f"Stay Updated page handling: {e}")

            # ── Step 8: 提取 API Key ──
            logger.info("Step 8: Extracting API Key...")
            api_key = _extract_api_key(page, timeout=20)

            if api_key:
                logger.info(f"Got API Key: {api_key[:15]}...")
                return {
                    "email": email,
                    "api_key": api_key,
                    "provider": "tavily",
                }
            else:
                logger.error("Failed to extract API Key")
                return None

    except Exception as e:
        logger.error(f"Registration failed for {email}: {e}")
        return None


class TavilyRegistrar:
    """Tavily Google OAuth 批量注册器"""

    def __init__(self, breaker: DomainBreaker):
        self.breaker = breaker

    async def register_with_google_accounts(
        self, accounts_text: str, proxy: str | None = None,
    ) -> list[dict]:
        """
        批量使用 Google 账号注册 Tavily。

        Args:
            accounts_text: 多行文本，每行格式 email|password|recovery|2fa|region

        Returns:
            结果列表
        """
        accounts = _parse_google_accounts(accounts_text)
        if not accounts:
            raise Exception("No valid accounts found")

        logger.info(f"Parsed {len(accounts)} Google accounts")
        results = []

        for i, account in enumerate(accounts):
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    _run_sync_in_clean_thread,
                    register_tavily_with_google,
                    account, REGISTER_HEADLESS,
                )
                if result:
                    results.append(result)
                    logger.info(f"[{i+1}/{len(accounts)}] SUCCESS: {account['email']}")
                else:
                    results.append({"error": "Registration returned None", "email": account["email"]})
                    logger.error(f"[{i+1}/{len(accounts)}] FAILED: {account['email']}")
            except Exception as e:
                results.append({"error": str(e), "email": account["email"]})
                logger.error(f"[{i+1}/{len(accounts)}] ERROR: {account['email']}: {e}")

            # 冷却
            if i < len(accounts) - 1:
                delay = COOLDOWN_BASE + random.randint(0, COOLDOWN_JITTER)
                logger.info(f"Cooling down {delay}s...")
                await asyncio.sleep(delay)

        return results
