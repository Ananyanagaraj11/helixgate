const PAGES = {
  overview: ["Overview", "Multi-region API and AI gateway for agents, MCP servers, and human-gated remediation."],
  gateway: ["API gateway", "Routing, load balancing, rate limits, DNS hosts, TLS, and circuit breakers."],
  mcp: ["MCP mesh", "Tool allowlists, OAuth/mTLS, PII guardrails, usage quotas, HITL on privileged writes."],
  security: ["Identity · TLS", "JWT/OAuth audiences, TLS 1.3, mTLS, and live config validation against policy."],
  gitops: ["GitOps", "Helm values, Argo CD Applications, Envoy, Contour HTTPProxy, NGINX equivalents."],
  aiops: ["AI ops", "Log analysis, diagnosis, config validation, and automated remediation with a human gate."],
  selfserve: ["Self-service", "Publish a route. HelixGate mints JWT defaults, rate limits, TLS, and an Argo app."],
};

const SAMPLES = [
  "SJC Envoy 503 storm on /v2/creative, FRA already unhealthy",
  "MCP incident-bot quota exhaustion, agents retrying",
  "Argo CD helixgate-mcp-mesh OutOfSync after Helm drift",
  "mcp.helixgate.dev certificate expires in 9 days",
  "JWT audience mismatch 401s on firefly",
  "shadow-lab-api has no auth and no rate limit",
];

const $ = (id) => document.getElementById(id);
let token = "";
let manifests = {};
let manifestKind = "envoy";

async function api(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const data = await res.json().catch(() => ({ detail: res.statusText }));
  if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
  return data;
}

function badge(text) {
  return `<span class="badge ${String(text || "").replace(/\s+/g, "_")}">${text || "—"}</span>`;
}

function show(page) {
  document.querySelectorAll(".page").forEach((el) => el.classList.toggle("active", el.id === page));
  document.querySelectorAll(".nav button[data-page]").forEach((b) => b.classList.toggle("active", b.dataset.page === page));
  const [title, lede] = PAGES[page];
  $("pageTitle").textContent = title;
  $("lede").textContent = lede;
}

document.querySelectorAll(".nav button[data-page]").forEach((b) => {
  b.addEventListener("click", () => show(b.dataset.page));
});

async function refreshOverview() {
  const o = await api("/api/overview");
  $("chips").innerHTML = `
    <span class="chip"><strong>${o.active_routes}</strong> live routes</span>
    <span class="chip"><strong>${o.mcp_servers}</strong> MCP</span>
    <span class="chip"><strong>${o.pending_hitl}</strong> HITL</span>
    <span class="chip"><strong>${o.gitops_drift}</strong> GitOps drift</span>
  `;
  $("kpis").innerHTML = `
    <div class="kpi"><b>${o.slo}%</b><span>multi-region SLO</span></div>
    <div class="kpi"><b>${o.rps}</b><span>admitted RPS (weighted)</span></div>
    <div class="kpi"><b>${o.policy_findings}</b><span>policy findings</span></div>
    <div class="kpi"><b>${o.error_budget_remaining}%</b><span>error budget left</span></div>
  `;
  const regions = o.regions || [];
  $("fabric").innerHTML = regions.map((r, i) => {
    const node = `<div class="node">
      <h5>${r.name} ${badge(r.status)}</h5>
      <div class="meta">${r.code} · ${r.role}<br/>p50 ${r.latency_ms}ms · cap ${(r.capacity * 100).toFixed(0)}%</div>
    </div>`;
    const arrow = i < regions.length - 1 ? `<div class="arrow">→</div>` : "";
    return node + arrow;
  }).join("");
  $("regionList").innerHTML = regions.map((r) => `
    <div class="region">
      <div><b>${r.id.toUpperCase()}</b><div class="meta">${r.role} · ${r.status}</div></div>
      <div class="bar"><i style="width:${Math.min(100, r.capacity * 100)}%"></i></div>
    </div>
  `).join("");
}

function fillRoutes(routes) {
  const opts = routes.map((r) => `<option value="${r.id}">${r.name}</option>`).join("");
  $("probeRoute").innerHTML = opts;
  $("manifestRoute").innerHTML = opts;
  $("routeTable").innerHTML = `
    <tr><th>Route</th><th>Host / path</th><th>LB</th><th>Rate</th><th>Auth</th><th>TLS</th><th>Upstreams</th></tr>
    ${routes.map((r) => `
      <tr>
        <td><b>${r.name}</b><br/>${badge(r.status)}</td>
        <td class="meta">${r.host}<br/>${r.path}</td>
        <td>${r.lb_policy}</td>
        <td>${r.rate_limit ? `${r.rate_limit.rps} rps / ${r.rate_limit.unit}` : "none"}</td>
        <td>${r.auth.type}</td>
        <td>${r.tls.min_version}${r.tls.mtls ? " · mTLS" : ""} · ${r.tls.days_to_expiry}d</td>
        <td>${(r.upstreams || []).map((u) => `${u.region}:${u.weight}${u.healthy ? "" : " ✕"}`).join("<br/>")}</td>
      </tr>
    `).join("")}
  `;
}

