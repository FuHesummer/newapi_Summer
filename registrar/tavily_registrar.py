import asyncio
import random
import logging
from playwright.async_api import async_playwright
from duckmail_client import DuckMailClient
from domain_breaker import DomainBreaker
from config import TAVILY_SIGNUP_URL, REGISTRATION_PROXY, COOLDOWN_BASE, COOLDOWN_JITTER

logger = logging.getLogger(__name__)


class TavilyRegistrar:
    """Tavily 自动注册（Playwright + Auth0 + DuckMail）"""

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
            async with async_playwright() as p:
                browser_args = {}
                if proxy:
                    browser_args["proxy"] = {"server": proxy}

                browser = await p.chromium.launch(headless=True, **browser_args)
                context = await browser.new_context()
                page = await context.new_page()

                # 3. 打开 Tavily 注册页面
                await page.goto(TAVILY_SIGNUP_URL, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

                # 4. 查找并点击 Sign Up 链接
                signup_link = page.locator('a:has-text("Sign up"), a:has-text("sign up"), a:has-text("Register")')
                if await signup_link.count() > 0:
                    await signup_link.first.click()
                    await asyncio.sleep(2)

                # 5. 填写邮箱
                email_input = page.locator('input[name="email"], input[type="email"], input[id*="email"]')
                await email_input.first.fill(email)
                await asyncio.sleep(0.5)

                # 提交邮箱（Auth0 identifier-first 流程）
                submit_btn = page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("Next")')
                if await submit_btn.count() > 0:
                    await submit_btn.first.click()
                    await asyncio.sleep(2)

                # 6. 填写密码（Auth0 第二步）
                password_input = page.locator('input[name="password"], input[type="password"]')
                if await password_input.count() > 0:
                    await password_input.first.fill(password)
                    await asyncio.sleep(0.5)

                    submit_btn2 = page.locator('button[type="submit"], button:has-text("Continue"), button:has-text("Sign up")')
                    if await submit_btn2.count() > 0:
                        await submit_btn2.first.click()
                        await asyncio.sleep(3)

                # 7. 等待验证邮件
                logger.info(f"Waiting for verification email for {email}...")
                code = await self.mail.poll_for_code(mail_token, timeout=240, interval=5)

                if not code:
                    self.breaker.record_failure(domain)
                    raise Exception(f"Timeout waiting for verification email for {email}")

                logger.info(f"Got verification code/link: {code[:50]}...")

                # 8. 处理验证
                if code.startswith("http"):
                    # 验证链接
                    await page.goto(code, wait_until="networkidle", timeout=30000)
                else:
                    # OTP 验证码
                    otp_input = page.locator('input[name="code"], input[id*="code"], input[type="text"]')
                    if await otp_input.count() > 0:
                        await otp_input.first.fill(code)
                        verify_btn = page.locator('button[type="submit"], button:has-text("Verify"), button:has-text("Continue")')
                        if await verify_btn.count() > 0:
                            await verify_btn.first.click()
                            await asyncio.sleep(3)

                # 9. 等待登录完成，提取 API Key
                await asyncio.sleep(5)

                # 尝试从页面提取 API Key (tvly-...)
                api_key = None
                page_content = await page.content()

                import re
                key_match = re.search(r'tvly-[A-Za-z0-9]{20,}', page_content)
                if key_match:
                    api_key = key_match.group(0)
                else:
                    # 尝试导航到 API keys 页面
                    try:
                        await page.goto("https://app.tavily.com/home", wait_until="networkidle", timeout=15000)
                        await asyncio.sleep(3)
                        page_content = await page.content()
                        key_match = re.search(r'tvly-[A-Za-z0-9]{20,}', page_content)
                        if key_match:
                            api_key = key_match.group(0)
                    except Exception:
                        pass

                await browser.close()

                if api_key:
                    self.breaker.record_success(domain)
                    logger.info(f"Successfully registered Tavily account: {email}, key: {api_key[:15]}...")
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
            # 清理临时邮箱
            await self.mail.cleanup(mail_account_id, mail_token)

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
