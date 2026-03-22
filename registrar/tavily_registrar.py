import asyncio
import re
import random
import logging
from playwright.async_api import async_playwright
from duckmail_client import DuckMailClient
from domain_breaker import DomainBreaker
from config import REGISTRATION_PROXY, COOLDOWN_BASE, COOLDOWN_JITTER

logger = logging.getLogger(__name__)

# Auth0 sign-in entry — Playwright will click "Sign up" from here
TAVILY_SIGNIN_URL = "https://app.tavily.com/sign-in"


class TavilyRegistrar:
    """Tavily 自动注册（Playwright + Auth0 + DuckMail）"""

    def __init__(self, breaker: DomainBreaker):
        self.mail = DuckMailClient()
        self.breaker = breaker

    # ------------------------------------------------------------------
    # Internal: wait for Cloudflare Turnstile to resolve (invisible mode)
    # ------------------------------------------------------------------
    async def _wait_turnstile(self, page, timeout: int = 30):
        """Poll hidden captcha input until Turnstile fills it (max *timeout*s)."""
        for _ in range(timeout * 2):
            val = await page.evaluate(
                '() => { const el = document.querySelector(\'input[name="captcha"]\'); return el ? el.value : ""; }'
            )
            if val:
                logger.info("Turnstile captcha resolved")
                return True
            await asyncio.sleep(0.5)
        logger.warning("Turnstile captcha not resolved within timeout — continuing anyway")
        return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
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
            async with async_playwright() as p:
                browser_args = {}
                if proxy:
                    browser_args["proxy"] = {"server": proxy}

                browser = await p.chromium.launch(headless=True, **browser_args)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    )
                )
                page = await context.new_page()

                # ── Step 1: Open sign-in page (redirects to auth.tavily.com) ──
                logger.info("Navigating to Tavily sign-in page …")
                await page.goto(TAVILY_SIGNIN_URL, wait_until="domcontentloaded", timeout=60000)
                # Wait for Auth0 login form to render
                await page.wait_for_selector('input#email, input[name="email"]', timeout=30000)
                logger.info(f"Login page loaded: {page.url}")

                # ── Step 2: Click "Sign up" link ──
                signup_link = page.locator('a:has-text("Sign up")')
                await signup_link.wait_for(timeout=10000)
                await signup_link.click()
                logger.info("Clicked 'Sign up' link")

                # Wait for signup form
                await page.wait_for_selector('input#email, input[name="email"]', timeout=15000)
                await asyncio.sleep(1)
                logger.info(f"Signup page loaded: {page.url}")

                # ── Step 3: Wait for Turnstile to resolve ──
                await self._wait_turnstile(page, timeout=30)

                # ── Step 4: Fill email ──
                email_input = page.locator('input#email, input[name="email"]')
                await email_input.fill(email)
                logger.info(f"Filled email: {email}")
                await asyncio.sleep(0.5)

                # ── Step 5: Click Continue ──
                continue_btn = page.locator('button[type="submit"], button:has-text("Continue")')
                await continue_btn.first.click()
                logger.info("Clicked Continue on email step")

                # ── Step 6: Password step (Auth0 identifier-first) ──
                password_input = page.locator('input[name="password"], input[type="password"]')
                try:
                    await password_input.first.wait_for(timeout=15000)
                    await password_input.first.fill(password)
                    logger.info("Filled password")
                    await asyncio.sleep(0.5)

                    submit_btn = page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("Sign up")')
                    await submit_btn.first.click()
                    logger.info("Submitted signup form")
                    await asyncio.sleep(3)
                except Exception:
                    logger.info("No password step — may be passwordless / OTP flow")

                # ── Step 7: Wait for verification email ──
                logger.info(f"Waiting for verification email for {email} …")
                code = await self.mail.poll_for_code(mail_token, timeout=300, interval=5)

                if not code:
                    self.breaker.record_failure(domain)
                    raise Exception(f"Timeout waiting for verification email for {email}")

                logger.info(f"Got verification code/link: {code[:80]}…")

                # ── Step 8: Handle verification ──
                if code.startswith("http"):
                    await page.goto(code, wait_until="domcontentloaded", timeout=60000)
                    await asyncio.sleep(5)
                else:
                    otp_input = page.locator(
                        'input[name="code"], input[id*="code"], input[inputmode="numeric"], input[type="text"]'
                    )
                    try:
                        await otp_input.first.wait_for(timeout=10000)
                        await otp_input.first.fill(code)
                        verify_btn = page.locator(
                            'button[type="submit"], button:has-text("Verify"), button:has-text("Continue")'
                        )
                        await verify_btn.first.click()
                        await asyncio.sleep(5)
                    except Exception as e:
                        logger.warning(f"OTP input not found, skipping: {e}")

                # ── Step 9: Extract API Key ──
                api_key = await self._extract_api_key(page)

                await browser.close()

                if api_key:
                    self.breaker.record_success(domain)
                    logger.info(f"Successfully registered Tavily: {email}, key: {api_key[:15]}…")
                    return {
                        "email": email,
                        "api_key": api_key,
                        "provider": "tavily",
                    }
                else:
                    self.breaker.record_failure(domain)
                    raise Exception(f"Failed to extract API key for {email}")

        except Exception as e:
            logger.error(f"Registration failed for {email}: {e}")
            raise
        finally:
            await self.mail.cleanup(mail_account_id, mail_token)

    # ------------------------------------------------------------------
    # Extract tvly-* key from page or navigate to dashboard
    # ------------------------------------------------------------------
    async def _extract_api_key(self, page) -> str | None:
        for attempt in range(3):
            content = await page.content()
            match = re.search(r'tvly-[A-Za-z0-9]{20,}', content)
            if match:
                return match.group(0)

            # Try navigating to dashboard / API keys page
            targets = [
                "https://app.tavily.com/home",
                "https://app.tavily.com/dashboard",
            ]
            for url in targets:
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await asyncio.sleep(3)
                    content = await page.content()
                    match = re.search(r'tvly-[A-Za-z0-9]{20,}', content)
                    if match:
                        return match.group(0)
                except Exception:
                    continue

            await asyncio.sleep(3)

        return None

    async def batch_register(self, count: int = 1, proxy: str | None = None) -> list[dict]:
        results = []
        for i in range(count):
            try:
                result = await self.register(proxy)
                if result:
                    results.append(result)
                # 注册间隔
                if i < count - 1:
                    delay = COOLDOWN_BASE + random.randint(0, COOLDOWN_JITTER)
                    logger.info(f"Cooling down for {delay}s before next registration...")
                    await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"Registration {i+1}/{count} failed: {e}")
                results.append({"error": str(e), "index": i})
        return results
