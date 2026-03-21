import httpx
import asyncio
import random
import string
import re
from config import DUCKMAIL_BASE_URL, DUCKMAIL_API_KEY


class DuckMailClient:
    """DuckMail 临时邮箱客户端 (sfj.blogsummer.cn)"""

    def __init__(self):
        self.base_url = DUCKMAIL_BASE_URL
        self.api_key = DUCKMAIL_API_KEY

    async def get_available_domains(self) -> list[str]:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base_url}/domains",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [d["domain"] for d in data.get("hydra:member", []) if d.get("isVerified")]

    async def create_account(self, domain: str) -> dict:
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{username}@{domain}"
        password = "".join(random.choices(string.ascii_letters + string.digits, k=16))

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/accounts",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={"address": email, "password": password},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "email": email,
                "password": password,
                "token": data.get("token"),
                "account_id": data.get("id"),
            }

    async def poll_for_code(
        self, token: str, timeout: int = 240, interval: int = 3
    ) -> str | None:
        elapsed = 0
        async with httpx.AsyncClient() as client:
            while elapsed < timeout:
                resp = await client.get(
                    f"{self.base_url}/messages?page=1",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    messages = data.get("hydra:member", [])
                    for msg in messages:
                        # 尝试从邮件中提取验证码或验证链接
                        msg_id = msg.get("id")
                        detail_resp = await client.get(
                            f"{self.base_url}/messages/{msg_id}",
                            headers={"Authorization": f"Bearer {token}"},
                        )
                        if detail_resp.status_code == 200:
                            detail = detail_resp.json()
                            text = detail.get("text", "")
                            html_list = detail.get("html", [])
                            html = html_list[0] if html_list else ""
                            content = text + " " + html

                            # 匹配 6 位 OTP
                            otp_match = re.search(r"\b(\d{6})\b", content)
                            if otp_match:
                                return otp_match.group(1)

                            # 匹配验证链接
                            link_match = re.search(
                                r'https?://[^\s"<>]+(?:verify|confirm|activate)[^\s"<>]*',
                                content,
                                re.IGNORECASE,
                            )
                            if link_match:
                                return link_match.group(0)

                await asyncio.sleep(interval)
                elapsed += interval
        return None

    async def cleanup(self, account_id: str, token: str):
        try:
            async with httpx.AsyncClient() as client:
                await client.delete(
                    f"{self.base_url}/accounts/{account_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except Exception:
            pass