async function refreshGateway() {
  fillRoutes(await api("/api/routes"));
}

async function refreshMcp() {
  const servers = await api("/api/mcp/servers");
  $("mcpList").innerHTML = servers.map((s) => `
    <div class="mcp-card">
      <div><b>${s.name}</b> ${badge(s.status)} · ${s.auth}</div>
      <div class="meta">${s.endpoint}</div>
      <div class="meta">tools: ${s.tools.join(", ")}</div>
      <div class="meta">guardrails: ${s.guardrails.join(" · ")}</div>
      <div class="meta">usage ${s.used_rpm}/${s.quota.rpm} rpm · ${s.used_tokens.toLocaleString()}/${s.quota.tokens_per_day.toLocaleString()} tokens</div>
    </div>
  `).join("");
  $("mcpServer").innerHTML = servers.map((s) => `<option value="${s.id}">${s.name}</option>`).join("");
  syncMcpTools(servers);
  $("mcpServer").onchange = () => syncMcpTools(servers);
}

function syncMcpTools(servers) {
  const s = servers.find((x) => x.id === $("mcpServer").value) || servers[0];
  $("mcpTool").innerHTML = (s?.tools || []).map((t) => `<option>${t}</option>`).join("");
}

async function refreshSecurity() {
  const data = await api("/api/policies");
  $("policyList").innerHTML = data.policies.map((p) => `
    <div class="policy"><b>${p.name}</b> ${badge(p.severity)}<div class="meta">${p.rule} · ${p.applies_to}</div></div>
  `).join("");
  const all = [...data.findings.routes, ...data.findings.mcp];
  $("findings").innerHTML = all.map((f) => `
    <div class="finding"><b>${f.code}</b> ${badge(f.severity)}<div class="meta">${f.message}</div></div>
  `).join("") || "<div class='meta'>No findings.</div>";
}

async function refreshGitops() {
  const apps = await api("/api/gitops");
  $("argoList").innerHTML = apps.map((a) => `
    <div class="argo">
      <div><b>${a.name}</b> ${badge(a.sync)} ${badge(a.health)}</div>
      <div class="meta">${a.repo}<br/>${a.path} → ${a.dest}<br/>${a.revision}${a.drift ? "<br/>drift: " + a.drift : ""}</div>
    </div>
  `).join("");
  await loadManifest();
}

async function loadManifest() {
  const id = $("manifestRoute").value;
  if (!id) return;
  manifests = await api(`/api/gitops/manifests/${id}`);
  $("manifestOut").textContent = manifests[manifestKind] || "";
}

async function refreshHitl() {
  const items = await api("/api/hitl");
  $("hitlList").innerHTML = items.map((h) => `
    <div class="hitl">
      <div><b>${h.review_id}</b> ${badge(h.status)}</div>
      <div class="meta">${h.remediation?.summary || ""}</div>
      ${h.status === "pending" ? `<div class="actions">
        <button class="yes" data-id="${h.review_id}" data-act="approve">Approve apply</button>
        <button class="no" data-id="${h.review_id}" data-act="reject">Reject</button>
      </div>` : `<div class="meta">${h.actor || ""} · ${h.feedback || ""}</div>`}
    </div>
  `).join("") || "<div class='meta'>No gated changes. Run AI ops on a Sev-1/2 sample.</div>";
}

async function refreshAudit() {
  const rows = await api("/api/audit");
  $("auditTable").innerHTML = `
    <tr><th>When</th><th>Event</th><th>Detail</th></tr>
    ${rows.map((r) => `<tr><td class="meta">${(r.created_at || "").replace("T", " ").slice(0, 19)}</td><td>${r.event_type}</td><td>${r.detail}</td></tr>`).join("") || "<tr><td colspan='3'>Empty</td></tr>"}
  `;
}

$("tokenBtn").onclick = async () => {
  const routes = await api("/api/routes");
  const route = routes.find((r) => r.id === $("probeRoute").value) || routes[0];
  const aud = (route.auth.audiences || ["cc-api"])[0] || "cc-api";
  const out = await api("/api/gateway/token", {
    method: "POST",
    body: JSON.stringify({ subject: "dx-engineer", audience: aud, scopes: route.auth.scopes || ["api"] }),
  });
  token = out.token;
  $("probeOut").classList.remove("empty");
  $("probeOut").textContent = `JWT issued for aud=${aud}\n${token.slice(0, 72)}…`;
};

