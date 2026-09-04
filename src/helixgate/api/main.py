from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from helixgate import __version__
from helixgate.agents.ops import OpsGraph
from helixgate.observability.metrics import (
    AIOPS_RUNS,
    GATEWAY_REQUESTS,
    HITL,
    MCP_REQUESTS,
    REGION_CAP,
    ROUTE_ERROR,
    metrics_response,
)
from helixgate.plane import ControlPlane
from helixgate.security.identity import authorize_route, issue_token

ROOT = Path(__file__).resolve().parents[3]
DASHBOARD = ROOT / "dashboard"

plane = ControlPlane()
ops = OpsGraph(plane.index, plane)

for region in plane.regions:
    REGION_CAP.labels(region=region["id"]).set(region["capacity"])
for route in plane.engine.list_routes():
    ROUTE_ERROR.labels(route=route["name"]).set(float(route.get("error_rate") or 0))

app = FastAPI(
    title="HelixGate",
    description="AI-native API & MCP gateway control plane — routing, identity, GitOps, guardrails, AI ops.",
    version=__version__,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if DASHBOARD.exists():
    app.mount("/assets", StaticFiles(directory=DASHBOARD), name="assets")


class InvokeBody(BaseModel):
    route_id: str
    token: str | None = None


class TokenBody(BaseModel):
    subject: str = "dx-engineer"
    audience: str = "cc-api"
    scopes: list[str] = Field(default_factory=lambda: ["creative.read"])


class McpBody(BaseModel):
    server_id: str
    tool: str
    argument: str = ""
    token: str | None = None


class AnalyzeBody(BaseModel):
    query: str = Field(min_length=8, max_length=2000)


class HitlBody(BaseModel):
    reviewer: str = "human"
    feedback: str = ""


class RouteBody(BaseModel):
    name: str
    host: str | None = None
    path: str = "/v1/*"
    audience: str | None = None
    owner: str = "self-service"


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return authorization


@app.get("/")
async def index() -> FileResponse:
    page = DASHBOARD / "index.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="Dashboard missing")
    return FileResponse(page)


@app.get("/health")
async def health() -> dict:
    o = plane.overview()
    return {
        "status": "ok",
        "service": "helixgate",
        "version": __version__,
        "regions": [r["id"] for r in plane.regions],
        "routes": o["routes"],
        "mcp": o["mcp_servers"],
    }


@app.get("/metrics")
async def metrics() -> Response:
    body, content_type = metrics_response()
    return Response(content=body, media_type=content_type)


@app.get("/api/overview")
async def overview() -> dict:
    return plane.overview()


@app.get("/api/regions")
async def regions() -> list[dict]:
    return plane.regions


@app.get("/api/routes")
async def routes() -> list[dict]:
    return plane.engine.list_routes()


@app.post("/api/routes")
async def create_route(body: RouteBody) -> dict:
    return plane.register_route(body.model_dump())


@app.get("/api/policies")
async def policies() -> dict:
    return {"policies": plane.policies, "findings": plane.validate_all()}


@app.get("/api/mcp/servers")
async def mcp_servers() -> list[dict]:
    return plane.mcp.list_servers()


@app.get("/api/gitops")
async def gitops() -> list[dict]:
    return plane.gitops


@app.get("/api/gitops/manifests/{route_id}")
async def gitops_manifests(route_id: str) -> dict:
    docs = plane.manifests(route_id)
    if not docs:
        raise HTTPException(status_code=404, detail="route not found")
    return docs


@app.get("/api/logs")
async def logs() -> list[dict]:
    return plane.logs


@app.get("/api/knowledge")
async def knowledge() -> list[dict]:
    return [{"doc_id": d["doc_id"], "title": d["title"], "category": d["category"], "excerpt": d["text"][:220]} for d in plane.documents]


@app.get("/api/audit")
async def audit() -> list[dict]:
    return plane.events[:50]


@app.post("/api/gateway/token")
async def token(body: TokenBody) -> dict:
    jwt_token = issue_token(body.subject, body.audience, body.scopes)
    return {"token": jwt_token, "issuer": "https://id.helixgate.dev", "audience": body.audience, "subject": body.subject}


@app.post("/api/gateway/invoke")
async def invoke(body: InvokeBody, authorization: str | None = Header(default=None)) -> dict:
    route = plane.engine.get(body.route_id)
    if not route:
        raise HTTPException(status_code=404, detail="route not found")
    token = body.token or _bearer(authorization)
    ok, identity, _claims = authorize_route(token, route)
    result = plane.engine.invoke(body.route_id, identity, ok)
    GATEWAY_REQUESTS.labels(route=route["name"], status=str(result["status"])).inc()
    return result


@app.post("/api/mcp/invoke")
async def mcp_invoke(body: McpBody, authorization: str | None = Header(default=None)) -> dict:
    server = plane.mcp.get(body.server_id)
    if not server:
        raise HTTPException(status_code=404, detail="mcp server not found")
    fake_route = {"auth": {"type": "jwt", "audiences": [server.get("audience") or "mcp"]}}
    token = body.token or _bearer(authorization)
    ok, _identity, _claims = authorize_route(token, fake_route)
    result = plane.mcp.invoke(body.server_id, body.tool, body.argument, ok)
    MCP_REQUESTS.labels(server=server["name"], status=str(result["status"])).inc()
    return result


@app.post("/api/aiops/analyze")
async def analyze(body: AnalyzeBody) -> dict:
    result = ops.run(body.query.strip())
    AIOPS_RUNS.labels(grounded=str(result["grounded"]).lower()).inc()
    return result


@app.get("/api/aiops/runs")
async def runs() -> list[dict]:
    return plane.runs[:40]


@app.get("/api/hitl")
async def hitl() -> list[dict]:
    return plane.hitl[:40]


@app.post("/api/hitl/{review_id}/approve")
async def hitl_approve(review_id: str, body: HitlBody) -> dict:
    try:
        review = plane.resolve_hitl(review_id, True, body.reviewer, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    HITL.labels(decision="approved").inc()
    return review


@app.post("/api/hitl/{review_id}/reject")
async def hitl_reject(review_id: str, body: HitlBody) -> dict:
    try:
        review = plane.resolve_hitl(review_id, False, body.reviewer, body.feedback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    HITL.labels(decision="rejected").inc()
    return review
