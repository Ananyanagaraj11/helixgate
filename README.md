# HelixGate

<p align="center">
  <img src="docs/helix.svg" width="72" alt="HelixGate mark" />
</p>

<p align="center">
  <strong>The door every API and AI agent has to walk through.</strong><br/>
  <em>San Jose primary · Ashburn failover · Frankfurt EU pin</em>
</p>

<p align="center">
  <a href="https://helixgate.onrender.com"><strong>▶ Live control plane</strong></a>
  &nbsp;·&nbsp;
  <a href="https://helixgate.onrender.com/docs"><strong>Swagger</strong></a>
  &nbsp;·&nbsp;
  <a href="docs/ARCHITECTURE.md"><strong>Architecture notes</strong></a>
</p>

<p align="center">
  <a href="https://github.com/Ananyanagaraj11/helixgate/actions"><img src="https://github.com/Ananyanagaraj11/helixgate/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <img src="https://img.shields.io/badge/edge-JWT%20·%20429%20·%20451%20·%20423-3ee6c8" alt="live status codes" />
  <img src="https://img.shields.io/badge/regions-SJC%20%2B%20IAD%20%2B%20FRA-8d7bff" alt="regions" />
  <img src="https://img.shields.io/badge/GitOps-Helm%20%2B%20Argo%20CD-EF7B4D" alt="GitOps" />
</p>

---

A creative studio ships a thousand APIs. An agent mesh ships a thousand more. Someone still has to decide **who gets through, to which region, under which quota, and who is allowed to change the gate itself.**

HelixGate is that door — a Developer Experience control plane for **API traffic and MCP servers** on a Kubernetes-shaped edge. It is not a chatbot taped to YAML. Burst the demo: you will get a real JWT, a real `429`, a PII `451`, and a privileged MCP write that stays `423` until a human approves.

```
        APIs                         agents
          \                           /
           \     TLS 1.3 · JWT       /
            \    rate limit · mTLS  /
             >>>>>>>  HELIX  <<<<<<<
            /    Envoy · Contour    \
           /     MCP guardrails      \
          /                           \
     SJC primary                  GitOps + HITL
```

**Why San Jose?** That is where a Bay Area DX team would actually run the primary. `sjc-prod-1` is home. Ashburn is the failover. Frankfurt is an EU pin — not a global dump — and in the demo it is already *degraded*, so you can watch the helix unwind traffic away from a sick region.

---

## Architecture

One plane. Three jobs: **admit**, **observe**, **remediate**.

```mermaid
flowchart TB
  subgraph clients["Who is knocking"]
    DEV["Product APIs<br/>Creative Cloud · Acrobat · Experience"]
    AGENT["AI agents<br/>inference · copilot · MCP clients"]
  end

  subgraph edge["HelixGate edge"]
    ID["Identity<br/>JWT · OAuth · mTLS"]
    RL["Token bucket<br/>ip · jwt_sub · agent_id"]
    LB["Weighted LB<br/>eject unhealthy"]
    POL["Policy lint<br/>TLS 1.3 · retries · cert floor"]
    ID --> RL --> LB
    POL -.-> ID
  end

  subgraph fabric["Traffic fabric"]
    SJC["SJC · San Jose<br/>primary · p50 12ms"]
    IAD["IAD · Ashburn<br/>failover"]
    FRA["FRA · Frankfurt<br/>EU pin · degraded"]
  end

  subgraph south["What sits behind the door"]
    REST["REST upstreams<br/>cc-api · firefly · aep · pdf"]
    MCP["MCP mesh<br/>docs-rag · k8s-ops · lint · incident-bot"]
  end

  subgraph plane["Control plane"]
    UI["DX console"]
    API["FastAPI · /metrics · /health"]
    AI["AI ops<br/>Sentinel → Pathfinder → Validator → Steward"]
    GIT["GitOps renderer<br/>Envoy · HTTPProxy · Helm · Argo CD"]
    HITL["Human gate"]
    UI --- API
    API --- AI
    AI --> HITL
    HITL --> GIT
  end

  DEV --> ID
  AGENT --> ID
  LB --> SJC
  LB --> IAD
  LB -.-> FRA
  SJC --> REST
  SJC --> MCP
  IAD --> REST
  GIT --> K8S["Kubernetes<br/>HPA 2–8"]
```

### A request walking the helix

