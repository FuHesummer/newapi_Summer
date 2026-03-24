import time
from config import BREAKER_FAIL_THRESHOLD, BREAKER_WINDOW_SECONDS, BREAKER_OPEN_SECONDS


class DomainBreaker:
    """域名熔断器：多域名轮询 + 失败率统计 + 自动熔断"""

    def __init__(self):
        self.stats: dict[str, dict] = {}
        self.index = 0

    def _init_domain(self, domain: str):
        if domain not in self.stats:
            self.stats[domain] = {
                "success": 0,
                "fail": 0,
                "consecutive_fails": 0,
                "last_fail_time": 0,
                "circuit_open_until": 0,
            }

    def get_available_domain(self, domains: list[str]) -> str | None:
        now = time.time()
        available = []
        for d in domains:
            self._init_domain(d)
            s = self.stats[d]
            # 跳过熔断中的域名
            if s["circuit_open_until"] > now:
                continue
            # 半开状态：熔断到期，允许一次试探
            available.append(d)

        if not available:
            return None

        # 轮询
        self.index = self.index % len(available)
        domain = available[self.index]
        self.index += 1
        return domain

    def record_success(self, domain: str):
        self._init_domain(domain)
        s = self.stats[domain]
        s["success"] += 1
        s["consecutive_fails"] = 0

    def record_failure(self, domain: str):
        self._init_domain(domain)
        s = self.stats[domain]
        s["fail"] += 1
        s["consecutive_fails"] += 1
        s["last_fail_time"] = time.time()

        # 连续失败达到阈值 → 熔断
        if s["consecutive_fails"] >= BREAKER_FAIL_THRESHOLD:
            s["circuit_open_until"] = time.time() + BREAKER_OPEN_SECONDS

    def get_status(self) -> list[dict]:
        now = time.time()
        result = []
        for domain, s in self.stats.items():
            status = "healthy"
            remaining = 0
            if s["circuit_open_until"] > now:
                status = "open"
                remaining = int(s["circuit_open_until"] - now)
            result.append({
                "domain": domain,
                "status": status,
                "success": s["success"],
                "fail": s["fail"],
                "consecutive_fails": s["consecutive_fails"],
                "remaining_seconds": remaining,
            })
        return result
