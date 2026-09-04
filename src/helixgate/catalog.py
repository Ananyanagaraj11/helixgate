from __future__ import annotations

from copy import deepcopy

REGIONS = [
    {
        "id": "sjc",
        "name": "San Jose",
        "code": "sjc-prod-1",
        "role": "primary",
        "latency_ms": 12,
        "status": "healthy",
        "capacity": 0.62,
    },
    {
        "id": "iad",
        "name": "Ashburn",
        "code": "iad-prod-1",
        "role": "secondary",
        "latency_ms": 68,
        "status": "healthy",
        "capacity": 0.41,
    },
    {
        "id": "fra",
        "name": "Frankfurt",
        "code": "fra-prod-1",
        "role": "secondary",
        "latency_ms": 141,
        "status": "degraded",
        "capacity": 0.88,
    },
]

ROUTES = [
    {
        "id": "rt-creative-cloud",
        "name": "creative-cloud-api",
        "host": "api.helixgate.dev",
        "path": "/v2/creative/*",
        "methods": ["GET", "POST", "PUT"],
        "upstreams": [
            {"region": "sjc", "target": "cc-api.sjc.svc:8443", "weight": 70, "healthy": True},
            {"region": "iad", "target": "cc-api.iad.svc:8443", "weight": 20, "healthy": True},
            {"region": "fra", "target": "cc-api.fra.svc:8443", "weight": 10, "healthy": False},
        ],
        "lb_policy": "weighted_least_request",
        "rate_limit": {"rps": 2000, "burst": 4000, "unit": "ip+jwt_sub"},
        "auth": {"type": "jwt", "audiences": ["cc-api"], "scopes": ["creative.read", "creative.write"]},
        "tls": {"mode": "terminate", "min_version": "1.3", "mtls": True, "days_to_expiry": 86},
        "timeout_ms": 2500,
        "retries": 2,
        "circuit_breaker": {"consecutive_5xx": 8, "ejection_pct": 15},
        "status": "active",
        "owner": "dx-gateway",
        "sli_p99_ms": 94,
        "error_rate": 0.21,
    },
    {
        "id": "rt-firefly",
        "name": "firefly-inference",
        "host": "ai.helixgate.dev",
        "path": "/v1/firefly/*",
        "methods": ["POST"],
        "upstreams": [
            {"region": "sjc", "target": "ffly-infer.sjc.svc:8443", "weight": 50, "healthy": True},
            {"region": "iad", "target": "ffly-infer.iad.svc:8443", "weight": 50, "healthy": True},
        ],
        "lb_policy": "ewma",
        "rate_limit": {"rps": 400, "burst": 800, "unit": "jwt_sub"},
        "auth": {"type": "jwt", "audiences": ["firefly"], "scopes": ["gen.infer"]},
        "tls": {"mode": "terminate", "min_version": "1.3", "mtls": True, "days_to_expiry": 41},
        "timeout_ms": 8000,
        "retries": 1,
        "circuit_breaker": {"consecutive_5xx": 5, "ejection_pct": 20},
        "status": "active",
        "owner": "genai-platform",
        "sli_p99_ms": 640,
        "error_rate": 0.8,
    },
    {
        "id": "rt-experience",
        "name": "experience-platform",
        "host": "aep.helixgate.dev",
        "path": "/v3/experience/*",
        "methods": ["GET", "POST"],
        "upstreams": [
            {"region": "sjc", "target": "aep.sjc.svc:8443", "weight": 60, "healthy": True},
            {"region": "iad", "target": "aep.iad.svc:8443", "weight": 40, "healthy": True},
        ],
        "lb_policy": "round_robin",
        "rate_limit": {"rps": 5000, "burst": 8000, "unit": "ip"},
        "auth": {"type": "oauth2+jwt", "audiences": ["aep"], "scopes": ["aep.read", "aep.write"]},
        "tls": {"mode": "passthrough", "min_version": "1.3", "mtls": True, "days_to_expiry": 120},
        "timeout_ms": 1800,
        "retries": 2,
        "circuit_breaker": {"consecutive_5xx": 10, "ejection_pct": 10},
        "status": "active",
        "owner": "experience-eng",
        "sli_p99_ms": 71,
        "error_rate": 0.09,
    },
    {
        "id": "rt-acrobat",
        "name": "acrobat-services",
        "host": "pdf.helixgate.dev",
        "path": "/v1/pdf/*",
        "methods": ["GET", "POST"],
        "upstreams": [
            {"region": "sjc", "target": "pdf.sjc.svc:8443", "weight": 80, "healthy": True},
            {"region": "fra", "target": "pdf.fra.svc:8443", "weight": 20, "healthy": True},
        ],
        "lb_policy": "weighted_round_robin",
        "rate_limit": {"rps": 1200, "burst": 2400, "unit": "ip+jwt_sub"},
        "auth": {"type": "jwt", "audiences": ["acrobat"], "scopes": ["pdf.read", "pdf.write"]},
        "tls": {"mode": "terminate", "min_version": "1.3", "mtls": False, "days_to_expiry": 18},
        "timeout_ms": 12000,
        "retries": 2,
        "circuit_breaker": {"consecutive_5xx": 6, "ejection_pct": 15},
        "status": "active",
        "owner": "document-cloud",
        "sli_p99_ms": 410,
        "error_rate": 0.34,
    },
    {
        "id": "rt-mcp-edge",
        "name": "mcp-edge",
        "host": "mcp.helixgate.dev",
        "path": "/mcp/*",
        "methods": ["POST"],
        "upstreams": [
            {"region": "sjc", "target": "mcp-broker.sjc.svc:7443", "weight": 100, "healthy": True},
        ],
        "lb_policy": "ring_hash",
        "rate_limit": {"rps": 80, "burst": 160, "unit": "agent_id"},
        "auth": {"type": "oauth2+mtls", "audiences": ["mcp"], "scopes": ["mcp.invoke"]},
        "tls": {"mode": "terminate", "min_version": "1.3", "mtls": True, "days_to_expiry": 9},
        "timeout_ms": 15000,
        "retries": 0,
        "circuit_breaker": {"consecutive_5xx": 3, "ejection_pct": 25},
        "status": "active",
        "owner": "dx-ai",
        "sli_p99_ms": 220,
        "error_rate": 1.4,
    },
    {
        "id": "rt-unprotected-lab",
        "name": "shadow-lab-api",
        "host": "lab.helixgate.dev",
        "path": "/v0/shadow/*",
        "methods": ["GET", "POST"],
        "upstreams": [
            {"region": "sjc", "target": "lab.sjc.svc:8080", "weight": 100, "healthy": True},
        ],
        "lb_policy": "round_robin",
        "rate_limit": None,
        "auth": {"type": "none", "audiences": [], "scopes": []},
        "tls": {"mode": "terminate", "min_version": "1.2", "mtls": False, "days_to_expiry": 2},
        "timeout_ms": 30000,
        "retries": 5,
        "circuit_breaker": {},
        "status": "draft",
        "owner": "dx-sandbox",
        "sli_p99_ms": 0,
        "error_rate": 0,
    },
]

