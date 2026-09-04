from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

GATEWAY_REQUESTS = Counter("helixgate_gateway_requests_total", "Gateway invocations", ["route", "status"])
MCP_REQUESTS = Counter("helixgate_mcp_invocations_total", "MCP tool calls", ["server", "status"])
AIOPS_RUNS = Counter("helixgate_aiops_runs_total", "AI ops analyses", ["grounded"])
HITL = Counter("helixgate_hitl_total", "HITL decisions", ["decision"])
ROUTE_ERROR = Gauge("helixgate_route_error_rate", "Configured error rate", ["route"])
REGION_CAP = Gauge("helixgate_region_capacity", "Region capacity ratio", ["region"])
GATEWAY_LATENCY = Histogram("helixgate_gateway_latency_ms", "Simulated gateway latency", ["route"])


def metrics_response() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
