from __future__ import annotations

import uuid
from datetime import datetime, timezone

from helixgate.catalog import clone_catalog
from helixgate.gateway.engine import GatewayEngine
from helixgate.gitops.renderer import lint_mcp, lint_route, manifests_for, nginx_snippet
from helixgate.mcp.mesh import McpMesh
from helixgate.rag.corpus import DOCUMENTS, chunks
from helixgate.rag.hybrid import HybridIndex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ControlPlane:
    def __init__(self) -> None:
        data = clone_catalog()
        self.regions = data["regions"]
        self.policies = data["policies"]
        self.gitops = data["gitops"]
        self.logs = data["logs"]
        self.engine = GatewayEngine(data["routes"])
        self.mcp = McpMesh(data["mcp"])
        self.index = HybridIndex(chunks())
        self.documents = DOCUMENTS
        self.runs: list[dict] = []
        self.hitl: list[dict] = []
        self.events: list[dict] = []
        self._sync_gitops_health()

    def audit(self, event_type: str, detail: str, actor: str = "system") -> None:
        self.events.insert(
            0,
            {
                "event_id": f"evt-{uuid.uuid4().hex[:8]}",
                "actor": actor,
                "event_type": event_type,
                "detail": detail,
                "created_at": _now(),
            },
        )
        self.events = self.events[:80]

    def _sync_gitops_health(self) -> None:
        mcp_edge = self.engine.get("rt-mcp-edge")
        days = int((mcp_edge or {}).get("tls", {}).get("days_to_expiry") or 0)
        for app in self.gitops:
            if app["name"] != "helixgate-mcp-mesh":
                continue
            if days >= 21:
                app["sync"] = "Synced"
                app["health"] = "Healthy"
                app["drift"] = None
                app["revision"] = "main@live"
            else:
                app["sync"] = "OutOfSync"
                app["health"] = "Degraded"
                app["drift"] = f"mcp-edge TLS days_to_expiry={days}, desired >= 21"

    def overview(self) -> dict:
        routes = self.engine.list_routes()
        mcp = self.mcp.list_servers()
        findings = []
        for r in routes:
            findings.extend(lint_route(r))
        for s in mcp:
            findings.extend(lint_mcp(s))
        active = [r for r in routes if r.get("status") == "active"]
        return {
            "service": "helixgate",
            "regions": self.regions,
            "routes": len(routes),
            "active_routes": len(active),
            "mcp_servers": len(mcp),
            "pending_hitl": sum(1 for h in self.hitl if h["status"] == "pending"),
            "gitops_drift": sum(1 for g in self.gitops if g.get("sync") != "Synced"),
            "policy_findings": len(findings),
            "critical_findings": sum(1 for f in findings if f["severity"] == "critical"),
            "rps": round(sum((r.get("rate_limit") or {}).get("rps", 0) for r in active) * 0.31, 1),
            "slo": 99.95,
            "error_budget_remaining": 64,
            "gateway_stats": self.engine.snapshot_stats(),
        }

    def validate_all(self) -> dict:
        route_findings = []
        for r in self.engine.list_routes():
            route_findings.extend(lint_route(r))
        mcp_findings = []
        for s in self.mcp.list_servers():
            mcp_findings.extend(lint_mcp(s))
        return {"routes": route_findings, "mcp": mcp_findings}

    def manifests(self, route_id: str) -> dict | None:
        route = self.engine.get(route_id)
        if not route:
            return None
        docs = manifests_for(route)
        docs["nginx"] = nginx_snippet(route)
        return docs

    def register_route(self, body: dict) -> dict:
        route_id = body.get("id") or f"rt-{uuid.uuid4().hex[:6]}"
        route = {
            "id": route_id,
            "name": body.get("name") or route_id,
            "host": body.get("host") or f"{route_id}.helixgate.dev",
            "path": body.get("path") or "/v1/*",
            "methods": body.get("methods") or ["GET", "POST"],
            "upstreams": body.get("upstreams")
            or [{"region": "sjc", "target": f"{route_id}.sjc.svc:8443", "weight": 100, "healthy": True}],
            "lb_policy": body.get("lb_policy") or "weighted_least_request",
            "rate_limit": body.get("rate_limit") or {"rps": 50, "burst": 100, "unit": "jwt_sub"},
            "auth": body.get("auth") or {"type": "jwt", "audiences": [body.get("audience") or route_id], "scopes": ["api"]},
            "tls": body.get("tls") or {"mode": "terminate", "min_version": "1.3", "mtls": True, "days_to_expiry": 90},
            "timeout_ms": int(body.get("timeout_ms") or 2000),
            "retries": int(body.get("retries") or 1),
            "circuit_breaker": {"consecutive_5xx": 8, "ejection_pct": 15},
            "status": "active",
            "owner": body.get("owner") or "self-service",
            "sli_p99_ms": 0,
            "error_rate": 0,
        }
        self.engine.upsert(route)
        self.gitops.insert(
            0,
            {
                "name": route["name"],
                "repo": "github.com/Ananyanagaraj11/helixgate",
                "path": "infra/helm/helixgate",
                "dest": "helixgate / sjc-prod-1",
                "sync": "Synced",
                "health": "Healthy",
                "revision": "main@self-service",
                "auto_sync": True,
            },
        )
        self.audit("route.register", f"self-service created {route['id']}")
        return route

    def apply_remediation(self, rem: dict, actor: str) -> dict:
        action = rem.get("action")
        if action == "drain_region":
            route = self.engine.get(rem["route_id"])
            if route:
                for u in route["upstreams"]:
                    if u["region"] == rem.get("region"):
                        u["healthy"] = False
                        u["weight"] = 0
                    if u["region"] == rem.get("shift_to"):
                        u["healthy"] = True
                        u["weight"] = 100
                route["error_rate"] = 0.04
        elif action == "raise_quota":
            server = self.mcp.get(rem["server_id"])
            if server:
                server["quota"]["tokens_per_day"] = rem["tokens_per_day"]
                server["status"] = "healthy"
                server["used_rpm"] = 0
        elif action == "gitops_sync":
            route = self.engine.get("rt-mcp-edge")
            if route:
                route["tls"]["days_to_expiry"] = 90
            self._sync_gitops_health()
        elif action == "rotate_tls":
            route = self.engine.get(rem["route_id"])
            if route:
                route["tls"]["days_to_expiry"] = rem.get("days_to_expiry", 90)
                route["tls"]["min_version"] = "1.3"
                route["tls"]["mtls"] = True
            self._sync_gitops_health()
        elif action == "lock_lab_route":
            route = self.engine.get(rem["route_id"])
            if route:
                route["status"] = "draft"
                route["rate_limit"] = {"rps": 20, "burst": 40, "unit": "ip"}
                route["auth"] = {"type": "jwt", "audiences": ["lab"], "scopes": ["lab.read"]}
                route["tls"] = {"mode": "terminate", "min_version": "1.3", "mtls": True, "days_to_expiry": 90}
                route["retries"] = 1
        self.audit("hitl.apply", rem.get("summary", action), actor=actor)
        return rem

    def resolve_hitl(self, review_id: str, approved: bool, actor: str, feedback: str) -> dict:
        review = next((h for h in self.hitl if h["review_id"] == review_id), None)
        if not review:
            raise ValueError("review not found")
        if review["status"] != "pending":
            raise ValueError("review already resolved")
        review["status"] = "approved" if approved else "rejected"
        review["actor"] = actor
        review["feedback"] = feedback
        review["resolved_at"] = _now()
        if approved:
            self.apply_remediation(review["remediation"], actor)
        else:
            self.audit("hitl.reject", review["remediation"].get("summary", ""), actor=actor)
        for run in self.runs:
            if run["run_id"] == review["run_id"]:
                run["hitl_status"] = review["status"]
        return review
