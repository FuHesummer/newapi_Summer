import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from tavily_registrar import TavilyRegistrar
from domain_breaker import DomainBreaker
from duckmail_client import DuckMailClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Registrar Sidecar", version="1.0.0")
breaker = DomainBreaker()
tavily_registrar = TavilyRegistrar(breaker)
mail_client = DuckMailClient()


class RegisterRequest(BaseModel):
    count: int = 1
    proxy: str | None = None


@app.post("/register/tavily")
async def register_tavily(req: RegisterRequest):
    try:
        results = await tavily_registrar.batch_register(count=req.count, proxy=req.proxy)
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "registrar"}


@app.get("/domains")
async def domains():
    try:
        available = await mail_client.get_available_domains()
        status = breaker.get_status()
        # 合并：所有域名 + 熔断状态
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


@app.on_event("startup")
async def startup():
    logger.info("Registrar sidecar started")
    # 预加载域名到熔断器
    try:
        domains = await mail_client.get_available_domains()
        for d in domains:
            breaker._init_domain(d)
        logger.info(f"Loaded {len(domains)} domains: {domains}")
    except Exception as e:
        logger.warning(f"Failed to load domains on startup: {e}")
