from __future__ import annotations

import uuid
from datetime import datetime, timezone

from helixgate.gitops.renderer import lint_mcp, lint_route
from helixgate.rag.hybrid import HybridIndex, ScoredChunk
from helixgate.plane import ControlPlane

HIGH_RISK = ("prod", "drain", "rotate", "sync", "weight", "quota", "promote", "dns", "tls")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _severity(query: str, hits: list[ScoredChunk]) -> str:
    text = (query + " " + " ".join(h.text for h in hits[:2])).lower()
    if any(w in text for w in ("503", "outage", "unhealthy", "expiry", "401 storm")):
        return "Sev-1"
    if any(w in text for w in ("drift", "quota", "throttl", "429", "mismatch")):
        return "Sev-2"
    return "Sev-3"


def _remediation(query: str, hits: list[ScoredChunk]) -> dict:
    q = query.lower()
    if "503" in q or "sjc" in q and "creative" in q or "outlier" in q:
        return {
            "action": "drain_region",
            "route_id": "rt-creative-cloud",
            "region": "sjc",
            "shift_to": "iad",
            "summary": "Drain SJC creative-cloud upstream and shift weight to IAD.",
        }
    if "quota" in q or "incident-bot" in q or "tokens" in q:
        return {
            "action": "raise_quota",
            "server_id": "mcp-incident",
            "tokens_per_day": 960_000,
            "summary": "Raise incident-bot daily token budget 20% and stop retry storm.",
        }
    if "outofsync" in q or "argo" in q or "drift" in q or "gitops" in q:
        return {
            "action": "gitops_sync",
            "app": "helixgate-mcp-mesh",
            "summary": "Render Helm values and mark Argo app Synced after cert floor is restored.",
        }
    if "tls" in q or "cert" in q or "expir" in q:
        return {
            "action": "rotate_tls",
            "route_id": "rt-mcp-edge",
            "days_to_expiry": 90,
            "summary": "Rotate mcp.helixgate.dev certificate and set remaining life to 90 days.",
        }
    if "jwt" in q or "audience" in q or "401" in q:
        return {
            "action": "note_identity",
            "route_id": "rt-firefly",
            "summary": "Do not disable JWT. Issue tokens with aud=firefly for the inference route.",
        }
    if "shadow" in q or "lab" in q or "unsigned" in q or "no auth" in q:
        return {
            "action": "lock_lab_route",
            "route_id": "rt-unprotected-lab",
            "summary": "Keep lab route in draft, add JWT + rate limit + TLS 1.3 before any DNS record.",
        }
    if hits:
        return {
            "action": "apply_runbook",
            "doc_id": hits[0].doc_id,
            "summary": f"Follow {hits[0].doc_id}: {hits[0].title}.",
        }
    return {"action": "noop", "summary": "No safe automated change. Collect more evidence."}


class OpsGraph:
    """Sentinel → Pathfinder → Validator → Steward. Writes never skip HITL."""

    def __init__(self, index: HybridIndex, plane: ControlPlane):
        self.index = index
        self.plane = plane

    def run(self, query: str) -> dict:
        run_id = f"run-{uuid.uuid4().hex[:8]}"
        hits = self.index.search(query, k=4)
        sentinel = {
            "agent": "Sentinel",
            "status": "ok",
            "detail": f"Parsed incident text and retrieved {len(hits)} runbook chunks (BM25 + TF-IDF + RRF).",
        }
        if not hits:
            pathfinder = {
                "agent": "Pathfinder",
                "status": "abstain",
                "detail": "No grounded runbook. Refusing to invent a diagnosis.",
            }
            validator = {"agent": "Validator", "status": "skipped", "detail": "No candidate change."}
            steward = {"agent": "Steward", "status": "blocked", "detail": "HITL not opened — insufficient evidence."}
            record = {
                "run_id": run_id,
                "query": query,
                "created_at": _now(),
                "grounded": False,
                "severity": "Sev-3",
                "answer": (
                    "HelixGate will not guess. Index a runbook covering this symptom, then re-run AI Ops."
                ),
                "citations": [],
                "steps": [sentinel, pathfinder, validator, steward],
                "remediation": {"action": "noop", "summary": "Abstain"},
                "hitl": None,
            }
            self.plane.runs.insert(0, record)
            return record

        severity = _severity(query, hits)
        diagnosis = (
            f"Likely cause from {hits[0].doc_id} ({hits[0].title}). Severity {severity}. "
            f"{hits[0].text[:280]}"
        )
        pathfinder = {"agent": "Pathfinder", "status": "ok", "detail": diagnosis}
        findings: list[dict] = []
        for route in self.plane.engine.list_routes():
            findings.extend(lint_route(route))
        for server in self.plane.mcp.list_servers():
            findings.extend(lint_mcp(server))
        related = [f for f in findings if any(tok in f["message"].lower() for tok in query.lower().split() if len(tok) > 3)]
        validator = {
            "agent": "Validator",
            "status": "ok",
            "detail": f"Policy engine reported {len(findings)} live findings; {len(related)} overlap this incident.",
            "findings": (related or findings)[:6],
        }
        rem = _remediation(query, hits)
        needs_hitl = severity in {"Sev-1", "Sev-2"} or any(w in query.lower() for w in HIGH_RISK)
        review_id = None
        if needs_hitl and rem.get("action") != "noop":
            review_id = f"hitl-{uuid.uuid4().hex[:8]}"
            self.plane.hitl.insert(
                0,
                {
                    "review_id": review_id,
                    "run_id": run_id,
                    "status": "pending",
                    "remediation": rem,
                    "created_at": _now(),
                },
            )
        steward = {
            "agent": "Steward",
            "status": "waiting" if review_id else "advisory",
            "detail": (
                f"Proposed '{rem['summary']}' — production apply is gated on HITL."
                if review_id
                else rem["summary"]
            ),
        }
        answer_lines = [
            f"Grounded diagnosis ({severity}) from {hits[0].doc_id}.",
            "",
            hits[0].text,
            "",
            f"Proposed remediation: {rem['summary']}",
            "Automated apply stays blocked until a human approves. GitOps remains the source of truth.",
        ]
        record = {
            "run_id": run_id,
            "query": query,
            "created_at": _now(),
            "grounded": True,
            "severity": severity,
            "answer": "\n".join(answer_lines),
            "citations": [
                {
                    "doc_id": h.doc_id,
                    "title": h.title,
                    "category": h.category,
                    "score": h.score,
                    "bm25": h.bm25,
                    "vector": h.vector,
                    "excerpt": h.text[:240],
                }
                for h in hits
            ],
            "steps": [sentinel, pathfinder, validator, steward],
            "remediation": rem,
            "hitl": review_id,
        }
        self.plane.runs.insert(0, record)
        self.plane.audit(
            "aiops.run",
            f"{run_id} grounded={record['grounded']} severity={severity}",
        )
        return record