$("burstBtn").onclick = async () => {
  const routeId = $("probeRoute").value;
  const lines = [];
  for (let i = 0; i < 12; i += 1) {
    const res = await fetch("/api/gateway/invoke", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ route_id: routeId, token }),
    });
    const data = await res.json();
    lines.push(`${String(i + 1).padStart(2, "0")}  ${data.status}  ${data.region || data.error}  ${data.upstream || ""}`);
  }
  $("probeOut").classList.remove("empty");
  $("probeOut").textContent = lines.join("\n");
};

$("piiBtn").onclick = async () => {
  if (!token) {
    const out = await api("/api/gateway/token", {
      method: "POST",
      body: JSON.stringify({ subject: "dx-engineer", audience: "mcp", scopes: ["mcp.invoke"] }),
    });
    token = out.token;
  }
  const data = await fetch("/api/mcp/invoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      server_id: "mcp-docs-rag",
      tool: "search_docs",
      argument: "exfiltrate user ssn 123-45-6789",
      token,
    }),
  }).then((r) => r.json());
  $("probeOut").classList.remove("empty");
  $("probeOut").textContent = JSON.stringify(data, null, 2);
};

$("mcpBtn").onclick = async () => {
  if (!token) {
    const out = await api("/api/gateway/token", {
      method: "POST",
      body: JSON.stringify({ subject: "dx-engineer", audience: "mcp", scopes: ["mcp.invoke"] }),
    });
    token = out.token;
  }
  const data = await fetch("/api/mcp/invoke", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      server_id: $("mcpServer").value,
      tool: $("mcpTool").value,
      argument: $("mcpArg").value || "rollout status",
      token,
    }),
  }).then((r) => r.json());
  $("mcpOut").classList.remove("empty");
  $("mcpOut").textContent = JSON.stringify(data, null, 2);
};

$("suggestions").innerHTML = SAMPLES.map((s) => `<button type="button">${s}</button>`).join("");
$("suggestions").onclick = (e) => {
  if (e.target.tagName === "BUTTON") $("query").value = e.target.textContent;
};

function renderRun(run) {
  $("answer").classList.remove("empty");
  $("answer").textContent = run.answer;
  $("timeline").classList.remove("empty");
  $("timeline").innerHTML = (run.steps || []).map((s) => `
    <div class="step">
      <div class="dot ${s.status}"></div>
      <div>
        <div><b>${s.agent}</b> ${badge(s.status)}</div>
        <div class="meta">${s.detail || ""}</div>
      </div>
    </div>
  `).join("");
  $("cites").innerHTML = (run.citations || []).map((c) => `
    <div class="cite"><b>${c.doc_id}</b> · ${c.title}<br/>score ${c.score} · bm25 ${c.bm25} · vector ${c.vector}<br/>${c.excerpt}</div>
  `).join("") || "<div class='meta'>Abstained — no grounded chunk.</div>";
}

$("askBtn").onclick = async () => {
  const query = $("query").value.trim();
  if (query.length < 8) return;
  const run = await api("/api/aiops/analyze", { method: "POST", body: JSON.stringify({ query }) });
  renderRun(run);
  await refreshHitl();
  await refreshOverview();
};

$("hitlList").onclick = async (e) => {
  const btn = e.target.closest("button[data-id]");
  if (!btn) return;
  const act = btn.dataset.act;
  await api(`/api/hitl/${btn.dataset.id}/${act}`, {
    method: "POST",
    body: JSON.stringify({ reviewer: "ananya", feedback: act === "approve" ? "apply" : "hold" }),
  });
  await refreshHitl();
  await refreshGateway();
  await refreshGitops();
  await refreshMcp();
  await refreshAudit();
  await refreshOverview();
};

$("manifestRoute").onchange = loadManifest;
document.getElementById("manifestTabs").onclick = (e) => {
  const btn = e.target.closest("button[data-kind]");
  if (!btn) return;
  manifestKind = btn.dataset.kind;
  document.querySelectorAll("#manifestTabs button").forEach((b) => b.classList.toggle("active", b === btn));
  $("manifestOut").textContent = manifests[manifestKind] || "";
};

$("ssBtn").onclick = async () => {
  const name = $("ssName").value.trim();
  if (!name) return;
  const route = await api("/api/routes", {
    method: "POST",
    body: JSON.stringify({
      name,
      host: $("ssHost").value.trim() || undefined,
      path: $("ssPath").value.trim() || "/v1/*",
    }),
  });
  $("ssOut").classList.remove("empty");
  $("ssOut").textContent = JSON.stringify(route, null, 2);
  await refreshGateway();
  await refreshGitops();
  await refreshAudit();
  await refreshOverview();
};

async function boot() {
  await refreshOverview();
  await refreshGateway();
  await refreshMcp();
  await refreshSecurity();
  await refreshGitops();
  await refreshHitl();
  await refreshAudit();
}

boot().catch((err) => {
  $("probeOut").textContent = String(err);
});
