import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from exa_registrar import ExaRegistrar
from tavily_registrar import TavilyRegistrar
from domain_breaker import DomainBreaker
from duckmail_client import DuckMailClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Registrar sidecar started (Exa + Tavily-Google)")
    try:
        domains_list = await mail_client.get_available_domains()
        for d in domains_list:
            breaker._init_domain(d)
        logger.info(f"Loaded {len(domains_list)} domains: {domains_list}")
    except Exception as e:
        logger.warning(f"Failed to load domains on startup: {e}")
    yield


app = FastAPI(title="Registrar Sidecar", version="3.0.0", lifespan=lifespan)
breaker = DomainBreaker()
exa_registrar = ExaRegistrar(breaker)
tavily_registrar = TavilyRegistrar(breaker)
mail_client = DuckMailClient()


# ── Exa 注册（DuckMail OTP） ──

class ExaRegisterRequest(BaseModel):
    count: int = 1
    proxy: str | None = None


@app.post("/register/exa")
async def register_exa(req: ExaRegisterRequest):
    try:
        results = await exa_registrar.batch_register(count=req.count, proxy=req.proxy)
        successful = [r for r in results if "api_key" in r]
        failed = [r for r in results if "error" in r]
        return {
            "success": True,
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "keys": successful,
            "errors": failed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Tavily 注册（Google OAuth） ──

class TavilyGoogleRegisterRequest(BaseModel):
    accounts: str = ""  # 多行文本：email|password|recovery|2fa|region
    count: int = 0      # 兼容旧的 count 模式（但 Tavily 需要 Google 账号，此字段被忽略）
    proxy: str | None = None


@app.post("/register/tavily")
async def register_tavily(req: TavilyGoogleRegisterRequest):
    # Tavily 只支持 Google OAuth 模式，必须提供 accounts
    if not req.accounts or not req.accounts.strip():
        raise HTTPException(
            status_code=400,
            detail="Tavily 注册需要提供 Google 账号（accounts 参数），格式：email|password|recovery|2fa|region，每行一个"
        )
    try:
        results = await tavily_registrar.register_with_google_accounts(
            accounts_text=req.accounts, proxy=req.proxy,
        )
        successful = [r for r in results if "api_key" in r]
        failed = [r for r in results if "error" in r]
        return {
            "success": True,
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "keys": successful,
            "errors": failed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 通用 ──

@app.get("/health")
async def health():
    return {"status": "ok", "service": "registrar", "providers": ["exa", "tavily-google"]}


@app.get("/domains")
async def domains():
    try:
        available = await mail_client.get_available_domains()
        status = breaker.get_status()
        domain_status = {}
        for d in available:
            domain_status[d] = {"status": "healthy", "success": 0, "fail": 0}
        for s in status:
            domain_status[s["domain"]] = s
        return {
            "domains": list(domain_status.values()),
            "total": len(available),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
