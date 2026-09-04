from __future__ import annotations

import re
from typing import Any

PII = re.compile(
    r"(\b\d{3}-\d{2}-\d{4}\b)|(\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b)|(\b(ssn|passport|secret|password)\b)",
    re.I,
)
INJECTION = re.compile(r"ignore (previous|all) (instructions|rules)|exfiltrat|disable guardrail", re.I)


class McpMesh:
    def __init__(self, servers: list[dict]):
        self.servers = {s["id"]: s for s in servers}

    def list_servers(self) -> list[dict]:
        return list(self.servers.values())

    def get(self, server_id: str) -> dict | None:
        return self.servers.get(server_id)

    def invoke(self, server_id: str, tool: str, argument: str, authorized: bool) -> dict[str, Any]:
        server = self.servers.get(server_id)
        if not server:
            return {"ok": False, "status": 404, "error": "mcp_server_not_found"}
        if not authorized:
            return {"ok": False, "status": 401, "error": "mcp_unauthorized", "server": server["name"]}
        if tool not in server.get("tools", []):
            return {"ok": False, "status": 403, "error": "tool_not_allowlisted", "server": server["name"], "tool": tool}
        if PII.search(argument or "") and "no_pii_egress" in server.get("guardrails", []):
            return {
                "ok": False,
                "status": 451,
                "error": "guardrail_pii",
                "server": server["name"],
                "tool": tool,
                "guardrail": "no_pii_egress",
            }
        if INJECTION.search(argument or ""):
            return {
                "ok": False,
                "status": 403,
                "error": "guardrail_injection",
                "server": server["name"],
                "tool": tool,
            }
        if server.get("status") == "throttled" or server.get("used_rpm", 0) >= server.get("quota", {}).get("rpm", 10**9):
            return {
                "ok": False,
                "status": 429,
                "error": "usage_quota",
                "server": server["name"],
                "quota": server.get("quota"),
            }
        privileged = tool in server.get("privileged_tools", [])
        if privileged and "prod_write_requires_hitl" in server.get("guardrails", []):
            return {
                "ok": False,
                "status": 423,
                "error": "hitl_required",
                "server": server["name"],
                "tool": tool,
                "detail": "Production MCP writes stay blocked until a human approves the change window.",
            }
        server["used_rpm"] = int(server.get("used_rpm") or 0) + 1
        previews = {
            "search_docs": f"3 cited runbooks for '{argument[:80]}'",
            "get_page": "SOP-GW-014 § regional drain",
            "cite": "SOP-GW-014, SOP-RL-002",
            "get_pods": "envoy-gateway-7f9c / 2 ready, mcp-broker-0 / 1 ready",
            "describe_ingress": "HTTPProxy helixgate-edge hosts=api,ai,mcp.helixgate.dev",
            "rollout_status": "envoy-gateway progressing 1/2 updated",
            "lint_envoy": "2 policy findings, 0 syntax errors",
            "lint_httpproxy": "Contour HTTPProxy valid; TLS secret days_to_expiry=9",
            "lint_helm": "values.tls.days_to_expiry below 21",
            "summarize_logs": "503s concentrated on cc-api.sjc; FRA already unhealthy",
            "propose_remediation": "Drain SJC creative-cloud weight to IAD after HITL",
        }
        return {
            "ok": True,
            "status": 200,
            "server": server["name"],
            "tool": tool,
            "result": previews.get(tool, f"{tool} accepted"),
            "usage": {"rpm": server["used_rpm"], "limit": server["quota"]["rpm"]},
        }
