from helixgate.plane import ControlPlane


def test_hybrid_retrieval_ranks_gateway_runbook():
    plane = ControlPlane()
    hits = plane.index.search("Envoy 503 outlier ejection sjc creative", k=3)
    assert hits
    assert hits[0].doc_id == "SOP-GW-014"


def test_jwt_and_rate_limit():
    plane = ControlPlane()
    denied = plane.engine.invoke("rt-creative-cloud", "anon", authorized=False)
    assert denied["status"] == 401
    statuses = [plane.engine.invoke("rt-creative-cloud", "dx-engineer", True)["status"] for _ in range(16)]
    assert 200 in statuses
    assert 429 in statuses


def test_load_balancer_skips_unhealthy():
    plane = ControlPlane()
    regions = {plane.engine.invoke("rt-creative-cloud", "dx", True).get("region") for _ in range(20)}
    regions.discard(None)
    assert "fra" not in regions
    assert regions <= {"sjc", "iad"}


def test_mcp_guardrails():
    plane = ControlPlane()
    pii = plane.mcp.invoke("mcp-docs-rag", "search_docs", "ssn 123-45-6789", True)
    assert pii["status"] == 451
    hitl = plane.mcp.invoke("mcp-k8s-ops", "apply_patch", "scale envoy", True)
    assert hitl["status"] == 423
    ok = plane.mcp.invoke("mcp-docs-rag", "search_docs", "rate limit unit", True)
    assert ok["status"] == 200


def test_lab_route_fails_policy():
    plane = ControlPlane()
    findings = plane.validate_all()["routes"]
    codes = {f["code"] for f in findings}
    assert "AUTH_MISSING" in codes or "TLS_MIN" in codes
    assert "RATE_LIMIT" in codes


def test_gitops_manifests_include_host():
    plane = ControlPlane()
    docs = plane.manifests("rt-firefly")
    assert "ai.helixgate.dev" in docs["envoy"]
    assert "HTTPProxy" in docs["httpproxy"]
    assert "argoproj.io" in docs["argocd"]
    assert "limit-rps" in docs["nginx"]
    assert "firefly-inference" in docs["helm"]


def test_aiops_hitl_drains_sjc():
    from helixgate.agents.ops import OpsGraph

    plane = ControlPlane()
    graph = OpsGraph(plane.index, plane)
    run = graph.run("SJC Envoy 503 storm on /v2/creative, FRA already unhealthy")
    assert run["grounded"] is True
    assert run["hitl"]
    review = plane.resolve_hitl(run["hitl"], True, "ananya", "apply drain")
    assert review["status"] == "approved"
    route = plane.engine.get("rt-creative-cloud")
    sjc = next(u for u in route["upstreams"] if u["region"] == "sjc")
    iad = next(u for u in route["upstreams"] if u["region"] == "iad")
    assert sjc["healthy"] is False
    assert iad["weight"] == 100


def test_self_service_registers_gitops_app():
    plane = ControlPlane()
    route = plane.register_route({"name": "billing-api", "host": "billing.helixgate.dev"})
    assert route["tls"]["min_version"] == "1.3"
    assert route["auth"]["type"] == "jwt"
    assert any(a["name"] == "billing-api" for a in plane.gitops)
