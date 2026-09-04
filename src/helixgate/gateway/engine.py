from __future__ import annotations

import random
import time
from typing import Any

from helixgate.config import DEMO_RATE_BURST, DEMO_RATE_RPS


class TokenBucket:
    def __init__(self, rps: float, burst: float):
        self.rps = rps
        self.burst = burst
        self.tokens = burst
        self.ts = time.monotonic()

    def allow(self, n: float = 1.0) -> bool:
        now = time.monotonic()
        self.tokens = min(self.burst, self.tokens + (now - self.ts) * self.rps)
        self.ts = now
        if self.tokens >= n:
            self.tokens -= n
            return True
        return False


class GatewayEngine:
    def __init__(self, routes: list[dict]):
        self.routes = {r["id"]: r for r in routes}
        self.buckets: dict[str, TokenBucket] = {}
        self.stats: dict[str, dict[str, int]] = {}

    def get(self, route_id: str) -> dict | None:
        return self.routes.get(route_id)

    def list_routes(self) -> list[dict]:
        return list(self.routes.values())

    def upsert(self, route: dict) -> dict:
        self.routes[route["id"]] = route
        return route

    def _bucket(self, route_id: str, identity: str) -> TokenBucket:
        key = f"{route_id}:{identity}"
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(DEMO_RATE_RPS, DEMO_RATE_BURST)
        return self.buckets[key]

    def pick_upstream(self, route: dict) -> dict | None:
        healthy = [u for u in route.get("upstreams", []) if u.get("healthy")]
        if not healthy:
            return None
        policy = route.get("lb_policy") or "round_robin"
        if policy in {"weighted_least_request", "weighted_round_robin", "ewma", "ring_hash"}:
            weights = [max(int(u.get("weight") or 1), 1) for u in healthy]
            return random.choices(healthy, weights=weights, k=1)[0]
        return random.choice(healthy)

    def _bump(self, route_id: str, field: str) -> None:
        row = self.stats.setdefault(route_id, {"ok": 0, "denied": 0, "limited": 0, "fail": 0})
        row[field] = row.get(field, 0) + 1

    def invoke(self, route_id: str, identity: str, authorized: bool) -> dict[str, Any]:
        route = self.routes.get(route_id)
        if not route:
            return {"ok": False, "status": 404, "error": "route_not_found"}
        if route.get("status") != "active":
            self._bump(route_id, "denied")
            return {"ok": False, "status": 403, "error": "route_not_active", "route": route["name"]}
        if not authorized:
            self._bump(route_id, "denied")
            return {"ok": False, "status": 401, "error": "unauthorized", "route": route["name"]}
        if route.get("rate_limit") and not self._bucket(route_id, identity).allow():
            self._bump(route_id, "limited")
            return {
                "ok": False,
                "status": 429,
                "error": "rate_limited",
                "route": route["name"],
                "retry_after_ms": 400,
                "unit": route["rate_limit"]["unit"],
            }
        upstream = self.pick_upstream(route)
        if not upstream:
            self._bump(route_id, "fail")
            return {"ok": False, "status": 503, "error": "no_healthy_upstream", "route": route["name"]}
        self._bump(route_id, "ok")
        return {
            "ok": True,
            "status": 200,
            "route": route["name"],
            "upstream": upstream["target"],
            "region": upstream["region"],
            "lb_policy": route["lb_policy"],
            "tls": route["tls"]["min_version"],
            "identity": identity,
        }

    def snapshot_stats(self) -> dict[str, dict[str, int]]:
        return {k: dict(v) for k, v in self.stats.items()}
