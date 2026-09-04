from __future__ import annotations

DOCUMENTS = [
    {
        "doc_id": "SOP-GW-014",
        "title": "Envoy 503 outlier ejection and regional drain",
        "category": "gateway",
        "text": (
            "If Envoy reports consecutive_5xx >= circuit_breaker threshold on a region, mark the upstream unhealthy "
            "and shift weight to healthy regions. Do not send new traffic to FRA if fra_health=unhealthy. "
            "Drain SJC only when IAD can absorb the load (capacity < 0.75). Remediation: set sjc weight to 0, "
            "iad weight to 100, keep FRA ejected until health checks pass for 10 minutes. HITL required before "
            "changing production weights. Re-enable SJC with canary weight 10 after error_rate < 0.5%."
        ),
    },
    {
        "doc_id": "SOP-MCP-007",
        "title": "MCP quota exhaustion and usage controls",
        "category": "mcp",
        "text": (
            "When an MCP server approaches tokens_per_day or rpm limits, shed non-critical agents first. "
            "incident-bot retries must stop at 3. Raise rpm only with HITL. Guardrails: no_pii_egress stays on. "
            "Remediation: set server status=throttled, drop retry storm, optionally raise tokens_per_day by 20% "
            "for 1 hour after approval. Usage controls are per agent_id, not per IP."
        ),
    },
    {
        "doc_id": "SOP-GITOPS-003",
        "title": "Argo CD OutOfSync and Helm drift",
        "category": "gitops",
        "text": (
            "OutOfSync on helixgate-mcp-mesh means live TLS or quota values drifted from Helm. "
            "Do not kubectl apply. Render the Helm chart, open a GitOps diff, and sync via Argo CD after HITL. "
            "Desired mcp-edge certificate remaining life is >= 21 days. If days_to_expiry < 21, rotate the cert "
            "in Helm values and auto-sync. Custom resources (HTTPProxy, EnvoyFilter) must stay in git."
        ),
    },
    {
        "doc_id": "SOP-TLS-021",
        "title": "TLS rotation for gateway and MCP hosts",
        "category": "security",
        "text": (
            "Certificates under 21 days must rotate. Minimum TLS 1.3. MCP and AI inference routes require mTLS. "
            "DNS remains on api/ai/mcp/pdf.helixgate.dev. After rotate, bump days_to_expiry to 90 and force "
            "Contour HTTPProxy and Envoy listener reload. HTTP/1.2-only routes fail policy pol-tls13."
        ),
    },
    {
        "doc_id": "SOP-JWT-009",
        "title": "JWT audience and OAuth token storms",
        "category": "security",
        "text": (
            "401 storms with aud mismatch mean the token was issued for another route. Firefly requires aud=firefly. "
            "Creative Cloud requires aud=cc-api. Do not disable JWT. Issue a correctly scoped token from the "
            "identity service. Rate-limit 401s per ip+sub to protect the gateway. OAuth client credentials still "
            "map to JWT with iss=https://id.helixgate.dev."
        ),
    },
    {
        "doc_id": "SOP-SEC-011",
        "title": "Unsigned lab routes must not reach production DNS",
        "category": "security",
        "text": (
            "shadow-lab-api has auth=none, no rate limit, TLS 1.2, retries=5. It must stay status=draft and must "
            "not receive a public DNS record. Before promotion: JWT, rate_limit.rps <= 50, tls.min_version=1.3, "
            "retries <= 2, and a Helm/Argo application in git. Config validation must fail the route until then."
        ),
    },
    {
        "doc_id": "SOP-RL-002",
        "title": "Rate limiting and load shedding",
        "category": "gateway",
        "text": (
            "Every active route needs a token bucket. Unit is ip, jwt_sub, or agent_id. Burst is 2x rps. "
            "On 429, return Retry-After and do not retry MCP tools. Load balancer policies: weighted_least_request "
            "for user APIs, ewma for inference, ring_hash for MCP session affinity. Never remove rate limits to "
            "clear an incident."
        ),
    },
    {
        "doc_id": "SOP-DNS-004",
        "title": "DNS failover across SJC IAD FRA",
        "category": "networking",
        "text": (
            "Primary DNS geo is SJC. If SJC Envoy health < 80%, drop TTL to 30s and shift DNS weight to IAD. "
            "FRA is EU pin, not a global failover target while degraded. TLS and HTTPProxy hosts must match DNS. "
            "Service-to-service stays on cluster local DNS (*.svc) with mTLS. Do not flatten MCP endpoints to public DNS."
        ),
    },
]


def chunks() -> list[dict]:
    out: list[dict] = []
    for doc in DOCUMENTS:
        out.append(
            {
                "chunk_id": f"{doc['doc_id']}-c0",
                "doc_id": doc["doc_id"],
                "title": doc["title"],
                "category": doc["category"],
                "text": doc["text"],
            }
        )
    return out
