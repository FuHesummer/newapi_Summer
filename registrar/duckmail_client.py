"""DuckMail 临时邮箱客户端 — 适配 DuckMail API"""
import httpx
import asyncio
import random
import string
import re
import logging
from config import DUCKMAIL_BASE_URL, DUCKMAIL_API_KEY

logger = logging.getLogger(__name__)


class DuckMailClient:
    """DuckMail 临时邮箱客户端"""

    def __init__(self):
        self.base_url = DUCKMAIL_BASE_URL
        self.api_key = DUCKMAIL_API_KEY

    async def get_available_domains(self) -> list[str]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{self.base_url}/domains",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [d["domain"] for d in data.get("hydra:member", []) if d.get("isVerified")]

    async def create_account(self, domain: str) -> dict:
        """创建邮箱账号，生成强密码（满足 DuckMail >=6位要求）"""
        username = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
        email = f"{username}@{domain}"
        password = f"Tv{self._rand_str(6)}{random.randint(100,999)}!A"

        async with httpx.AsyncClient(timeout=15) as client:
            # POST /accounts
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
            account_id = data.get("id", "")
            token = data.get("token", "")

            # 如果创建响应没有 token，单独获取
            if not token:
                token_resp = await client.post(
                    f"{self.base_url}/token",
                    headers={"Content-Type": "application/json"},
                    json={"address": email, "password": password},
                )
                if token_resp.status_code == 200:
                    token_data = token_resp.json()
                    token = token_data.get("token", "")
                    if not account_id:
                        account_id = token_data.get("id", "")

            return {
                "email": email,
                "password": password,
                "token": token,
                "account_id": account_id,
            }

    async def poll_for_code(
        self, token: str, timeout: int = 90, interval: int = 3,
        service: str = "exa",
    ) -> str | None:
        """轮询邮箱，提取 6 位 OTP 验证码"""
        elapsed = 0
        seen_ids: set[str] = set()

        async with httpx.AsyncClient(timeout=15) as client:
            while elapsed < timeout:
                try:
                    resp = await client.get(
                        f"{self.base_url}/messages?page=1",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        messages = data.get("hydra:member", [])
                        for msg in messages:
                            msg_id = str(msg.get("id", ""))
                            if not msg_id or msg_id in seen_ids:
                                continue
                            seen_ids.add(msg_id)

                            # 获取邮件详情
                            detail_resp = await client.get(
                                f"{self.base_url}/messages/{msg_id}",
                                headers={"Authorization": f"Bearer {token}"},
                            )
                            if detail_resp.status_code != 200:
                                continue

                            detail = detail_resp.json()
                            text = detail.get("text", "")
                            html_list = detail.get("html", [])
                            html = html_list[0] if html_list else ""
                            subject = detail.get("subject", "")
                            content = f"{subject} {text} {html}"
                            combined = content.lower()

                            # Exa 专用匹配
                            if service == "exa":
                                if "exa" not in combined:
                                    continue
                                if "verification code" not in combined and "sign in" not in combined:
                                    continue
                                # 优先匹配 "verification code is XXXXXX"
                                match = re.search(
                                    r'verification code(?:\s+for\s+exa)?(?:\s+is)?[^0-9]*(\d{6})',
                                    content, re.IGNORECASE,
                                )
                                if match:
                                    return match.group(1)

                            # 通用 6 位 OTP 匹配
                            content_clean = re.sub(
                                r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
                                '', content,
                            )
                            otp_match = re.search(r'(?<!\d)(\d{6})(?!\d)', content_clean)
                            if otp_match:
                                return otp_match.group(1)

                except Exception as e:
                    logger.warning(f"DuckMail poll error: {e}")

                await asyncio.sleep(interval)
                elapsed += interval
        return None

    async def cleanup(self, account_id: str, token: str):
        """删除临时邮箱账号"""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.delete(
                    f"{self.base_url}/accounts/{account_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except Exception:
            pass

    @staticmethod
    def _rand_str(n: int = 8) -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))
