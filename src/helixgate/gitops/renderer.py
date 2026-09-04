from __future__ import annotations


def lint_route(route: dict) -> list[dict]:
    findings: list[dict] = []
    tls = route.get("tls") or {}
    auth = route.get("auth") or {}
    if str(tls.get("min_version") or "") in {"", "1.0", "1.1", "1.2"}:
        findings.append(
            {
                "code": "TLS_MIN",
                "severity": "high",
                "message": f"{route.get('name')}: TLS min {tls.get('min_version')} fails pol-tls13 (need 1.3).",
            }
        )
    if int(tls.get("days_to_expiry") or 0) < 21:
        findings.append(
            {
                "code": "TLS_EXPIRY",
                "severity": "high",
                "message": f"{route.get('name')}: certificate remaining life is {tls.get('days_to_expiry')} days (need >= 21).",
            }
        )
    if route.get("status") == "active" and auth.get("type") in {None, "", "none"}:
        findings.append(
            {
                "code": "AUTH_MISSING",
                "severity": "critical",
                "message": f"{route.get('name')}: active route has no JWT/OAuth/mTLS.",
            }
        )
    if not route.get("rate_limit"):
        findings.append(
            {
                "code": "RATE_LIMIT",
                "severity": "medium",
                "message": f"{route.get('name')}: rate_limit is required before GitOps promote.",
            }
        )
    if int(route.get("retries") or 0) > 3:
        findings.append(
            {
                "code": "RETRIES",
                "severity": "medium",
                "message": f"{route.get('name')}: retries={route.get('retries')} exceeds bound of 3.",
            }
        )
    if "mcp" in (route.get("name") or "") and not tls.get("mtls"):
        findings.append(
            {
                "code": "MCP_MTLS",
                "severity": "critical",
                "message": f"{route.get('name')}: MCP edge requires mTLS.",
            }
        )
    return findings


def lint_mcp(server: dict) -> list[dict]:
    findings: list[dict] = []
    if "mtls" not in (server.get("auth") or ""):
        findings.append(
            {
                "code": "MCP_AUTH",
                "severity": "high",
                "message": f"{server.get('name')}: MCP auth must include mTLS.",
            }
        )
    if "no_pii_egress" not in (server.get("guardrails") or []) and server.get("name") != "config-lint":
        findings.append(
            {
                "code": "PII",
                "severity": "high",
                "message": f"{server.get('name')}: missing no_pii_egress guardrail.",
            }
        )
    quota = server.get("quota") or {}
    if int(server.get("used_tokens") or 0) > 0.9 * int(quota.get("tokens_per_day") or 1):
        findings.append(
            {
                "code": "QUOTA",
                "severity": "medium",
                "message": f"{server.get('name')}: token usage > 90% of daily budget.",
            }
        )
    return findings


def render_envoy(route: dict) -> str:
    clusters = []
    for u in route.get("upstreams", []):
        clusters.append(
            f"""  - name: {route['id']}-{u['region']}
    type: STRICT_DNS
    lb_policy: LEAST_REQUEST
    load_assignment:
      cluster_name: {route['id']}-{u['region']}
      endpoints:
        - lb_endpoints:
            - endpoint:
                address:
                  socket_address: {{ address: {u['target'].split(':')[0]}, port_value: {u['target'].split(':')[-1]} }}
            load_balancing_weight: {u.get('weight', 1)}"""
        )
    rl = route.get("rate_limit") or {"rps": 1, "burst": 1, "unit": "ip"}
    weighted = "\n".join(
        f"                                - name: {route['id']}-{u['region']}\n                                  weight: {u.get('weight', 1)}"
        for u in route.get("upstreams", [])
    )
    return f"""static_resources:
  listeners:
    - name: {route['id']}
      address:
        socket_address: {{ address: 0.0.0.0, port_value: 8443 }}
      filter_chains:
        - transport_socket:
            name: envoy.transport_sockets.tls
            typed_config:
              min_protocol_version: TLSv1_3
              require_client_certificate: {str(bool((route.get('tls') or {}).get('mtls'))).lower()}
          filters:
            - name: envoy.filters.network.http_connection_manager
              typed_config:
                stat_prefix: {route['id']}
                route_config:
                  virtual_hosts:
                    - name: {route['name']}
                      domains: ["{route['host']}"]
                      routes:
                        - match: {{ prefix: "{route['path'].replace('*', '')}" }}
                          route:
                            weighted_clusters:
                              clusters:
{weighted}
                            timeout: {int(route.get('timeout_ms') or 2000)}ms
                            retry_policy: {{ retry_on: "5xx", num_retries: {int(route.get('retries') or 0)} }}
                http_filters:
                  - name: envoy.filters.http.jwt_authn
                  - name: envoy.filters.http.local_ratelimit
                    typed_config:
                      token_bucket: {{ max_tokens: {rl['burst']}, tokens_per_fill: {rl['rps']}, fill_interval: 1s }}
                      filter_enabled: {{ runtime_key: rl, default_value: {{ numerator: 100 }} }}
                  - name: envoy.filters.http.router
  clusters:
{chr(10).join(clusters)}
"""