```mermaid
sequenceDiagram
  autonumber
  participant C as Client / agent
  participant G as Gateway engine
  participant I as JWT issuer
  participant U as Upstream (SJC / IAD)
  participant M as MCP server

  C->>I: Issue token (aud must match the route)
  I-->>C: JWT
  C->>G: Invoke route
  G->>G: Verify audience + TLS policy
  alt wrong aud or no token
    G-->>C: 401 unauthorized
  else bucket empty
    G-->>C: 429 rate_limited
  else no healthy region
    G-->>C: 503 no_healthy_upstream
  else admitted
    G->>U: Weighted pick (FRA already ejected)
    U-->>C: 200
  end
  C->>M: MCP tool call
  alt PII / injection
    M-->>C: 451 guardrail_pii
  else privileged write
    M-->>C: 423 hitl_required
  else quota
    M-->>C: 429 usage_quota
  else allowlisted tool
    M-->>C: 200 cited result
  end
```

### When the door starts 503-ing

Recurring ops work becomes a four-agent graph. Steward drafts the change. **Git stays the source of truth. A human still turns the key.**

```mermaid
flowchart LR
  LOG["Envoy logs<br/>SJC 503 storm"] --> S["Sentinel<br/>BM25 + TF-IDF + RRF"]
  S --> P["Pathfinder<br/>cite or abstain"]
  P --> V["Validator<br/>lint live routes + MCP"]
  V --> ST["Steward<br/>drain / rotate / quota"]
  ST --> H{"HITL"}
  H -->|Approve| LIVE["Mutate catalog<br/>SJC weight → 0<br/>IAD weight → 100"]
  H -->|Reject| AUDIT["Audit only"]
  LIVE --> ARGO["Argo CD sync<br/>Helm values"]
```

San Jose carries ~70% of creative-cloud weight until it is sick. Then the runbook is not “hope FRA absorbs it.” FRA is the EU pin and it is already unhealthy. The helix shifts **SJC → IAD**, the same way a San Jose on-call would.

---

## What the console proves

| Open this | You should feel | Live signal |
|-----------|-----------------|-------------|
| Overview → Burst 12 | The edge is real | `200` then `429` |
| MCP PII probe | Agents do not get a free pass | `451 no_pii_egress` |
| `k8s-ops` / `apply_patch` | Production writes are not a toy | `423` until HITL |
| AI ops → 503 sample | Diagnosis is grounded or it abstains | Citations + Steward waiting |
| Approve apply | Remediation is reversible and gated | SJC drained, IAD takes traffic |
| GitOps tab | Self-service is GitOps-shaped | Envoy · HTTPProxy · Helm · Argo · NGINX |
| Identity · TLS | Policy is code | Lab route fails TLS 1.3 / auth / rate limit |

**Stack:** FastAPI · Python · JWT · Envoy / Contour / NGINX · Helm · Argo CD · Kubernetes · hybrid RAG · MCP guardrails · Prometheus · Docker · GitHub Actions

---

## 90 seconds on the live plane

[helixgate.onrender.com](https://helixgate.onrender.com) — free Render may sleep ~40s.

1. Issue a JWT for `creative-cloud-api`. Burst 12. Watch the bucket trip.
2. MCP PII probe — the mesh should refuse.
3. AI ops → *SJC Envoy 503 storm on /v2/creative, FRA already unhealthy*.
4. Approve the drain. San Jose goes quiet. Ashburn carries the helix.
5. GitOps → `firefly-inference` → flip the five manifests.

Other storms on the board: MCP quota, Argo drift, TLS expiry, JWT audience mismatch, unsigned lab route.

---

## Run it locally

```bash
git clone https://github.com/Ananyanagaraj11/helixgate
cd helixgate
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
$env:PYTHONPATH = "src"
uvicorn helixgate.api.main:app --reload --port 8080
```

[http://localhost:8080](http://localhost:8080)

```bash
docker compose up --build
pytest tests -q
ruff check src tests
```

```
dashboard/                 DX console
src/helixgate/
  gateway/engine.py        Admit: JWT, LB, token bucket
  mcp/mesh.py              Guard: allowlist, PII, quota, HITL
  agents/ops.py            Remediate: 4-agent graph
  rag/                     BM25 + vectors + RRF
  gitops/renderer.py       Envoy / HTTPProxy / Helm / Argo
infra/                     Kubernetes, Helm, Argo CD, Envoy, Contour
```

---

## Say this in an interview

> HelixGate is the control plane I would want if I owned API and AI gateway infrastructure. Clients and agents share one door: JWT audiences, rate limits, TLS 1.3, weighted regions. San Jose is primary because that is where the team sits; Ashburn is failover; Frankfurt is an EU pin and it is already ejected in the demo. MCP servers live behind the same policies — PII never egresses, privileged kubectl-shaped tools stay 423. When Envoy 503s, Sentinel retrieves the runbook, Validator lints live config, and Steward will drain SJC — but only after a human, and only as GitOps.

Then pause: *Want the gateway engine, the MCP guardrails, or the agent graph?*

---

**Ananya Naga Raj** · [GitHub](https://github.com/Ananyanagaraj11) · [LinkedIn](https://www.linkedin.com/in/ananyanagaraj/)

MIT License
