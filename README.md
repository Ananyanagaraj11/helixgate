# HelixGate · DX control plane

> Route every API and AI agent through one guarded control plane — then let AI ops propose the fix, not invent it.

A company-style **API + MCP gateway** for developer experience teams: Kubernetes-shaped GitOps, real JWT and rate limits, MCP guardrails, and human-gated remediation.

<p align="center">
  <a href="https://helixgate.onrender.com"><strong>▶ Live demo</strong></a>&nbsp;·&nbsp;
  <a href="https://helixgate.onrender.com/docs"><strong>API / Swagger</strong></a>&nbsp;·&nbsp;
  <a href="docs/ARCHITECTURE.md"><strong>Architecture</strong></a>
</p>

[![CI](https://github.com/Ananyanagaraj11/helixgate/actions/workflows/ci.yml/badge.svg)](https://github.com/Ananyanagaraj11/helixgate/actions)
![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-HPA%202–8-326CE5?logo=kubernetes&logoColor=white)
![Envoy](https://img.shields.io/badge/Envoy-gateway-AC6199)
![Helm](https://img.shields.io/badge/Helm-GitOps-0F1689?logo=helm&logoColor=white)
![Argo CD](https://img.shields.io/badge/Argo%20CD-Application%20CR-EF7B4D?logo=argo&logoColor=white)

---

## What it is

HelixGate is the missing control plane between **product APIs**, **AI inference**, and **MCP servers**. Operators see multi-region health. Developers self-publish a route. AI ops reads gateway logs, lints Envoy/Helm against policy, and waits for a human before it touches production weights, TLS, or quotas.

This is not a chatbot glued onto YAML. The demo gateway actually returns **401 / 429 / 451 / 423**.

## Recruiter table

| # | What to notice | Where |
|---|----------------|-------|
| 1 | **Live API gateway** — JWT audience checks, token-bucket rate limits, weighted LB that ejects unhealthy regions | Overview → *Burst 12 requests* |
| 2 | **MCP mesh** — tool allowlists, OAuth/mTLS, PII guardrail (451), usage quotas, HITL on privileged writes (423) | MCP mesh · *MCP PII probe* |
| 3 | **Config validation** — TLS 1.3, auth required, bounded retries, cert floor, MCP mTLS | Identity · TLS |
| 4 | **GitOps artifacts** — Envoy, Contour `HTTPProxy`, Helm values, Argo CD `Application`, NGINX Ingress | GitOps tab |
| 5 | **AI ops graph** — Sentinel (hybrid RAG) → Pathfinder → Validator → Steward. No citation, no diagnosis. | AI ops |
| 6 | **Human gate** — approve a drain / TLS rotate / quota bump and watch live catalog + Argo sync flip | HITL queue |
| 7 | **Self-service** — register an API; HelixGate mints JWT, rate limit, TLS 1.3, and an Argo app | Self-service |
| 8 | **Kubernetes, not a Dockerfile only** — Deployment ×2, Service, HPA 2–8, Ingress, Helm, Argo CD | `infra/` |

**Stack:** FastAPI · Python · JWT/OAuth · Envoy/Contour/NGINX configs · Helm · Argo CD · Kubernetes · hybrid RAG · MCP guardrails · Prometheus · Docker · GitHub Actions

## 90-second live walkthrough

Open the **[live demo](https://helixgate.onrender.com)** (Render free tier may take ~40s to wake).

1. **Overview** → *Issue JWT* → *Burst 12 requests*. You should see `200` then `429`.
2. Click **MCP PII probe**. Guardrail returns `451`.
3. **AI ops** → sample *SJC Envoy 503 storm…* → watch Sentinel → Pathfinder → Validator → Steward.
4. **Approve apply**. SJC weight goes to 0, IAD takes the traffic.
5. **GitOps** → pick `firefly-inference` → flip Envoy / HTTPProxy / Helm / Argo CD / NGINX.

Other samples: MCP quota, Argo drift, TLS expiry, JWT audience mismatch, unsigned lab route.

## Quick start

```bash
git clone https://github.com/Ananyanagaraj11/helixgate
cd helixgate
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH = "src"
uvicorn helixgate.api.main:app --reload --port 8080
```

Open [http://localhost:8080](http://localhost:8080)

```bash
docker compose up --build
pytest tests -q
ruff check src tests
```

## Repo map

```
dashboard/                 Control plane UI
src/helixgate/
  api/main.py              FastAPI
  gateway/engine.py        Routing, LB, rate limit
  mcp/mesh.py              Guardrails + usage
  security/identity.py     JWT issue / verify
  agents/ops.py            4-agent AI ops + HITL
  rag/                     BM25 + TF-IDF + RRF
  gitops/renderer.py       Envoy / HTTPProxy / Helm / Argo
infra/kubernetes           Deployment, HPA, Ingress
infra/helm/helixgate       Chart
infra/argocd               Application CRs
infra/envoy · contour      Edge configs
```

## Interview script

> HelixGate is a DX control plane I built for API and AI traffic. The edge enforces JWT audiences, rate limits, and weighted multi-region load balancing — FRA is already ejected in the demo. MCP servers sit behind the same plane with tool allowlists, PII guardrails, and usage quotas; privileged Kubernetes patches stay 423 until a human approves. Recurring incidents go through hybrid RAG plus a validator that lints live config against policy. Steward can drain a region or rotate TLS, but only GitOps-shaped apply after HITL. The repo ships Helm, Argo CD, Envoy, and Contour HTTPProxy so the console is not a mock.

Then pause: *Want the gateway engine, the MCP guardrails, or the AI ops graph?*

## Author

**Ananya Naga Raj** — Software Development Engineer  
[GitHub](https://github.com/Ananyanagaraj11) · [LinkedIn](https://www.linkedin.com/in/ananyanagaraj/)

MIT License