MCP_SERVERS = [
    {
        "id": "mcp-docs-rag",
        "name": "docs-rag",
        "endpoint": "mcp://docs.helixgate.svc:7443",
        "tools": ["search_docs", "get_page", "cite"],
        "auth": "oauth2+mtls",
        "guardrails": ["no_pii_egress", "tool_allowlist", "max_tokens_per_min"],
        "quota": {"rpm": 120, "tokens_per_day": 2_000_000},
        "used_rpm": 44,
        "used_tokens": 610_400,
        "status": "healthy",
        "region": "sjc",
        "audience": "mcp",
    },
    {
        "id": "mcp-k8s-ops",
        "name": "k8s-ops",
        "endpoint": "mcp://k8s-ops.helixgate.svc:7443",
        "tools": ["get_pods", "describe_ingress", "rollout_status", "apply_patch"],
        "auth": "oauth2+mtls+jit",
        "guardrails": ["prod_write_requires_hitl", "namespace_allowlist", "no_secret_read"],
        "quota": {"rpm": 30, "tokens_per_day": 200_000},
        "used_rpm": 9,
        "used_tokens": 41_200,
        "status": "healthy",
        "region": "sjc",
        "audience": "mcp",
        "privileged_tools": ["apply_patch"],
    },
    {
        "id": "mcp-config-lint",
        "name": "config-lint",
        "endpoint": "mcp://lint.helixgate.svc:7443",
        "tools": ["lint_envoy", "lint_httpproxy", "lint_helm"],
        "auth": "mtls",
        "guardrails": ["tool_allowlist"],
        "quota": {"rpm": 200, "tokens_per_day": 500_000},
        "used_rpm": 71,
        "used_tokens": 88_100,
        "status": "healthy",
        "region": "iad",
        "audience": "mcp",
    },
    {
        "id": "mcp-incident",
        "name": "incident-bot",
        "endpoint": "mcp://incident.helixgate.svc:7443",
        "tools": ["summarize_logs", "propose_remediation", "open_change"],
        "auth": "oauth2+mtls",
        "guardrails": ["no_pii_egress", "prod_write_requires_hitl"],
        "quota": {"rpm": 40, "tokens_per_day": 800_000},
        "used_rpm": 38,
        "used_tokens": 790_000,
        "status": "throttled",
        "region": "sjc",
        "audience": "mcp",
        "privileged_tools": ["open_change"],
    },
]