def render_httpproxy(route: dict) -> str:
    services = "\n".join(
        f"""        - name: {u['target'].split(':')[0]}
          port: {u['target'].split(':')[-1]}
          weight: {u.get('weight', 1)}"""
        for u in route.get("upstreams", [])
    )
    return f"""apiVersion: projectcontour.io/v1
kind: HTTPProxy
metadata:
  name: {route['id']}
  namespace: helixgate
spec:
  virtualhost:
    fqdn: {route['host']}
    tls:
      secretName: {route['id']}-tls
      minimumProtocolVersion: "1.3"
  routes:
    - conditions:
        - prefix: "{route['path'].replace('*', '')}"
      loadBalancerPolicy:
        strategy: WeightedLeastRequest
      services:
{services}
      rateLimitPolicy:
        local:
          requests: {(route.get('rate_limit') or {}).get('rps', 1)}
          unit: second
          burst: {(route.get('rate_limit') or {}).get('burst', 1)}
"""


def render_helm_values(route: dict) -> str:
    regions = "\n".join(
        f"    - id: {u['region']}\n      target: {u['target']}\n      weight: {u.get('weight', 1)}\n      healthy: {u.get('healthy', True)}"
        for u in route.get("upstreams", [])
    )
    return f"""gateway:
  name: {route['name']}
  replicaCount: 2
  hpa:
    min: 2
    max: 8
  host: {route['host']}
  path: {route['path']}
  tls:
    minVersion: "{(route.get('tls') or {}).get('min_version', '1.3')}"
    mtls: {(route.get('tls') or {}).get('mtls', True)}
    daysToExpiry: {(route.get('tls') or {}).get('days_to_expiry', 90)}
  auth:
    type: {(route.get('auth') or {}).get('type')}
    audiences: {(route.get('auth') or {}).get('audiences', [])}
  rateLimit:
    rps: {(route.get('rate_limit') or {}).get('rps', 0)}
    burst: {(route.get('rate_limit') or {}).get('burst', 0)}
    unit: {(route.get('rate_limit') or {}).get('unit', 'ip')}
  regions:
{regions}
"""


def render_argo_app(route: dict) -> str:
    return f"""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {route['id']}
  namespace: argocd
spec:
  project: helixgate
  source:
    repoURL: https://github.com/Ananyanagaraj11/helixgate
    targetRevision: main
    path: infra/helm/helixgate
    helm:
      valueFiles:
        - values.yaml
      parameters:
        - name: gateway.name
          value: {route['name']}
        - name: gateway.host
          value: {route['host']}
  destination:
    server: https://kubernetes.default.svc
    namespace: helixgate
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
"""


def manifests_for(route: dict) -> dict[str, str]:
    return {
        "envoy": render_envoy(route),
        "httpproxy": render_httpproxy(route),
        "helm": render_helm_values(route),
        "argocd": render_argo_app(route),
    }


def nginx_snippet(route: dict) -> str:
    return f"""# NGINX ingress equivalent for {route['name']}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {route['id']}
  annotations:
    nginx.ingress.kubernetes.io/limit-rps: "{(route.get('rate_limit') or {}).get('rps', 1)}"
    nginx.ingress.kubernetes.io/backend-protocol: "HTTPS"
    nginx.ingress.kubernetes.io/affinity: "cookie"
spec:
  tls:
    - hosts: ["{route['host']}"]
      secretName: {route['id']}-tls
  rules:
    - host: {route['host']}
      http:
        paths:
          - path: {route['path'].replace('*', '')}
            pathType: Prefix
            backend:
              service:
                name: {route['name']}
                port:
                  number: 8443
"""