POLICIES = [
    {
        "id": "pol-tls13",
        "name": "TLS 1.3 minimum",
        "applies_to": "all routes",
        "rule": "tls.min_version >= 1.3",
        "severity": "high",
    },
    {
        "id": "pol-authn",
        "name": "JWT or mTLS on every external route",
        "applies_to": "status=active",
        "rule": "auth.type in jwt|oauth2+jwt|oauth2+mtls",
        "severity": "high",
    },
    {
        "id": "pol-rl",
        "name": "Rate limit required",
        "applies_to": "all routes",
        "rule": "rate_limit.rps is set",
        "severity": "medium",
    },
    {
        "id": "pol-retry",
        "name": "Bounded retries",
        "applies_to": "all routes",
        "rule": "retries <= 3",
        "severity": "medium",
    },
    {
        "id": "pol-mcp-mtls",
        "name": "MCP servers require mTLS",
        "applies_to": "mcp mesh",
        "rule": "auth contains mtls",
        "severity": "high",
    },
    {
        "id": "pol-pii",
        "name": "No PII in MCP tool args or logs",
        "applies_to": "mcp mesh",
        "rule": "guardrails includes no_pii_egress",
        "severity": "critical",
    },
]

GITOPS_APPS = [
    {
        "name": "helixgate-gateway",
        "repo": "github.com/Ananyanagaraj11/helixgate",
        "path": "infra/helm/helixgate",
        "dest": "helixgate / sjc-prod-1",
        "sync": "Synced",
        "health": "Healthy",
        "revision": "main@a1c3e9",
        "auto_sync": True,
    },
    {
        "name": "helixgate-mcp-mesh",
        "repo": "github.com/Ananyanagaraj11/helixgate",
        "path": "infra/argocd",
        "dest": "helixgate / sjc-prod-1",
        "sync": "OutOfSync",
        "health": "Degraded",
        "revision": "main@a1c3e9 → helm-values drift",
        "auto_sync": False,
        "drift": "mcp-edge TLS days_to_expiry=9, desired >= 21",
    },
    {
        "name": "contour-ingress",
        "repo": "github.com/Ananyanagaraj11/helixgate",
        "path": "infra/contour",
        "dest": "ingress-nginx / all-regions",
        "sync": "Synced",
        "health": "Healthy",
        "revision": "main@88f2aa",
        "auto_sync": True,
    },
    {
        "name": "envoy-gateway",
        "repo": "github.com/Ananyanagaraj11/helixgate",
        "path": "infra/envoy",
        "dest": "gateway-system / multi-region",
        "sync": "Synced",
        "health": "Progressing",
        "revision": "main@c01b44",
        "auto_sync": True,
    },
]

LOG_SAMPLES = [
    {
        "id": "log-503-sjc",
        "title": "SJC Envoy 503 storm on /v2/creative",
        "body": (
            "ts=2026-09-04T12:04:11Z envoy cluster=cc-api.sjc.svc code=503 "
            "outlier_ejection=true consecutive_5xx=11 region=sjc route=rt-creative-cloud "
            "upstream_cx_overflow=true fra_health=unhealthy iad_health=ok"
        ),
    },
    {
        "id": "log-mcp-quota",
        "title": "MCP incident-bot quota exhaustion",
        "body": (
            "mcp server=incident-bot status=429 tokens_used=790000 tokens_limit=800000 "
            "rpm=38 rpm_limit=40 tool=summarize_logs agent=dx-copilot retries=14"
        ),
    },
    {
        "id": "log-argo-drift",
        "title": "Argo CD helixgate-mcp-mesh OutOfSync",
        "body": (
            "argocd app=helixgate-mcp-mesh sync=OutOfSync health=Degraded "
            "drift=tls.days_to_expiry desired=21 observed=9 path=infra/argocd"
        ),
    },
    {
        "id": "log-tls-expiry",
        "title": "mcp.helixgate.dev certificate expires in 9 days",
        "body": (
            "cert host=mcp.helixgate.dev not_after=2026-09-13 tls_min=1.3 mtls=true "
            "route=rt-mcp-edge days_to_expiry=9 policy=pol-tls13"
        ),
    },
    {
        "id": "log-jwt-aud",
        "title": "JWT audience mismatch 401s on firefly",
        "body": (
            "jwt iss=https://id.helixgate.dev aud=cc-api expected=firefly "
            "route=rt-firefly status=401 count=1842 window=5m"
        ),
    },
    {
        "id": "log-shadow-open",
        "title": "shadow-lab-api has no auth and no rate limit",
        "body": (
            "route=rt-unprotected-lab auth=none rate_limit=null tls_min=1.2 retries=5 "
            "status=draft host=lab.helixgate.dev path=/v0/shadow/*"
        ),
    },
]


def clone_catalog() -> dict:
    return {
        "regions": deepcopy(REGIONS),
        "routes": deepcopy(ROUTES),
        "mcp": deepcopy(MCP_SERVERS),
        "policies": deepcopy(POLICIES),
        "gitops": deepcopy(GITOPS_APPS),
        "logs": deepcopy(LOG_SAMPLES),
    }
