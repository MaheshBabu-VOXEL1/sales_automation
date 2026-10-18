/* Voxel1 Growth Engine: Training and BIM Services workspaces.
   Server-backed records; explicit Outlook queues submit approved email only. */

const SERVICES = [
  { id: "bim", name: "BIM Services", code: "BIM" },
  { id: "training", name: "Training", code: "TRN" },
];
const STAGES = ["new", "engaged", "meeting", "proposal", "negotiation", "won"];
const STAGE_NAMES = { new: "New", engaged: "Engaged", meeting: "Meeting", proposal: "Proposal", negotiation: "Negotiation", won: "Won", lost: "Lost" };
// Times and task rationale from Voxel1 Growth EngineV2.html; sample results are excluded.
const CONTENT_RULES = ["Simple, professional tone", "No invented case studies", "Only projects you approve", "No free pilots or trial offers", "Messages only to people who opted in", "You approve every post before it goes out"];
const CHANNEL_ICON = { Internal: ["·", "#5B6879"], Email: ["@", "#4A6785"], LinkedIn: ["in", "#0A66C2"], Instagram: ["IG", "#B1306E"], Facebook: ["f", "#1877F2"], YouTube: ["YT", "#C4302B"], WhatsApp: ["WA", "#1F7A5C"], Phone: ["☎", "#2B3A50"], Website: ["W", "#0B2545"], Event: ["EV", "#7A5C2E"] };

const S = {
  growth: null, icp: {}, leads: {}, budget: null,
  page: "service", sel: "bim", view: "today", lead: null,
  lf: "active", q: "", showDoneTasks: false,
  af: { p: "all", s: "all", t: "all", show: false },
  open: {}, history: {}, busy: false, editor: null,
};

const $ = (id) => document.getElementById(id);
// Mirrors ai_draft.base_domain: registrable part of a host without a public-suffix list.
const FREE_MAIL = ["gmail", "googlemail", "yahoo", "hotmail", "outlook", "live", "msn", "icloud", "aol", "proton", "protonmail", "zoho", "yandex", "mail", "gmx", "rediffmail"];
const baseDomain = (host) => {
  const labels = String(host || "").toLowerCase().replace(/^\.+|\.+$/g, "").split(".").filter(Boolean);
  if (labels[0] === "www") labels.shift();
  const n = labels.length;
  const keep = n >= 3 && labels[n - 1].length === 2 && ["co", "com", "org", "net", "ac", "gov", "edu", "gob", "nic"].includes(labels[n - 2]) ? 3 : 2;
  return labels.slice(-keep).join(".");
};
const domainMismatch = (l) => {
  const email = String(l.email || "").trim(), web = String(l.website || "").trim();
  if (!email.includes("@") || !web) return false;
  let host = "";
  try { host = new URL(web.includes("//") ? web : `https://${web}`).hostname; } catch { return false; }
  if (!host) return false;
  const [a, b] = [baseDomain(email.split("@").pop()), baseDomain(host)];
  // Mirrors ai_draft.related_domains: only the same registrable domain counts; similar names prove nothing.
  if (FREE_MAIL.includes(a.split(".")[0])) return true;
  return a !== b;
};
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const safeUrl = (value) => { try { const u = new URL(value); return ["https:", "http:"].includes(u.protocol) ? u.href : null; } catch { return null; } };
const svc = (id) => SERVICES.find((s) => s.id === id);
const today = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const fmtDate = (iso) => { if (!iso) return ""; const d = new Date(iso.length === 10 ? iso + "T00:00:00" : iso); return d.toLocaleDateString(undefined, { day: "2-digit", month: "short" }); };
const fmtWhen = (item) => item.due ? `${item.due === today() ? "Today" : fmtDate(item.due)}${item.due_time ? " " + item.due_time : ""}` : (item.due_time || "No date");
const CHECK = '<svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.5 6.5l2.3 2.3L9.5 3.8" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

/* ---------- data ---------- */
async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  if (response.status === 401) { location.href = "/login"; throw new Error("Please sign in again."); }
  let data = {};
  try { data = await response.json(); } catch { /* empty body */ }
  if (!response.ok) { const error = new Error(data.error || `Request failed (${response.status})`); error.status = response.status; error.budget = data.budget; throw error; }
  return data;
}

async function load() {
  const [growth, ...rest] = await Promise.all([
    api("/api/growth"),
    ...SERVICES.map((s) => api(`/api/services/${s.id}/icp`)),
    ...SERVICES.map((s) => api(`/api/services/${s.id}/leads`)),
  ]);
  if (!growth.campaigns || !growth.jobs || !growth.sales_progress) throw new Error("The server update is not ready yet. Refresh after deployment, or restart python server.py for a local server.");
  S.growth = growth;
  SERVICES.forEach((s, i) => { S.icp[s.id] = rest[i]; S.leads[s.id] = rest[SERVICES.length + i]; });
  S.budget = providerMode() ? await api("/api/budget").catch(() => null) : null;
  if (S.lead && !lead(S.lead)) S.lead = null;
  S.history = S.lead ? { [S.lead]: await api(`/api/services/${S.sel}/leads/${S.lead}/history`).catch(() => []) } : {};
}

const providerMode = () => SERVICES.some((s) => S.icp[s.id]?.search_mode === "Apollo + Brave");
const settings = (id) => S.growth.settings.find((r) => r.service === id) || { paused: 0, goal: 0, strategy: "" };
const paused = (id) => Boolean(settings("global").paused || settings(id).paused);
const items = (id, kind) => S.growth.items.filter((i) => i.service === id && (!kind || i.kind === kind));
const item = (itemId) => S.growth.items.find((i) => i.id === itemId);
const allLeads = (id) => S.leads[id] || [];
const activeLeads = (id) => allLeads(id).filter((l) => (l.review_decision || "active") === "active");
const lead = (leadId) => SERVICES.flatMap((s) => allLeads(s.id)).find((l) => l.id === leadId);
const detail = (leadId) => S.growth.lead_details.find((d) => d.lead_id === leadId) || { stage: "new", owner: "", room_notes: "" };
const wonCount = (id) => S.growth.sales_progress?.[id]?.quarter ? S.growth.sales_progress[id].quarter_won : activeLeads(id).filter((l) => detail(l.id).stage === "won").length;
const pendingDrafts = (id) => S.growth.items.filter((i) => i.kind !== "task" && i.state === "pending" && (!id || i.service === id));
const reasonLabel = (id, code) => S.icp[id]?.review_reasons?.[code] || code || "No reason recorded";

/* ---------- UI helpers ---------- */
let noticeTimer;
function notice(text, error = false) {
  const box = $("notice");
  box.textContent = text;
  box.classList.toggle("error", error);
  box.hidden = false;
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { box.hidden = true; }, error ? 9000 : 5000);
}

async function run(task, success) {
  if (S.busy) return;
  S.busy = true;
  document.body.classList.add("busy");
  try {
    const result = await task();
    await load();
    render();
    if (success) notice(typeof success === "function" ? success(result) : success);
    return result;
  } catch (error) {
    if (error.status === 409 && !error.budget) { await load().catch(() => {}); render(); }
    notice(error.message, true);
    throw error;
  } finally {
    S.busy = false;
    document.body.classList.remove("busy");
  }
}

const stHtml = (cls, label) => `<span class="st ${cls}"><i></i>${esc(label)}</span>`;
function itemStatus(i) {
  if (i.kind === "brief") return stHtml(i.state === "pending" ? "you" : "done", i.state === "pending" ? "Needs review" : i.state === "rejected" ? "Rejected" : "Reviewed brief");
  if (i.kind === "room" && i.state === "done") return stHtml("done", "Applied to room");
  if (i.state === "done" && S.growth.outlook?.queue.some((q) => q.item_id === i.id && q.state === "accepted")) return stHtml("done", "Submitted to Outlook");
  if (i.state === "done") return i.kind === "task" ? stHtml("done", "Done") : stHtml("done", "Posted / sent by you");
  if (i.state === "approved") return stHtml("done", "Approved draft");
  if (i.state === "rejected") return stHtml("later", i.kind === "task" ? "Skipped" : "Rejected");
  if (i.kind !== "task") return stHtml("you", "Needs approval");
  if (i.due && i.due < today()) return stHtml("you", "Overdue");
  if (i.due === today()) return stHtml("run", "Today");
  return stHtml("later", i.due ? "Later" : "Open");
}
const chanCell = (name) => { const c = CHANNEL_ICON[name] || ["?", "#5B6879"]; return `<span class="chan"><span class="ci" style="background:${c[1]}">${esc(c[0])}</span>${esc(name)}</span>`; };
const who = (owner) => `<span class="who ${/^you$/i.test(owner || "") ? "you" : ""}">${esc(owner || "Unassigned")}</span>`;
const interestBadge = (l) => (l.review_decision || "active") !== "active"
  ? `<span class="badge cold">${l.review_decision === "rejected" ? "Rejected" : "Archived"}</span>`
  : l.status === "interested" ? '<span class="badge ok">Interested</span>' : l.status === "not_interested" ? '<span class="badge cold">Not interested</span>' : '<span class="badge plain">Needs review</span>';
const sbar = (stage) => `<span class="sbar">${STAGES.map((s, i) => `<i class="${i <= STAGES.indexOf(stage) ? (stage === "won" ? "won" : "on") : ""}"></i>`).join("")}</span>`;

function itemButtons(i) {
  const b = [];
  const id = i.id;
  if (i.kind !== "task" && i.body) b.push(`<button class="btn" data-item="toggle" data-id="${id}">${S.open[id] ? "Hide text" : "View text"}</button>`);
  if (i.state === "pending") {
    if (i.kind === "task") b.push(`<button class="btn pri" data-item="complete" data-id="${id}">Mark done</button>`);
    else b.push(`<button class="btn pri" data-item="approve" data-id="${id}">${i.kind === "brief" ? "Mark reviewed" : "Approve"}</button>`);
    b.push(`<button class="btn" data-item="edit" data-id="${id}">Edit</button>`);
    b.push(`<button class="btn" data-item="reject" data-id="${id}">${i.kind === "task" ? "Skip" : "Reject"}</button>`);
  } else if (i.state === "approved") {
    b.push(`<button class="btn" data-item="copy" data-id="${id}">Copy text</button>`);
    b.push(`<button class="btn" data-item="download" data-id="${id}">Download</button>`);
    if (i.kind !== "brief") b.push(i.kind === "room" ? `<button class="btn pri" data-item="apply-room" data-id="${id}">Apply to room</button>` : `<button class="btn pri" data-item="complete" data-id="${id}">Record as ${i.kind === "content" ? "posted" : "sent"}</button>`);
    if (i.kind === "outreach" && i.channel === "Email") {
      const queued = S.growth.outlook?.queue.find((q) => q.item_id === id && q.state !== "cancelled");
      b.push(queued ? `<span class="note">Outlook: ${esc(queued.state)}</span>` : `<button class="btn pri" data-item="outlook-send" data-id="${id}">Send with Outlook</button>`);
    }
    b.push(`<button class="btn" data-item="reopen" data-id="${id}">Reopen</button>`);
  } else if (i.kind === "outreach" && i.state === "done") {
    // The sent record drives follow-ups and history, so it cannot be reopened or edited.
    b.push(`<span class="note">Recorded as sent; locked</span>`);
  } else {
    b.push(`<button class="btn" data-item="reopen" data-id="${id}">Reopen</button>`);
  }
  if (i.kind === "content" && ["Instagram", "Facebook"].includes(i.channel)) b.push(`<button class="btn" data-item="graphic-png" data-id="${id}">Download PNG</button><a class="btn" href="/api/growth/graphics/${i.id}.svg?revision=${i.revision}" download="voxel1-${i.id}-graphic-draft.svg">Editable SVG</a>`);
  return `<div class="actions">${b.join("")}</div>`;
}
const draftText = (i) => S.open[i.id] && i.body ? `<div class="draft">${esc(i.body)}</div>${i.kind === "content" && ["Instagram", "Facebook"].includes(i.channel) ? `<figure><img width="270" height="270" loading="lazy" src="/api/growth/graphics/${i.id}.svg?revision=${i.revision}" alt="Editable graphic-card draft preview"><figcaption class="note">Original graphic-card layout draft; review alongside the caption.</figcaption></figure>` : ""}` : "";

/* ---------- top bar and sidebar ---------- */
function topbar() {
  const goal = SERVICES.reduce((a, s) => a + settings(s.id).goal, 0);
  const won = SERVICES.reduce((a, s) => a + wonCount(s.id), 0);
  $("tot").textContent = `${won} / ${goal}`;
  const need = pendingDrafts().length;
  $("approvals").innerHTML = `Approvals <b>${need}</b>`;
  $("approvals").className = "apbtn" + (need ? " warn" : "") + (S.page === "approvals" ? " on" : "");
  $("approvals").setAttribute("aria-pressed", String(S.page === "approvals"));
  const active = SERVICES.filter((s) => !paused(s.id)).length;
  $("gstate").textContent = active === SERVICES.length ? "Both workspaces active" : active === 0 ? "All paused" : `${active} of ${SERVICES.length} active`;
  $("gdot").className = "sdot" + (active === 0 ? " off" : active < SERVICES.length ? " warn" : "");
  $("pause-all").textContent = settings("global").paused ? "Resume all" : "Pause all";
  const dark = document.documentElement.dataset.theme === "dark" || (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: dark)").matches);
  $("theme").textContent = dark ? "Light mode" : "Dark mode";
}

function side() {
  $("side").innerHTML = `<span class="lbl">Service workspaces</span>` + SERVICES.map((s) => {
    const n = pendingDrafts(s.id).length;
    const state = paused(s.id) ? "Paused" : n ? `${n} need${n === 1 ? "s" : ""} you` : "Active";
    return `<button class="nav" type="button" data-sel="${s.id}" aria-current="${S.page !== "approvals" && S.sel === s.id}">
      <span class="av av-${s.id === "training" ? "train" : s.id}">${s.code}</span>
      <span class="nav-n"><b>${esc(s.name)}</b><small><span class="sdot ${paused(s.id) ? "off" : n ? "warn" : ""}"></span>${state}</small></span>
      <span class="nav-s"><b>${wonCount(s.id)}</b>/${settings(s.id).goal}</span></button>`;
  }).join("") + `<div class="side-foot"><span class="lbl" style="padding:0">Sales goal</span><span class="note">Won / goal per service, from the stages your team sets in each lead room. Goals start at 0 until you set them.</span></div>`;
}

/* ---------- service page ---------- */
function header(s) {
  const st = settings(s.id);
  const n = pendingDrafts(s.id).length;
  const badge = paused(s.id) ? '<span class="badge cold">Paused</span>' : n ? `<span class="badge warn">${n} need${n === 1 ? "s" : ""} you</span>` : '<span class="badge ok">Active</span>';
  const leads = activeLeads(s.id);
  const pipeline = leads.filter((l) => ["engaged", "meeting", "proposal", "negotiation"].includes(detail(l.id).stage)).length;
  const plan = rhythmPlan(s.id);
  const goal = st.goal, won = wonCount(s.id);
  const seg = goal ? `<span class="seg">${Array.from({ length: Math.min(goal, 20) }, (_, i) => `<i class="${i < won ? "won" : ""}"></i>`).join("")}</span>` : '<span>Set a goal to track progress</span>';
  const next = n;
  const now = paused(s.id)
    ? `<b>Paused.</b> New searches and approvals are blocked until you resume. A search already running is not cancelled.`
    : n ? `<b>${n} draft${n === 1 ? "" : "s"} waiting for your approval.</b>`
      : `<b>Nothing waiting for you.</b> The rhythm prepares drafts for approval; set it with Edit rhythm.`;
  return `<div class="crumb">Growth Engine <span>/</span> ${S.lead ? `<button type="button" data-act="back">${esc(s.name)}</button> <span>/</span> Lead room` : esc(s.name)}</div>
  <div class="ph">
    <div class="ph-l"><span class="av lg av-${s.id === "training" ? "train" : s.id}">${s.code}</span><div style="min-width:0"><div class="title-row"><h1>${esc(s.name)}</h1>${badge}</div><p>${esc(st.strategy || "No strategy written yet.")}</p></div></div>
    <div class="ph-r"><button class="btn" type="button" data-act="edit-goal">Sales Goal</button><button class="btn" type="button" data-act="pause">${settings(s.id).paused ? "Resume workspace" : "Pause workspace"}</button></div>
  </div>
  <section class="kpis" aria-label="Key figures">
    <div class="kpi"><span>Sales goal ${esc(S.growth.sales_progress?.[s.id]?.quarter || "(all time)")}</span><b>${won}<small> / ${goal}</small></b>${seg}</div>
    <div class="kpi"><span>Active leads</span><b>${leads.length}</b><span>${leads.filter((l) => l.email || l.phone).length} with email or phone</span></div>
    <div class="kpi"><span>In pipeline</span><b>${pipeline}</b><span>engaged to negotiation</span></div>
    <div class="kpi"><span>Daily rhythm</span><b>${plan.filter((a) => a.on).length}<small> / ${plan.length}</small></b><span>activities on</span></div>
    <div class="kpi ${n ? "warn" : ""}"><span>Needs you</span><b>${n}</b><span>drafts to approve</span></div>
  </section>
  <div class="now"><span class="pulse${paused(s.id) || !next ? " off" : ""}"></span><span>${now}</span></div>`;
}

const byDue = (a, b) => (a.due || "9999").localeCompare(b.due || "9999") || (a.due_time || "99").localeCompare(b.due_time || "99") || a.id - b.id;

function todayRows(id) {
  const t = today();
  return S.growth.items.filter((i) => i.service === id && (
    (i.kind === "task" && (i.state === "pending" ? (!i.due || i.due <= t) : S.showDoneTasks || (i.state === "done" && i.updated_at.slice(0, 10) === new Date().toISOString().slice(0, 10)))) ||
    (i.kind !== "task" && i.state === "pending" && (!i.due || i.due <= t))
  )).sort(byDue);
}

function workerStatus() {
  const w = S.growth.worker || {};
  if (w.runtime?.running && w.runtime.busy) return `<p class="note">Worker is processing a batch started ${esc(new Date(w.runtime.started_at).toLocaleTimeString())}. Results appear as jobs finish. A long batch may need attention if individual jobs stop progressing.</p>`;
  if (!w.last_tick) return '<p class="blocked">Background worker: no tick recorded yet. Scheduled drafts only run while the server is awake.</p>';
  const minutes = Math.round((Date.now() - new Date(w.last_tick).getTime()) / 60000);
  const when = `${new Date(w.last_tick).toLocaleString(undefined, { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })} (${minutes < 1 ? "just now" : `${minutes} min ago`})`;
  const failing = w.last_error && (!w.last_ok || w.last_error_at >= w.last_ok);
  const stale = minutes > 5 && !w.runtime?.running;
  return `<p class="${stale || failing ? "blocked" : "note"}">Last worker tick: ${esc(when)}${stale ? ". The worker looks stopped or asleep; scheduled jobs will not run." : ""}${failing ? ` Last tick had errors: ${esc(w.last_error)}` : ""}${w.commit ? ` <span class="muted">Build ${esc(String(w.commit).slice(0, 7))}</span>` : ""}</p>`;
}

function knowledgeStatus(id) {
  const k = S.growth.knowledge?.[id];
  if (!k?.version) return `<p class="note">Company knowledge pack: none yet for this service. AI drafts describe Voxel1 only in general terms.</p>`;
  const rows = k.missing.map((m) => `<li><b>${esc(m.priority)}</b>: ${esc(m.question)}</li>`).join("");
  return `<details class="note"><summary>Company knowledge pack ${esc(k.version)}: ${k.usable} facts used in drafts (${k.awaiting_approval} from the website, awaiting owner approval) · ${k.held} held back · ${k.missing.length} missing facts</summary><p class="muted">Source: ${esc(k.source || "")}. Drafts may state only these facts about Voxel1 and remain pending for review. Portfolio projects, testimonials and office cities are held until the owner approves them.</p><ul>${rows}</ul></details>`;
}

function retryDraftButton(j, r) {
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const supported = /^(?:room:\d+:[a-f0-9]{12}|draft:\d+|message:(?:LinkedIn|WhatsApp):\d+)$/.test(j.job);
  if (j.state !== "needs_you" || !supported) return "";
  if (r.retry_safe && r.failure_token && j.day === day && !r.item_id && !r.item_ids?.length) {
    return `<button class="btn" data-act="retry-draft" data-service="${esc(j.service)}" data-day="${esc(j.day)}" data-job="${esc(j.job)}" data-token="${esc(r.failure_token)}" ${paused(j.service) ? "disabled" : ""}>Retry failed draft</button><span class="sub">One explicit attempt, subject to daily and monthly limits.</span>`;
  }
  return '<span class="sub">Retry unavailable: older record, saved output, or unconfirmed failure outcome. Review this job before regenerating.</span>';
}

function setupChecks(campaign, budget, knowledge, storageAllowed) {
  if (!campaign) return ["Set a Sales Goal before scheduling this workspace."];
  const checks = [];
  if (campaign.full_rhythm && !storageAllowed) checks.push("Research blocked: confirm Brave storage rights before enabling research.");
  if (budget && budget.searches_used >= budget.limits.searches) checks.push("New discovery blocked: monthly search allowance is used. Existing-lead drafts can still use the remaining Gemini allowance.");
  if (budget && budget.used.gemini + budget.held.gemini >= budget.limits.gemini) checks.push("New AI drafts blocked: no Gemini allowance remains. Saved drafts can still be reviewed and edited.");
  if (campaign.full_rhythm) {
    if (campaign.partner_enabled !== false && !campaign.partner_accounts?.trim()) checks.push("Partner activity needs actual partner names and matching saved leads in Sales Goal.");
    if (!campaign.existing_clients?.trim()) checks.push("Client activity needs actual client names and matching saved leads, or a recorded Won opportunity.");
    if (!Object.values(campaign.content_targets || {}).some((v) => v > 0)) checks.push("Social drafts disabled: all daily targets are 0. Set targets in Sales Goal when you want these drafts.");
    if (!campaign.proof_consent || !campaign.approved_proof?.trim()) checks.push("Public proof unavailable: add approved facts and permission in Sales Goal. Educational drafts do not require a project example.");
  }
  if (knowledge?.awaiting_approval) checks.push(`${knowledge.awaiting_approval} website-derived company facts still await owner approval. Review the company knowledge section below.`);
  return checks;
}

function workflowSetup(s, campaign) {
  const checks = setupChecks(campaign, S.budget, S.growth.knowledge?.[s.id], S.growth.research_storage_allowed);
  return `<div class="panel-b"><h3>Workflow setup</h3><p class="note">Draft preparation and human review are available within the configured limits. These checks do not verify contact identity, business relationships or delivery permission.</p>${checks.length ? `<ul class="note">${checks.map((v) => `<li>${esc(v)}</li>`).join("")}</ul>` : '<p class="note">No missing setup detected by these checks. Review contact details and draft facts before approval.</p>'}<button class="btn" data-act="campaign">Review Sales Goal setup</button></div>`;
}

function agentPanel(s) {
  const campaign = S.growth.campaigns.find((c) => c.service === s.id);
  const jobs = S.growth.jobs.filter((j) => j.service === s.id);
  const messages = items(s.id, "outreach");
  const meetings = activeLeads(s.id).filter((l) => detail(l.id).stage === "meeting").length;
  return `<section class="panel"><div class="panel-h"><div><h2>Live agent workflow</h2><p class="note">${campaign ? `${esc(campaign.objective)} · Discovery ${esc(campaign.search_time)} / drafts ${esc(campaign.draft_time)} IST, every day. ${paused(s.id) ? "Paused." : "Active during campaign dates."}` : "Set a Sales Goal to start scheduled lead discovery and approval-ready drafts."}</p></div><button class="btn pri" data-act="campaign">${campaign ? "Edit Sales Goal" : "Set Sales Goal"}</button></div>
    <div class="panel-b"><p class="note">${activeLeads(s.id).length} active leads · ${messages.filter((i) => i.state === "pending").length} messages awaiting approval · ${messages.filter((i) => i.state === "done").length} recorded sent · ${meetings} currently at meeting stage · ${wonCount(s.id)} won${campaign?.quarter ? ` in ${esc(campaign.quarter)}` : " (all time)"}. Lead, message and meeting counts are service-wide.</p>${campaign?.content_targets ? `<p class="note">Daily content targets: ${Object.entries(campaign.content_targets).map(([channel, count]) => `${esc(channel)} ${count}`).join(" · ")}. ${campaign.full_rhythm ? "Complete draft rhythm enabled: see per-activity status below. Instagram/Facebook include editable graphic cards." : `${campaign.auto_linkedin ? "AI LinkedIn drafts enabled from 12:00 IST." : "LinkedIn preparation is manual."} ${campaign.auto_rooms ? "AI room drafts enabled from 07:30 IST." : "Room preparation is manual."} Other social content remains manual.`}</p>` : ""}</div>
    <div class="panel-b">${S.growth.automation_missing?.length ? `<p class="blocked">Server setup needed: ${S.growth.automation_missing.map(esc).join(", ")}. Add these server environment settings and restart; never paste API keys into goal fields.</p>` : ""}<p class="note">${campaign?.full_rhythm ? "Runs research, messages, social drafts and reporting within your provider budgets. Signal research requires a Brave plan with storage rights. Missing data and limits appear per activity." : "Uses Apollo, Brave and Gemini within server budgets. Up to one discovery and five email draft attempts per day."} Draft preparation sends or publishes nothing. The hosting server must stay running. <button class="linkish" data-act="refresh-jobs">Refresh results</button></p>${workerStatus()}${knowledgeStatus(s.id)}</div>
    ${workflowSetup(s, campaign)}<div class="tw"><table><thead><tr><th>Day (IST)</th><th>Job</th><th>Status</th><th>Result</th></tr></thead><tbody>${jobs.length ? jobs.map((j) => {
      const r = JSON.parse(j.result || "{}");
      return `<tr><td>${esc(j.day)}</td><td>${esc(j.job)}<span class="sub">Updated ${esc(new Date(j.updated_at).toLocaleString())}</span></td><td>${esc(j.state.replaceAll("_", " "))}</td><td>${esc(j.state === "running" ? "Processing this attempt; previous results will be replaced after it finishes." : r.message || (j.job === "discovery" ? `${r.found ?? 0} found; ${r.added ?? 0} added` : "No detailed result recorded."))}${r.warnings?.length ? `<span class="sub">${esc(r.warnings.join(" "))}</span>` : ""}${r.item_id ? `<button class="linkish" data-act="review-output" data-output="${r.item_id}">Review saved output</button>` : ""}${retryDraftButton(j, r)}</td></tr>`;
    }).join("") : '<tr><td colspan="4" class="empty-cell">No jobs have run yet.</td></tr>'}</tbody></table></div></section>`;
}

// The service's rhythm with each activity's time and on/off from its Sales Goal.
const rhythmPlan = (id) => {
  const saved = S.growth.campaigns.find((c) => c.service === id)?.rhythm || [];
  return S.growth.rhythm_templates[id].map(([time, label, title, purpose], i) => ({ time: saved[i]?.time || time, label, title, purpose, on: saved[i]?.on ?? true }));
};

function rhythmResult(s, index, scheduled) {
  const day = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const campaign = S.growth.campaigns.find((c) => c.service === s.id);
  const job = S.growth.jobs.find((j) => j.service === s.id && j.day === day && j.job === `rhythm:${index}`);
  if (!rhythmPlan(s.id)[index].on) return '<td>Off</td><td class="note">Turned off in Sales Goal.</td>';
  if (!campaign?.full_rhythm) return '<td><span class="note">Draft rhythm disabled</span></td><td class="note">Enable Complete draft rhythm in Sales Goal.</td>';
  if (!job) {
    if (paused(s.id)) return '<td>Paused</td><td class="note">Resume the workspace to run scheduled activities.</td>';
    if (day < campaign.start || (campaign.end && day > campaign.end)) return '<td>Outside campaign dates</td><td class="note">Review the campaign start and end dates in Sales Goal.</td>';
    if (index === (s.id === "bim" ? 5 : 1) && campaign.partner_enabled === false) return '<td>Disabled</td><td class="note">Partner activity is optional and disabled in Sales Goal.</td>';
    const socialSlot = s.id === "bim" ? 8 : 5;
    if (index === socialSlot && !Object.values(campaign.content_targets || {}).some((v) => v > 0)) return '<td>Disabled (0 targets)</td><td class="note">No social drafts requested. Set daily targets in Sales Goal to enable them.</td>';
    return `<td>Scheduled / waiting</td><td class="note">${esc(scheduled)} IST during campaign dates.</td>`;
  }
  const result = JSON.parse(job.result || "{}");
  const outputs = (result.item_ids || []).map(item).filter(Boolean);
  const reviewed = outputs.length && outputs.every((i) => ["approved", "done"].includes(i.state));
  const state = ["needs_you", "needs_input", "needs_budget"].includes(job.state) ? job.state.replaceAll("_", " ") : reviewed ? "Reviewed" : job.state.replaceAll("_", " ");
  return `<td><b>${esc(state)}</b></td><td><span class="sub">${esc(result.message || "Job is running.")}</span>${(result.issues || []).map((v) => `<span class="sub">${esc(v)}</span>`).join("")}${outputs.map((i) => `<button class="linkish" data-act="review-output" data-output="${i.id}">${esc(i.title)}</button>`).join("<br>")}</td>`;
}

function rhythm(s) {
  const schedule = S.growth.rhythm_settings.find((r) => r.service === s.id);
  const full = S.growth.campaigns.find((c) => c.service === s.id)?.full_rhythm;
  const drafts = pendingDrafts(s.id).sort(byDue);
  const row = (i) => {
    const l = i.lead_id ? lead(i.lead_id) : null;
    const kind = i.kind === "brief" ? "Review brief" : i.kind === "room" ? "Lead room" : i.kind === "content" ? "Content" : "Outreach";
    return `<tr><td><span class="ty Content">${kind}</span></td>
      <td><b class="strong">${esc(i.title)}</b>${l ? `<span class="sub">Lead: <button class="linkish" type="button" data-lead="${l.id}">${esc(l.company)}</button></span>` : ""}<span class="sub">${esc(i.channel)} draft${i.label ? " · " + esc(i.label) : ""}</span>${draftText(i)}
      <div class="actions">${i.body ? `<button class="btn" data-item="toggle" data-id="${i.id}">${S.open[i.id] ? "Hide text" : "View text"}</button>` : ""}<button class="btn pri" data-item="approve" data-id="${i.id}">Approve</button><button class="btn" data-item="reject" data-id="${i.id}">Reject</button></div></td></tr>`;
  };
  return `${agentPanel(s)}<section class="panel">
    <div class="panel-h"><div><h2>${esc(s.name)} daily rhythm</h2><span class="note">${full ? "Runs daily during campaign dates, through review drafts. Sending and publishing are separate." : "Reference schedule; enable Complete draft rhythm in Sales Goal for execution."} All times IST (Asia/Kolkata).</span></div>
      <div class="actions"><button class="btn" type="button" data-act="campaign">Edit rhythm</button>${schedule.enabled ? '<button class="btn" type="button" data-act="auto-rhythm">Turn off daily planning</button>' : ""}</div></div>
    <div class="tw"><table><thead><tr><th>Time (IST)</th><th>Type</th><th>Activity and purpose</th><th>Draft workflow status</th><th>Outputs / next action</th></tr></thead>
      <tbody>${rhythmPlan(s.id).map((a, index) => ({ ...a, index })).sort((x, y) => x.time.localeCompare(y.time)).map(({ time, label, title, purpose, on, index }) => `<tr${on ? "" : ' class="off"'}><td class="t">${esc(time)}</td><td><span class="ty ${esc(label)}">${esc(label)}</span></td><td><b class="strong">${esc(title)}</b><span class="sub">${esc(purpose)}</span></td>${rhythmResult(s, index, time)}</tr>`).join("")}</tbody>
    </table></div><div class="panel-f"><span class="note">${full ? "Each activity shows saved drafts, research coverage, or missing input/budget. Review outputs before use. The worker stays available while the server runs and respects pause." : "Set times and turn activities on or off with Edit rhythm."} Missed days are not backfilled. <a href="/draft-rhythm-guide" target="_blank" rel="noopener">Workflow setup and limits</a></span></div>
  </section>
  <section class="panel">
    <div class="panel-h"><div><h2>Waiting for your approval</h2><span class="note">Drafts the rhythm prepared. Approve or reject each one; nothing is sent or posted without approval.</span></div></div>
    <div class="tw"><table>
      <thead><tr><th>Type</th><th>Draft</th></tr></thead>
      <tbody>${drafts.length ? drafts.map(row).join("") : '<tr><td colspan="2" class="empty-cell">Nothing waiting for approval.</td></tr>'}</tbody>
    </table></div>
  </section>`;
}

/* ---------- leads ---------- */
function findPanel(s) {
  const icp = S.icp[s.id];
  const provider = icp.search_mode === "Apollo + Brave";
  const b = S.budget;
  let budget = "";
  if (provider && b) {
    const names = { apollo: "Apollo", brave: "Brave", gemini: "Gemini" };
    const cards = Object.entries(names).filter(([k]) => b.estimate[k] || b.used[k] || b.held[k]).map(([k, name]) =>
      `<div class="bcard"><span>${name} requests</span><b>${b.used[k]}<small> / ${b.limits[k] || "no limit set"}</small></b><span>This search: up to ${b.estimate[k]}${b.held[k] ? ` · ${b.held[k]} held` : ""}</span></div>`);
    cards.unshift(`<div class="bcard"><span>Searches this month</span><b>${b.searches_used}<small> / ${b.limits.searches || "no limit set"}</small></b><span>Counted even if a search fails</span></div>`);
    budget = `<div class="budget"><div class="bgrid">${cards.join("")}</div>${b.allowed ? "" : `<p class="blocked">Search blocked: ${b.blocked_reasons.map(esc).join(" ")}</p>`}<p class="note">Counts are provider requests sent by this app (${esc(b.month)}, UTC), not credits or money. Limits are set on the server.</p></div>`;
  }
  const blocked = paused(s.id) || (provider && b && !b.allowed);
  return `<section class="panel">
    <div class="panel-h"><div><h2>Find companies</h2><span class="note">${provider ? `Source: Apollo + Brave${icp.ai_qualification_enabled ? " + Gemini screening" : ""}. Up to 10 companies per search; you confirm the estimated requests first.` : "Source: OpenStreetMap city samples (no paid provider configured)."} ICP countries: ${esc(icp.countries.join(", "))}.</span></div>
      <div class="actions"><button class="btn" type="button" data-act="icp">Edit ICP</button><button class="btn" type="button" data-act="add-company">Add company</button><button class="btn pri" type="button" data-act="search" ${blocked ? "disabled" : ""}>Search companies</button></div></div>
    ${budget ? `<div class="panel-b">${budget}</div>` : ""}
  </section>`;
}

function leadFilter(l) {
  const active = (l.review_decision || "active") === "active";
  if (S.lf === "excluded") return !active;
  if (!active) return false;
  if (S.lf === "ai") return Boolean(l.ai_screened);
  if (S.lf === "new" || S.lf === "interested" || S.lf === "not_interested") return l.status === S.lf;
  return true;
}

function nextStep(l) {
  return S.growth.items.filter((i) => i.lead_id === l.id && i.state === "pending").sort(byDue)[0];
}

function leads(s) {
  const all = allLeads(s.id);
  const q = S.q.trim().toLowerCase();
  const list = all.filter((l) => leadFilter(l) && l.company.toLowerCase().includes(q))
    .sort((a, b) => STAGES.indexOf(detail(b.id).stage) - STAGES.indexOf(detail(a.id).stage) || b.id - a.id);
  const count = (f) => { const prev = S.lf; S.lf = f; const n = all.filter(leadFilter).length; S.lf = prev; return n; };
  const chips = [["active", "Active"], ["ai", "Gemini-screened"], ["new", "Needs review"], ["interested", "Interested"], ["not_interested", "Not interested"], ["excluded", "Rejected / archived"]]
    .map(([v, label]) => `<button class="fchip" type="button" data-lf="${v}" aria-pressed="${S.lf === v}">${label} <span class="num">${count(v)}</span></button>`).join("");
  return findPanel(s) + `<section class="panel">
    <div class="panel-h"><div><h2>Leads</h2><span class="note">Open a lead to see why it is listed, set its stage and owner, plan next steps and review it.</span></div><input class="search" type="search" id="lead-q" placeholder="Find a company" aria-label="Find a company" value="${esc(S.q)}"></div>
    <div class="filters"><div class="fgroup">${chips}</div></div>
    <div class="tw"><table>
      <thead><tr><th>Lead</th><th>Stage</th><th>Why listed</th><th>Next step</th><th>Owner</th></tr></thead>
      <tbody>${list.length ? list.map((l) => {
        const d = detail(l.id), nx = nextStep(l);
        const stage = d.stage === "lost" ? '<span class="badge cold">Lost</span>' : `${STAGE_NAMES[d.stage]}`;
        return `<tr class="click" data-lead="${l.id}" tabindex="0">
          <td><b class="strong">${esc(l.company)}</b><span class="sub">${esc([l.city, l.country].filter(Boolean).join(", ") || "Location unknown")}</span></td>
          <td><div class="stage"><span class="stage-l">${stage} ${interestBadge(l)}</span>${d.stage === "lost" ? "" : sbar(d.stage)}</div></td>
          <td class="why"><span class="clamp">${esc(l.match_reason || "No reason recorded (saved before reasons were tracked).")}</span>${l.ai_screened ? '<span class="sub">Gemini: plausible buyer</span>' : ""}</td>
          <td>${nx ? `${esc(nx.title)}<span class="sub">${esc(fmtWhen(nx))}</span>` : '<span class="muted">No next step</span>'}</td>
          <td>${who(nx?.owner || d.owner)}</td></tr>`;
      }).join("") : `<tr><td colspan="5" class="empty-cell">${all.length ? "No leads match this filter." : "No leads yet. Use Search companies or Add company."}</td></tr>`}</tbody>
    </table></div>
  </section>`;
}

/* ---------- content ---------- */
function content(s) {
  const list = items(s.id, "content").sort(byDue);
  const channels = [...new Set(list.map((i) => i.channel))];
  const roomCount = activeLeads(s.id).filter((l) => detail(l.id).room_notes.trim()).length;
  return `<section class="panel">
    <div class="panel-h"><h2>Channels</h2><span class="note">Reach, enquiries and meetings are not measured: no social, email or analytics account is connected.</span></div>
    <div class="tw"><table>
      <thead><tr><th>Channel</th><th class="r">Drafts</th><th class="r">Approved</th><th class="r">Posted (recorded)</th><th class="r">Rejected</th></tr></thead>
      <tbody>${channels.length ? channels.map((c) => { const it = list.filter((i) => i.channel === c), n = (st) => it.filter((i) => i.state === st).length;
        return `<tr><td>${chanCell(c)}</td><td class="r num" data-l="Drafts">${n("pending")}</td><td class="r num" data-l="Approved">${n("approved")}</td><td class="r num" data-l="Posted">${n("done")}</td><td class="r num" data-l="Rejected">${n("rejected")}</td></tr>`; }).join("")
        : '<tr><td colspan="5" class="empty-cell">No content yet.</td></tr>'}</tbody>
    </table></div>
  </section>
  <section class="panel">
    <div class="panel-h"><div><h2>Content plan</h2><span class="note">Review drafts here. Approving does not publish anything.</span></div><div class="actions"><button class="btn" type="button" data-act="ai-social">Draft social post with AI</button><button class="btn pri" type="button" data-act="new-content">New draft</button></div></div>
    <div class="tw"><table>
      <thead><tr><th>Date</th><th>Channel</th><th>Piece</th><th>Purpose</th><th>Status</th></tr></thead>
      <tbody>${list.length ? list.map((i) => `<tr><td class="t">${esc(fmtWhen(i))}</td><td>${chanCell(i.channel)}</td>
        <td><b class="strong">${esc(i.title)}</b>${i.owner ? `<span class="sub">Owner: ${esc(i.owner)}</span>` : ""}${draftText(i)}${itemButtons(i)}</td>
        <td>${i.label ? `<span class="purpose">${esc(i.label)}</span>` : '<span class="muted">—</span>'}</td><td>${itemStatus(i)}</td></tr>`).join("")
        : '<tr><td colspan="5" class="empty-cell">No content drafts. Use <b>New draft</b> to plan a post.</td></tr>'}</tbody>
    </table></div>
  </section>
  <section class="panel">
    <div class="panel-h"><h2>Content made for one lead</h2><button class="btn" type="button" data-view="leads">Open leads</button></div>
    <div class="panel-b inline-stat"><div><span class="num big">${roomCount}</span><div class="note">lead rooms with an outline written</div></div>
      <p class="note">Public content builds trust and brings enquiries. Each serious lead then gets a private room outline: their project, and what Voxel1 would do for them. Rooms are internal; nothing is shared with the client from this app.</p></div>
  </section>
  <section class="panel"><div class="panel-h"><h2>Rules for all content</h2></div><div class="panel-b"><div class="rules">${CONTENT_RULES.map((r) => `<span>${esc(r)}</span>`).join("")}</div></div></section>`;
}

/* ---------- lead room ---------- */
function historyText(h, serviceId) {
  const d = h.detail || {};
  const note = d.note ? ` “${esc(d.note)}”` : "";
  switch (h.event) {
    case "discovered": return `Added by ${esc(d.source || "search")}.`;
    case "found_again": return `Found again by ${esc(d.source || "search")}.`;
    case "interest": return `Interest: ${esc(d.from)} → ${esc(d.to)}.${note}`;
    case "review": return d.to === "active" ? `Restored to active leads.${note}` : `${d.to === "rejected" ? "Rejected" : "Archived"}: ${esc(reasonLabel(serviceId, d.reason))}.${note}`;
    case "lead_room_updated": return `Room saved: stage ${esc(STAGE_NAMES[d.stage] || d.stage)}${d.owner ? `, owner ${esc(d.owner)}` : ""}.`;
    case "created": return `${d.kind === "task" ? "Task" : "Draft"} added: ${esc(d.title)}.`;
    case "edited": return `Edited: ${esc(d.title)}.`;
    case "ai_drafted": return `AI wrote a ${esc((d.purpose || "").toLowerCase())} draft (${esc(d.model)}): ${esc(d.title)}. Waiting for review.`;
    case "ai_output_drafted": return `AI prepared a ${esc(d.kind)} draft (${esc(d.model)}): ${esc(d.title)}. Waiting for review.`;
    case "room_draft_applied": return `Approved outline applied to the internal room: ${esc(d.title)}.`;
    case "rhythm_output_created": return `${d.model ? `AI (${esc(d.model)}) prepared` : "Prepared"} a reviewable ${esc(d.kind)}: ${esc(d.title)}.`;
    case "approve": return `Approved draft: ${esc(d.title)} (not sent).`;
    case "reject": return `${d.kind === "task" ? "Skipped" : "Rejected"}: ${esc(d.title)}.`;
    case "complete": return d.kind === "task" ? `Done: ${esc(d.title)}.` : `Recorded as posted/sent: ${esc(d.title)}.`;
    case "reopen": return `Reopened: ${esc(d.title)}.`;
    default: return esc(h.event);
  }
}

function room(s, l) {
  const d = detail(l.id);
  const steps = S.growth.items.filter((i) => i.lead_id === l.id).sort((a, b) => (a.state === "pending" ? 0 : 1) - (b.state === "pending" ? 0 : 1) || byDue(a, b));
  const active = (l.review_decision || "active") === "active";
  const web = safeUrl(l.website), source = safeUrl(l.source_url);
  const apollo = l.source_id?.startsWith("apollo/");
  const sourceLabel = apollo ? "Apollo company record (website)" : l.source_id?.startsWith("manual/") ? "Entered manually" : /^(node|way|relation)\//.test(l.source_id || "") ? "OpenStreetMap record" : "Source";
  const outline = d.room_notes.split("\n").map((x) => x.trim()).filter(Boolean);
  const history = S.history[l.id];
  return `<section class="panel">
    <div class="panel-h"><div><span class="lbl">Lead room</span><h2 class="room-title">${esc(l.company)} <span class="muted" style="font-weight:400">· ${esc([l.city, l.country].filter(Boolean).join(", ") || "Location unknown")}</span></h2></div>
      <div class="actions">${interestBadge(l)}<button class="btn" type="button" data-act="back">Back to leads</button></div></div>
    <div class="stepper" role="group" aria-label="Sales stage">${STAGES.map((t, i) => `<button type="button" data-stage="${t}" class="${i <= STAGES.indexOf(d.stage) ? (d.stage === "won" ? "won on" : "on") : ""} ${t === d.stage ? "cur" : ""}" aria-pressed="${t === d.stage}"><i></i><span>${STAGE_NAMES[t]}</span></button>`).join("")}</div>
    ${d.stage === "lost" ? '<p class="panel-b note">Marked as lost. Choose a stage above to reopen it.</p>' : ""}
  </section>
  <div class="grid2">
    <section class="panel"><div class="panel-h"><h2>Next steps</h2><div class="actions"><button class="btn" type="button" data-act="lead-task">Add task</button><button class="btn" type="button" data-act="lead-draft">Draft message</button>${active ? '<button class="btn" type="button" data-act="ai-room">Draft room with AI</button><button class="btn pri" type="button" data-act="ai-draft">Write draft with AI</button>' : ""}</div></div>
      ${steps.length ? steps.map((i) => `<div class="ns"><span class="ck ${i.state === "done" || i.state === "approved" ? "done" : i.kind !== "task" && i.state === "pending" ? "you" : ""}">${i.state === "done" || i.state === "approved" ? CHECK : ""}</span>
        <div><b>${esc(i.title)}</b><span class="when">${esc(fmtWhen(i))} · ${i.kind === "task" ? esc(i.label || "Task") : esc(i.channel) + " draft"}</span> ${itemStatus(i)}${draftText(i)}${itemButtons(i)}</div>${who(i.owner)}</div>`).join("")
        : '<p class="panel-b note">No next steps yet. Add a task or draft a message for this lead.</p>'}
    </section>
    <div class="stack">
      <section class="panel"><div class="panel-h"><h2>Room outline</h2><span class="note">Private to your team</span></div><div class="panel-b">
        <div class="preview"><div class="pv-h"><b>VOXEL1</b><span>Prepared for ${esc(l.company)}</span></div>
          <div class="pv-b">${outline.length ? outline.map((x, i) => `<div class="pv-s"><i>${i + 1}</i><span>${esc(x)}</span></div>`).join("") : '<div class="pv-s"><span>No outline yet. Write one line per section below.</span></div>'}</div></div>
        <p class="eng">Not shared. This app has no client-facing room page and does not track opens.</p></div></section>
      <section class="panel"><div class="panel-h"><h2>Stage, owner &amp; outline</h2></div>
        <form class="panel-b form-grid" id="room-form">
          <label class="field">Stage<select name="stage">${[...STAGES, "lost"].map((t) => `<option value="${t}" ${t === d.stage ? "selected" : ""}>${STAGE_NAMES[t]}</option>`).join("")}</select></label>
          <label class="field">Owner<input name="owner" maxlength="120" value="${esc(d.owner)}" placeholder="e.g. Delivery head"></label>
          <label class="field full"><span class="flabel">Room outline <span class="optional">(one section per line)</span></span><textarea name="room_notes" rows="4" maxlength="10000">${esc(d.room_notes)}</textarea></label>
          <div class="full actions end"><button class="btn pri" type="submit">Save room</button></div>
        </form></section>
      <section class="panel"><div class="panel-h"><h2>Company &amp; review</h2></div><div class="panel-b facts">
        <div><span class="lbl">Why listed</span><p>${esc(l.match_reason || "No reason recorded. Saved before the app recorded why candidates were listed; verify fit on the website.")}</p>
          <p class="muted">${l.ai_screened ? (l.ai_reason ? `Gemini${l.ai_model ? ` (${esc(l.ai_model)})` : ""}${l.screened_at ? `, ${esc(fmtDate(l.screened_at))}` : ""}: “${esc(l.ai_reason)}” AI judgement, not proof of need.` : "Gemini marked it a plausible buyer earlier; its reason was not recorded.") : "Not screened by Gemini."}</p></div>
        <div><span class="lbl">Source</span><p>${source ? `<a href="${esc(source)}" target="_blank" rel="noopener noreferrer">${sourceLabel} ↗</a>` : esc(sourceLabel)}${web && web !== source ? ` · <a href="${esc(web)}" target="_blank" rel="noopener noreferrer">Website ↗</a>` : ""}</p><p class="muted">${esc(l.category && l.category !== "business" ? l.category : "Industry unconfirmed")}</p></div>
        <div><span class="lbl">Contact</span>${l.contact_name ? `<p><b>${esc(l.contact_name)}</b>${l.contact_title ? `<br><span class="muted">${esc(l.contact_title)}</span>` : ""}${l.contact_name.includes("*") ? '<br><span class="muted">Name partly hidden by provider</span>' : ""}</p>` : '<p class="muted">Decision-maker not found</p>'}
          ${l.email ? `<p><span class="muted">${apollo ? "Apollo email status: verified" : "Email (unverified)"}</span><br><a href="mailto:${encodeURIComponent(l.email)}">${esc(l.email)}</a></p>${domainMismatch(l) ? '<p class="blocked">This email’s domain doesn’t match the company website. The contact may not work here; confirm before using it. AI drafts won’t address this person by name.</p>' : ""}` : '<p class="muted">Work email unavailable</p>'}
          ${l.phone ? `<p><span class="muted">${apollo ? "Company phone, not a direct line" : "Phone (unverified)"}</span><br><a href="tel:${encodeURIComponent(l.phone)}">${esc(l.phone)}</a></p>` : ""}</div>
        ${active ? `<div><span class="lbl">Interest (after a real response)</span><select id="interest" aria-label="Interest status"><option value="new" ${l.status === "new" ? "selected" : ""}>Needs review</option><option value="interested" ${l.status === "interested" ? "selected" : ""}>Interested</option><option value="not_interested" ${l.status === "not_interested" ? "selected" : ""}>Not interested</option></select>${l.notes ? `<p class="muted">“${esc(l.notes)}”</p>` : ""}</div>
          <div class="actions"><button class="btn" type="button" data-act="review" data-decision="rejected">Reject</button><button class="btn" type="button" data-act="review" data-decision="archived">Archive</button></div>`
          : `<div><span class="lbl">${l.review_decision === "rejected" ? "Rejected" : "Archived"}</span><p>${esc(reasonLabel(s.id, l.review_reason))}${l.reviewed_at ? `, ${esc(fmtDate(l.reviewed_at))}` : ""}</p>${l.review_note ? `<p class="muted">“${esc(l.review_note)}”</p>` : ""}<p class="muted">Kept with its history. Later searches skip it.</p></div>
          <div class="actions"><button class="btn pri" type="button" data-act="restore">Restore to active</button></div>`}
      </div></section>
      <section class="panel"><div class="panel-h"><h2>Done so far</h2></div><div class="hist">${!history ? '<div><span class="d"></span><span class="muted">Loading history…</span></div>' : history.length ? history.map((h) => `<div><span class="d">${esc(fmtDate(h.created_at))}</span><span>${historyText(h, s.id)}</span></div>`).join("") : '<div><span class="d"></span><span class="muted">No history recorded yet. Events are recorded from this version onward.</span></div>'}</div></section>
    </div>
  </div>`;
}

/* ---------- approvals ---------- */
function approvalRows() {
  return S.growth.items.filter((i) => i.kind !== "task" && (i.state === "pending" || i.state === "approved")).map((i) => {
    const l = i.lead_id ? lead(i.lead_id) : null;
    const stage = l ? detail(l.id).stage : "";
    const pri = i.kind !== "content" ? (["proposal", "negotiation"].includes(stage) || l?.status === "interested" ? "High" : "Medium") : "Low";
    const why = pri === "High" ? (l?.status === "interested" ? "Interested lead" : "Deal at proposal stage") : i.kind === "room" ? "Internal room draft" : i.kind === "outreach" ? "Message to a lead" : "Planned content";
    return { i, l, pri, why: i.kind === "brief" ? "Internal research / planning" : why, type: i.kind === "brief" ? "Brief" : i.kind === "room" ? "Room" : i.kind === "outreach" ? "Outreach" : "Content" };
  }).sort((a, b) => ({ High: 0, Medium: 1, Low: 2 })[a.pri] - ({ High: 0, Medium: 1, Low: 2 })[b.pri] || byDue(a.i, b.i));
}

function outlookPage() {
  const o = S.growth.outlook;
  if (!o) return '<section class="panel"><div class="panel-b">The Outlook server update is not ready. Refresh after deployment.</div></section>';
  return `<div class="ph"><div><h1>Outlook email</h1><p>Sending account: ${esc(o.sender)}</p></div></div>
  <section class="panel"><div class="panel-b"><h2>${o.connected ? "Outlook connected" : "Connect your Outlook account"}</h2>
    ${o.missing.length ? `<p class="blocked">Microsoft app setup required on the hosting server: ${o.missing.map(esc).join(", ")}. <a href="/outlook-setup" target="_blank" rel="noopener">Open setup instructions</a> for your Microsoft 365 administrator. No password is needed in this app.</p>` : ""}
    <p>${o.connected ? (o.tested ? "Microsoft accepted the self-test. Review your Inbox and Sent Items before lead outreach." : "Send a test email to your own address before queuing lead outreach.") : "Sign in as " + esc(o.sender) + " and allow this app to send mail on your behalf. Existing approved drafts stay unsent until you select Send with Outlook."}</p>
    <div class="actions"><button class="btn pri" data-act="outlook-connect" ${o.missing.length ? "disabled" : ""}>${o.connected ? "Reconnect Outlook" : "Connect Outlook"}</button>${o.connected ? '<button class="btn" data-act="outlook-test">Send test email to myself</button><button class="btn" data-act="outlook-disconnect">Disconnect</button>' : ""}<button class="btn" data-act="refresh-jobs">Refresh status</button></div>
    <p class="note">Queued lead emails are submitted during 09:00–17:00 weekdays in the chosen recipient timezone, up to five per service per UTC day. Paused workspaces wait. Microsoft acceptance does not confirm delivery. Failed or uncertain submissions are never retried automatically.</p></div>
    <div class="tw"><table><thead><tr><th>Recipient</th><th>Status</th><th>Result</th><th>Action</th></tr></thead><tbody>${o.queue.map((q) => `<tr><td>${esc(q.recipient)}<span class="sub">${esc(q.timezone)}</span></td><td>${esc(q.state)}</td><td>${esc(q.result || "Waiting for a recipient working-hour window")}</td><td>${q.state === "queued" ? `<button class="btn" data-act="outlook-cancel" data-queue="${esc(q.id)}">Cancel</button>` : ""}</td></tr>`).join("") || '<tr><td colspan="4" class="empty-cell">No email submissions yet.</td></tr>'}</tbody></table></div></section>`;
}

function approvalsPage() {
  const f = S.af, all = approvalRows();
  const open = all.filter((a) => a.i.state === "pending");
  const list = all.filter((a) => (f.show || a.i.state === "pending") && (f.p === "all" || a.pri === f.p) && (f.s === "all" || a.i.service === f.s) && (f.t === "all" || a.type === f.t));
  const cnt = (fn) => open.filter(fn).length;
  const chips = (key, opts) => opts.map(([v, label, n]) => `<button class="fchip" type="button" data-af="${key}:${v}" aria-pressed="${f[key] === v}">${esc(label)}${n !== undefined ? ` <span class="num">${n}</span>` : ""}</button>`).join("");
  return `<div class="crumb">Growth Engine <span>/</span> Approvals</div>
  <div class="ph"><div class="ph-l"><div><h1>Approvals</h1><p>Drafts waiting for a decision across Training and BIM Services. Approval records your decision. Choose Send with Outlook separately to queue an approved email.</p></div></div></div>
  <section class="kpis four">
    <div class="kpi ${open.length ? "warn" : ""}"><span>Waiting</span><b>${open.length}</b><span>across ${new Set(open.map((a) => a.i.service)).size} services</span></div>
    <div class="kpi"><span>High priority</span><b>${cnt((a) => a.pri === "High")}</b><span>interested leads and proposals</span></div>
    <div class="kpi"><span>Medium</span><b>${cnt((a) => a.pri === "Medium")}</b><span>other messages to leads</span></div>
    <div class="kpi"><span>Low</span><b>${cnt((a) => a.pri === "Low")}</b><span>content drafts</span></div>
  </section>
  <section class="panel">
    <div class="filters">
      <div class="fgroup"><span class="lbl">Priority</span>${chips("p", [["all", "All"], ["High", "High", cnt((a) => a.pri === "High")], ["Medium", "Medium", cnt((a) => a.pri === "Medium")], ["Low", "Low", cnt((a) => a.pri === "Low")]])}</div>
      <div class="fgroup"><span class="lbl">Service</span>${chips("s", [["all", "All"], ...SERVICES.map((s) => [s.id, s.name, cnt((a) => a.i.service === s.id)])])}</div>
      <div class="fgroup"><span class="lbl">Type</span>${chips("t", [["all", "All"], ["Outreach", "Messages", cnt((a) => a.type === "Outreach")], ["Room", "Lead rooms", cnt((a) => a.type === "Room")], ["Brief", "Briefs", cnt((a) => a.type === "Brief")], ["Content", "Content", cnt((a) => a.type === "Content")]])}</div>
      <label class="fshow"><input type="checkbox" id="show-approved" ${f.show ? "checked" : ""}> Show approved</label>
    </div>
    <div class="tw"><table>
      <thead><tr><th>Priority</th><th>Service</th><th>Type</th><th>What to approve</th><th>When</th></tr></thead>
      <tbody>${list.length ? list.map(({ i, l, pri, why, type }) => { const s = svc(i.service);
        return `<tr><td><span class="prio ${pri}">${pri}</span><span class="sub">${esc(why)}</span></td>
          <td><span class="chan"><span class="av sm av-${s.id === "training" ? "train" : s.id}">${s.code}</span>${esc(s.name)}</span></td>
          <td><span class="purpose">${type}</span></td>
          <td><b class="strong">${esc(i.title)}</b><span class="sub">${esc(i.channel)}${l ? ` · ${esc(l.company)}` : ""}</span>${draftText(i)}${itemButtons(i)}${l ? `<div class="actions"><button class="btn" type="button" data-goto="${i.service}:${l.id}">Open lead</button></div>` : ""}</td>
          <td class="t">${esc(fmtWhen(i))}</td></tr>`; }).join("")
        : '<tr><td colspan="5" class="empty-cell">Nothing matches these filters.</td></tr>'}</tbody>
    </table></div>
  </section>`;
}

/* ---------- render ---------- */
function main() {
  if (S.page === "outlook") { $("main").innerHTML = outlookPage(); return; }
  if (S.page === "approvals") { $("main").innerHTML = approvalsPage(); return; }
  const s = svc(S.sel);
  let h = header(s);
  const l = S.lead ? lead(S.lead) : null;
  if (l) { $("main").innerHTML = h + room(s, l); return; }
  const n = pendingDrafts(s.id).length;
  h += `<div class="tabs" role="tablist">
    <button class="tab" role="tab" type="button" data-view="today" aria-selected="${S.view === "today"}">Daily rhythm</button>
    <button class="tab" role="tab" type="button" data-view="leads" aria-selected="${S.view === "leads"}">Leads <span class="cnt">${activeLeads(s.id).length}</span></button>
    <button class="tab" role="tab" type="button" data-view="content" aria-selected="${S.view === "content"}">Content <span class="cnt${n ? " warn" : ""}">${items(s.id, "content").length}</span></button>
  </div>`;
  h += S.view === "today" ? rhythm(s) : S.view === "leads" ? leads(s) : content(s);
  $("main").innerHTML = h;
}

function render() {
  if (!S.growth) return;
  const focus = document.activeElement?.id;
  const caret = focus === "lead-q" ? document.activeElement.selectionStart : null;
  topbar(); side(); main();
  if (focus === "lead-q" && $("lead-q")) { $("lead-q").focus(); $("lead-q").setSelectionRange(caret, caret); }
}

/* ---------- editor dialog ---------- */
function field(f) {
  const id = `f-${f.name}`;
  const req = f.required ? "required" : "";
  const label = `<span class="flabel">${esc(f.label)}${f.optional ? ' <span class="optional">(optional)</span>' : ""}</span>`;
  if (f.type === "rhythm") return `<fieldset class="field full rhythm-set"><legend class="flabel">${esc(f.label)}</legend>${f.value.map((a, i) => `<label class="rhythm-row"><input type="checkbox" name="rhythm_on_${i}" ${a.on ? "checked" : ""}><input type="time" name="rhythm_time_${i}" value="${esc(a.time)}" required><span>${esc(a.title)}</span></label>`).join("")}</fieldset>`;
  if (f.type === "textarea") return `<label class="field ${f.full !== false ? "full" : ""}" for="${id}">${label}<textarea id="${id}" name="${f.name}" rows="${f.rows || 5}" maxlength="${f.max || 10000}" ${req}>${esc(f.value || "")}</textarea></label>`;
  if (f.type === "select") return `<label class="field ${f.full ? "full" : ""}" for="${id}">${label}<select id="${id}" name="${f.name}" ${req}>${f.options.map(([v, t]) => `<option value="${esc(v)}" ${String(v) === String(f.value ?? "") ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></label>`;
  return `<label class="field ${f.full ? "full" : ""}" for="${id}">${label}<input id="${id}" name="${f.name}" type="${f.type || "text"}" value="${esc(f.value ?? "")}" ${f.max ? `maxlength="${f.max}"` : ""} ${f.min !== undefined ? `min="${f.min}"` : ""} ${f.placeholder ? `placeholder="${esc(f.placeholder)}"` : ""} ${req}></label>`;
}

function openEditor({ title, help = "", fields, submitLabel = "Save", submit }) {
  S.editor = { submit, fields };
  $("editor-title").textContent = title;
  $("editor-help").textContent = help;
  $("editor-help").hidden = !help;
  $("editor-fields").innerHTML = fields.map(field).join("");
  $("editor-submit").textContent = submitLabel;
  $("editor-error").hidden = true;
  $("editor").showModal();
  $("editor-fields").querySelector("input,textarea,select")?.focus();
}

function itemEditor(kind, service, existing = null, leadId = null) {
  const c = S.growth.choices;
  const labels = c.labels[kind];
  const leadOptions = [["", "No lead"], ...activeLeads(service).map((l) => [l.id, l.company])];
  const v = existing || { title: "", body: "", owner: kind === "task" ? "You" : "", channel: kind === "task" ? "Internal" : kind === "outreach" ? "Email" : "LinkedIn", label: "", due: today(), due_time: "", lead_id: leadId };
  const name = kind === "brief" ? "internal brief" : kind === "room" ? "room draft" : kind === "task" ? "task" : kind === "content" ? "content draft" : "message draft";
  const fields = [
    { name: "title", label: kind === "task" ? "Activity" : kind === "content" ? "Piece title" : "Subject / purpose", value: v.title, required: true, max: 200, full: true },
  ];
  if (kind !== "task") fields.push({ name: "body", label: "Draft text", type: "textarea", value: v.body, rows: 7, max: 10000 });
  fields.push(
    { name: "label", label: kind === "task" ? "Type" : "Purpose", type: "select", options: [["", "—"], ...labels.map((x) => [x, x])], value: v.label },
    { name: "channel", label: "Channel", type: "select", options: c.channels.map((x) => [x, x]), value: v.channel },
    { name: "due", label: "Date", type: "date", value: v.due, optional: true },
    { name: "due_time", label: "Time", type: "time", value: v.due_time, optional: true },
    { name: "owner", label: "Owner", value: v.owner, max: 120, placeholder: "e.g. You, Delivery head", optional: true },
    { name: "lead_id", label: "Lead", type: "select", options: leadOptions, value: v.lead_id ?? "" },
  );
  if (kind === "task") fields.push({ name: "body", label: "Notes", type: "textarea", value: v.body, rows: 3, max: 10000, optional: true });
  openEditor({
    title: existing ? `Edit ${name}` : `New ${name}`,
    help: kind === "task" ? "" : existing && existing.state !== "pending" ? "Saving changes returns this draft to “Needs approval”." : "Approve drafts here, then queue approved email with Outlook or send/post manually.",
    fields,
    submitLabel: existing ? "Save changes" : `Add ${name}`,
    submit: (values) => {
      const body = { ...values, lead_id: values.lead_id ? Number(values.lead_id) : null };
      return existing
        ? api(`/api/growth/items/${existing.id}`, { method: "PATCH", body: JSON.stringify({ ...body, revision: existing.revision }) })
        : api("/api/growth/items", { method: "POST", body: JSON.stringify({ ...body, service, kind }) });
    },
  });
}

/* ---------- actions ---------- */
async function itemAction(action, id) {
  const i = item(id);
  if (!i) return;
  if (action === "graphic-png") {
    let source;
    try {
      const response = await fetch(`/api/growth/graphics/${i.id}.svg?revision=${i.revision}`);
      if (!response.ok) throw new Error("Could not load the graphic draft. Refresh and sign in again if necessary.");
      source = URL.createObjectURL(await response.blob());
      const picture = new Image(); picture.src = source; await picture.decode();
      const canvas = document.createElement("canvas"); canvas.width = 1080; canvas.height = 1080;
      canvas.getContext("2d").drawImage(picture, 0, 0, 1080, 1080);
      const png = await new Promise((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!png) throw new Error("PNG export failed. Use Editable SVG instead.");
      const target = URL.createObjectURL(png), link = document.createElement("a");
      link.href = target; link.download = `voxel1-${i.id}-graphic-draft.png`; link.click();
      setTimeout(() => URL.revokeObjectURL(target), 10000);
    } catch (error) { notice(error.message, true); }
    finally { if (source) URL.revokeObjectURL(source); }
    return;
  }
  if (action === "apply-room") {
    if (!confirm("Apply this approved draft to the internal room outline? Review any existing notes first. It will not be shared externally.")) return;
    await run(() => api("/api/growth/apply-room", { method: "POST", body: JSON.stringify({ item_id: i.id, revision: i.revision, room_updated_at: detail(i.lead_id).updated_at || "" }) }), (r) => r.message).catch(() => {});
    return;
  }
  if (action === "outlook-send") {
    const o = S.growth.outlook;
    if (!o?.connected || !o.tested) { S.page = "outlook"; render(); return; }
    const l = lead(i.lead_id);
    if (!l?.email) { notice("This lead has no business email. Review the contact first.", true); return; }
    const zones = { "Saudi Arabia": "Asia/Riyadh", "UAE": "Asia/Dubai", "India": "Asia/Kolkata", "Singapore": "Asia/Singapore" };
    openEditor({ title: "Send approved email with Outlook", help: `From ${o.sender} to ${l.email}. Review the approved text before queuing. The server submits during 09:00–17:00 weekdays in the chosen timezone. An approved draft is sent only when you explicitly queue it here.`,
      fields: [
        { name: "recipient", label: "Confirm recipient email", value: l.email, required: true },
        { name: "timezone", label: "Recipient timezone (e.g. Asia/Riyadh or America/New_York)", value: zones[l.country] || "", required: true, full: true },
        { name: "permission", label: "I have verified permission to contact this recipient", type: "select", options: [["no", "Not confirmed"], ["yes", "Yes, permission verified"]], value: "no", required: true, full: true },
      ], submitLabel: "Queue approved email",
      submit: (v) => api("/api/outlook/queue", { method: "POST", body: JSON.stringify({ item_id: i.id, revision: i.revision, recipient: v.recipient, timezone: v.timezone, permission_confirmed: v.permission === "yes" }) }),
    }); return;
  }
  if (action === "toggle") { S.open[id] = !S.open[id]; render(); return; }
  if (action === "edit") { itemEditor(i.kind, i.service, i); return; }
  if (action === "copy") {
    try { await navigator.clipboard.writeText(i.body); notice("Draft text copied. Paste it into your own email or social account to send it."); }
    catch { S.open[id] = true; render(); notice("Copying is blocked in this browser. The text is shown so you can select and copy it.", true); }
    return;
  }
  if (action === "download") {
    const blob = new Blob([`${i.title}\n\n${i.body}\n`], { type: "text/plain;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${i.title.replace(/[^\w\- ]+/g, "").trim().slice(0, 60) || "draft"}.txt`;
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    return;
  }
  const messages = {
    approve: "Draft approved. Choose Send with Outlook or send manually; approval alone sends nothing.",
    reject: i.kind === "task" ? "Task skipped." : "Draft rejected.",
    complete: i.kind === "task" ? "Task marked done." : `Recorded as ${i.kind === "content" ? "posted" : "sent"} by you.`,
    reopen: "Reopened.",
  };
  if (action === "complete" && i.kind !== "task" && !confirm(`Record “${i.title}” as ${i.kind === "content" ? "posted" : "sent"}? Only do this after you have actually ${i.kind === "content" ? "posted" : "sent"} it yourself.`)) return;
  await run(() => api(`/api/growth/items/${id}`, { method: "PATCH", body: JSON.stringify({ action, revision: i.revision }) }), messages[action]).catch(() => {});
}

async function openLead(serviceId, leadId) {
  S.page = "service"; S.sel = serviceId; S.lead = leadId;
  render();
  window.scrollTo({ top: 0 });
  try { S.history[leadId] = await api(`/api/services/${serviceId}/leads/${leadId}/history`); }
  catch (error) { S.history[leadId] = []; notice(error.message, true); }
  render();
}

function openIcp() {
  const icp = S.icp[S.sel], form = $("icp-form");
  for (const name of ["name", "notes", "employee_min", "employee_max", "titles", "keywords", "exclusions", "goal"]) form.elements[name].value = icp[name] ?? "";
  form.querySelectorAll('[name="categories"]').forEach((b) => { b.checked = (icp.categories || []).includes(b.value); });
  const fixed = ["USA", "UAE", "Saudi Arabia", "India", "Singapore"];
  form.querySelectorAll('[name="countries"]').forEach((b) => { b.checked = icp.countries.includes(b.value); });
  form.elements.other_countries.value = icp.countries.filter((c) => !fixed.includes(c)).join(", ");
  $("icp-title").textContent = `Edit ICP: ${svc(S.sel).name}`;
  $("icp-updated").textContent = icp.updated_at ? `Last saved ${new Date(icp.updated_at).toLocaleString()}` : "";
  $("icp-error").hidden = true;
  $("icp-dialog").showModal();
}

function icpPayload() {
  const form = $("icp-form");
  const chosen = [...form.querySelectorAll('[name="countries"]:checked')].map((b) => b.value);
  const other = form.elements.other_countries.value.split(",").map((x) => x.trim()).filter(Boolean);
  return {
    name: form.elements.name.value.trim(), notes: form.elements.notes.value.trim(),
    categories: [...form.querySelectorAll('[name="categories"]:checked')].map((b) => b.value),
    countries: [...chosen, ...other], employee_min: form.elements.employee_min.value, employee_max: form.elements.employee_max.value,
    titles: form.elements.titles.value.trim(), keywords: form.elements.keywords.value.trim(), exclusions: form.elements.exclusions.value.trim(), goal: form.elements.goal.value.trim(),
  };
}

async function search() {
  const id = S.sel, icp = S.icp[id];
  let body = {};
  if (icp.search_mode === "Apollo + Brave") {
    S.budget = await api("/api/budget");
    const b = S.budget;
    if (!b.allowed) { render(); notice(`Search not started: ${b.blocked_reasons.join(" ")}`, true); return; }
    const counts = Object.entries({ apollo: "Apollo", brave: "Brave", gemini: "Gemini" }).filter(([k]) => b.estimate[k]).map(([k, n]) => `${n} ${b.estimate[k]}`).join(", ");
    if (!confirm(`Search ${svc(id).name} companies in ${icp.countries.join(", ")}?\n\nThis may send up to: ${counts} provider requests. Providers may charge credits for them.`)) { notice("Search cancelled. No provider requests were sent."); return; }
    body = { confirmed: true, estimate: b.estimate };
  } else if (!confirm(`Search OpenStreetMap city samples for ${svc(id).name}? This uses the free public map service.`)) return;
  notice("Searching companies and checking public website evidence. This can take a few minutes.");
  await run(() => api(`/api/services/${id}/discover`, { method: "POST", body: JSON.stringify(body) }), (r) => {
    const parts = [`${r.source}: found ${r.found} candidate${r.found === 1 ? "" : "s"}, ${r.added} new.`];
    if (r.skipped_reviewed) parts.push(`Skipped ${r.skipped_reviewed} rejected or archived.`);
    if (r.warnings?.length) parts.push(`Some checks failed: ${r.warnings.join(" ")}`);
    if (r.usage) parts.push(`Requests sent: ${Object.entries(r.usage.actual).filter(([, n]) => n).map(([k, n]) => `${k} ${n}`).join(", ") || "none"}.`);
    return parts.join(" ");
  }).catch((error) => { if (error.budget) { S.budget = error.budget; render(); } });
}

function addCompany() {
  openEditor({
    title: `Add a company to ${svc(S.sel).name}`,
    help: "For companies your team found itself. No provider is contacted.",
    fields: [
      { name: "company", label: "Company", required: true, max: 200, full: true },
      { name: "website", label: "Website", type: "url", placeholder: "https://", max: 500, optional: true, full: true },
      { name: "category", label: "Industry", max: 100, optional: true },
      { name: "city", label: "City", max: 100, optional: true },
      { name: "country", label: "Country", max: 100, optional: true },
      { name: "contact_name", label: "Contact name", max: 200, optional: true },
      { name: "contact_title", label: "Contact title", max: 200, optional: true },
      { name: "email", label: "Business email", type: "email", max: 254, optional: true },
      { name: "phone", label: "Phone", max: 100, optional: true },
    ],
    submitLabel: "Add company",
    submit: (values) => api("/api/growth/companies", { method: "POST", body: JSON.stringify({ ...values, service: S.sel }) }),
  });
}

function reviewEditor(l, decision) {
  const reasons = Object.entries(S.icp[l.service].review_reasons).filter(([code]) => decision === "archived" || code !== "no_current_need");
  openEditor({
    title: `${decision === "rejected" ? "Reject" : "Archive"} ${l.company}`,
    help: `${decision === "rejected" ? "Rejected" : "Archived"} leads leave the active list and later searches skip them. Nothing is deleted; you can restore it.`,
    fields: [
      { name: "reason", label: "Reason", type: "select", required: true, options: [["", "Choose a reason"], ...reasons], value: decision === "archived" ? "no_current_need" : "", full: true },
      { name: "notes", label: "Note", type: "textarea", rows: 3, max: 500, optional: true },
    ],
    submitLabel: decision === "rejected" ? "Reject" : "Archive",
    submit: (values) => api(`/api/services/${l.service}/leads/${l.id}/review`, { method: "PATCH", body: JSON.stringify({ decision, ...values }) }),
  });
}

async function act(el) {
  const d = el.dataset;
  const s = svc(S.sel);
  if (el.id === "outlook") { S.page = "outlook"; S.lead = null; render(); return; }
  if (el.id === "approvals") { S.page = "approvals"; S.lead = null; window.scrollTo({ top: 0 }); render(); return; }
  if (el.id === "theme") {
    const dark = $("theme").textContent === "Dark mode";
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try { localStorage.setItem("voxel1-theme", dark ? "dark" : "light"); } catch { /* preference not saved */ }
    render(); return;
  }
  if (el.id === "pause-all") {
    const on = !settings("global").paused;
    if (on && !confirm("Pause both workspaces? New searches, approvals and task completion are blocked until you resume. A search already running is not cancelled.")) return;
    await run(() => api("/api/growth/settings/global", { method: "PUT", body: JSON.stringify({ paused: on }) }), on ? "Both workspaces paused." : "Workspaces resumed.").catch(() => {});
    return;
  }
  if (d.close) { $(d.close).close(); return; }
  if (d.sel) { S.page = "service"; S.sel = d.sel; S.lead = null; S.view = "today"; S.q = ""; S.lf = "active"; render(); return; }
  if (d.view) { S.view = d.view; S.lead = null; render(); return; }
  if (d.goto) { const [sid, lid] = d.goto.split(":"); openLead(sid, Number(lid)); return; }
  if (d.lead) { openLead(S.sel, Number(d.lead)); return; }
  if (d.lf) { S.lf = d.lf; render(); return; }
  if (d.af) { const [k, v] = d.af.split(":"); S.af[k] = v; render(); return; }
  if (d.item) { await itemAction(d.item, Number(d.id)); return; }
  if (d.stage) {
    const det = detail(S.lead);
    await run(() => api(`/api/growth/leads/${S.lead}`, { method: "PUT", body: JSON.stringify({ service: S.sel, stage: d.stage, owner: det.owner, room_notes: det.room_notes }) }), `Stage set to ${STAGE_NAMES[d.stage]}.`).catch(() => {});
    return;
  }
  switch (d.act) {
    case "review-output": {
      const output = item(Number(d.output));
      if (!output) { notice("Refresh to load this output."); return; }
      S.sel = output.service; S.open[output.id] = true;
      if (output.kind === "brief") { S.page = "approvals"; S.lead = null; S.af = { p: "all", s: output.service, t: "Brief", show: true }; }
      else { S.page = "service"; S.lead = output.lead_id || null; S.view = output.kind === "content" ? "content" : "today"; }
      render(); return;
    }
    case "outlook-connect": {
      try {
        const result = await api("/api/outlook/connect", { method: "POST", body: "{}" });
        window.location.assign(result.url);
      } catch (error) { notice(error.message, true); }
      return;
    }
    case "outlook-test":
      if (confirm(`Send a test email from ${S.growth.outlook.sender} to the same address?`)) await run(() => api("/api/outlook/test", { method: "POST", body: "{}" }), (r) => r.message).catch(() => {});
      return;
    case "outlook-disconnect":
      if (confirm("Disconnect Outlook and cancel queued emails? A submission already in flight may finish.")) await run(() => api("/api/outlook/disconnect", { method: "POST", body: "{}" }), (r) => r.message).catch(() => {});
      return;
    case "outlook-cancel":
      await run(() => api("/api/outlook/cancel", { method: "POST", body: JSON.stringify({ id: d.queue }) }), (r) => r.message).catch(() => {});
      return;
    case "back": S.lead = null; S.view = "leads"; render(); return;
    case "pause": {
      const on = !settings(s.id).paused;
      await run(() => api(`/api/growth/settings/${s.id}`, { method: "PUT", body: JSON.stringify({ paused: on }) }), on ? `${s.name} paused.` : `${s.name} resumed.`).catch(() => {});
      return;
    }
    case "approvals": S.page = "approvals"; S.lead = null; render(); return;
    case "refresh-jobs": await run(async () => {}, "Results refreshed.").catch(() => {}); return;
    case "retry-draft":
      if (!confirm("Retry this failed draft once? It may use one additional Gemini request. Existing outputs are checked first, daily/monthly caps still apply, and nothing will be sent.")) return;
      await run(() => api("/api/growth/retry-draft", { method: "POST", body: JSON.stringify({ service: d.service, day: d.day, job: d.job, failure_token: d.token, confirmed: true }) }), (r) => r.message).catch(() => {});
      return;
    case "edit-goal":
    case "campaign": {
      const c = S.growth.campaigns.find((c) => c.service === s.id);
      const t = c?.targeting || S.icp[s.id];
      const st = settings(s.id);
      const year = Number(today().slice(0, 4)), month = Number(today().slice(5, 7));
      openEditor({ title: `${s.name}: Sales Goal`, help: "Complete draft rhythm runs the offering's timed research, mapping, room, outreach, partner, follow-up, customer and social workflows. All outputs remain drafts. Each AI attempt and research query uses the existing monthly budgets. Provide real target/partner/customer inputs below; missing inputs are shown instead of invented. Legacy campaigns keep their previous mode until saved. Times are IST.",
        fields: [
          { name: "goal", label: "Quarterly target (won sales)", type: "number", min: 0, value: st.goal, required: true },
          { name: "quarter", label: "Sales quarter (YYYY-Q1 to YYYY-Q4)", value: c?.quarter || `${year}-Q${Math.ceil(month / 3)}`, required: true, max: 7 },
          { name: "strategy", label: "Strategy", type: "textarea", rows: 3, max: 1000, value: st.strategy, full: true },
          { name: "full_rhythm", label: "Complete draft rhythm", type: "select", options: [["no", "Keep current discovery / selected drafting"], ["yes", "Automate all rhythm activities up to review drafts"]], value: c?.full_rhythm ? "yes" : "no", full: true },
          { name: "rhythm", label: "Daily rhythm (tick to run, set the IST time)", type: "rhythm", value: rhythmPlan(s.id) },
          { name: "objective", label: "Service focus and campaign objective", value: c?.objective || t.goal || "", required: true, max: 500, full: true },
          { name: "countries", label: "Target countries (comma separated)", value: t.countries.join(", "), required: true },
          { name: "industries", label: "Industries (comma separated: architecture, construction, engineering, real_estate, education)", value: t.categories.join(", "), required: true, full: true },
          { name: "service_focus", label: "Required service focus (every outbound draft must name it, e.g. Scan-to-BIM; comma-separate only if all phrases are required)", value: c?.service_focus || "", max: 200, optional: true, full: true },
          { name: "keywords", label: "Optional search keywords (discovery and research only; not a drafting requirement)", value: t.keywords, max: 500 },
          { name: "titles", label: "Decision-maker roles", value: t.titles, max: 500 },
          { name: "employee_min", label: "Minimum company size", type: "number", value: t.employee_min, optional: true },
          { name: "employee_max", label: "Maximum company size", type: "number", value: t.employee_max, optional: true },
          { name: "exclusions", label: "Exclude keywords", value: t.exclusions || "", max: 500, optional: true },
          { name: "target_accounts", label: "Named target accounts (one company per line)", type: "textarea", rows: 3, max: 3000, value: c?.target_accounts || "", optional: true, full: true },
          { name: "partner_enabled", label: "Partner activity (optional)", type: "select", options: [["no", "Disabled — partners not required"], ["yes", "Enable partner drafting"]], value: c?.partner_enabled === false ? "no" : "yes" },
          { name: "partner_accounts", label: "PMC / consultant / academic partners (only if partner activity is enabled)", type: "textarea", rows: 2, max: 3000, value: c?.partner_accounts || "", optional: true, full: true },
          { name: "existing_clients", label: "Actual existing clients (names matching saved leads; Training: VITALS/XIM clients)", type: "textarea", rows: 2, max: 3000, value: c?.existing_clients || "", optional: true, full: true },
          { name: "warm_paths", label: "Known introduction paths supplied by your team", type: "textarea", rows: 2, max: 3000, value: c?.warm_paths || "", optional: true, full: true },
          { name: "approved_proof", label: "Approved project proof / trainee story facts for social content", type: "textarea", rows: 3, max: 3000, value: c?.approved_proof || "", optional: true, full: true },
          { name: "proof_consent", label: "Permission to use the supplied proof/story publicly", type: "select", options: [["no", "Not confirmed — educational alternatives only"], ["yes", "Confirmed for the supplied facts"]], value: c?.proof_consent ? "yes" : "no", full: true },
          { name: "start", label: "Start date (IST)", type: "date", value: c?.start || today(), required: true },
          { name: "end", label: "End date (blank = ongoing)", type: "date", value: c?.end || "", optional: true },
          { name: "search_time", label: "Daily discovery (IST)", type: "time", value: c?.search_time || "06:00", required: true },
          { name: "draft_time", label: "Daily drafts (IST)", type: "time", value: c?.draft_time || (s.id === "bim" ? "09:00" : "10:00"), required: true },
          { name: "auto_rooms", label: "AI lead-room drafts", type: "select", options: [["no", "Manual only"], ["yes", "Prepare automatically for screened leads"]], value: c?.auto_rooms ? "yes" : "no" },
          { name: "auto_linkedin", label: "AI LinkedIn text drafts", type: "select", options: [["no", "Manual only"], ["yes", "Prepare daily target automatically"]], value: c?.auto_linkedin ? "yes" : "no" },
          ...["LinkedIn", "Instagram", "Facebook"].map((channel) => ({ name: `posts_${channel}`, label: `${channel} posts per day (0–10)`, type: "number", min: 0, value: c?.content_targets?.[channel] || 0, required: true })),
        ], submitLabel: "Save Sales Goal and activate",
        submit: (v) => api(`/api/growth/campaign/${s.id}`, { method: "PUT", body: JSON.stringify({ ...v, goal: Number(v.goal), accept_budget: true, auto_rooms: v.auto_rooms === "yes", auto_linkedin: v.auto_linkedin === "yes", full_rhythm: v.full_rhythm === "yes", proof_consent: v.proof_consent === "yes", partner_enabled: v.partner_enabled === "yes",
          content_targets: Object.fromEntries(["LinkedIn", "Instagram", "Facebook"].map((channel) => [channel, Number(v[`posts_${channel}`])])),
          rhythm: v.rhythm,
          targeting: { ...t, categories: v.industries.split(",").map((x) => x.trim()).filter(Boolean), countries: v.countries.split(",").map((x) => x.trim()).filter(Boolean), keywords: v.keywords, titles: v.titles, exclusions: v.exclusions, employee_min: v.employee_min, employee_max: v.employee_max, goal: v.objective } }) }),
      }); return;
    }
    case "new-task": itemEditor("task", s.id); return;
    case "ai-social": {
      openEditor({ title: "Prepare a social draft", help: "Uses one Gemini request within the monthly cap. Instagram and Facebook include an editable graphic-card layout. Nothing is published.",
        fields: [{ name: "kind", label: "Channel", type: "select", options: [["linkedin", "LinkedIn text"], ["instagram", "Instagram caption + graphic card"], ["facebook", "Facebook caption + graphic card"]], value: "linkedin" }],
        submitLabel: "Prepare draft",
        submit: (v) => api("/api/growth/output-draft", { method: "POST", body: JSON.stringify({ service: s.id, kind: v.kind }) }).then((output) => { S.open[output.id] = true; return output; }),
      }); return;
    }
    case "ai-room":
    case "ai-linkedin": {
      const kind = d.act === "ai-room" ? "room" : "linkedin";
      if (!confirm(`Prepare a ${kind === "room" ? "lead-room" : "LinkedIn post"} draft with AI? This uses one Gemini request within the monthly cap. Nothing is shared or published.`)) return;
      await run(async () => {
        const output = await api("/api/growth/output-draft", { method: "POST", body: JSON.stringify({ service: s.id, kind, lead_id: kind === "room" ? S.lead : null }) });
        S.open[output.id] = true;
        if (kind === "linkedin") { S.lead = null; S.view = "content"; }
        return output;
      }, "Draft prepared for review.").catch(() => {});
      return;
    }
    case "new-content": itemEditor("content", s.id); return;
    case "lead-task": itemEditor("task", s.id, null, S.lead); return;
    case "lead-draft": itemEditor("outreach", s.id, null, S.lead); return;
    case "ai-draft": {
      const leadId = S.lead, sent = S.growth.items.some((i) => i.lead_id === leadId && i.kind === "outreach" && ["approved", "done"].includes(i.state));
      openEditor({
        title: "Write draft with AI",
        help: "If a pending or approved first-contact email already exists, it opens for review without another request. Otherwise Gemini writes one email using the stored facts and one request from the monthly allowance. Edit the existing draft to change it. Nothing is sent.",
        fields: [{ name: "purpose", label: "Purpose", type: "select", options: [["First contact", "First contact"], ...(sent ? [["Follow-up", "Follow-up"]] : [])], value: sent ? "Follow-up" : "First contact", full: true },
          { name: "guidance", label: "Guidance for the AI", type: "textarea", rows: 3, max: 500, optional: true, value: "" }],
        submitLabel: "Write draft",
        submit: (v) => api(`/api/services/${s.id}/leads/${leadId}/ai-draft`, { method: "POST", body: JSON.stringify(v) }).then((item) => { S.open[item.id] = true; return item; }),
      });
      return;
    }
    case "auto-rhythm": {
      const schedule = S.growth.rhythm_settings.find((r) => r.service === s.id);
      await run(() => api(`/api/growth/rhythm/${s.id}`, { method: "PUT", body: JSON.stringify({ enabled: !schedule.enabled }) }), "Daily planning updated.").catch(() => {});
      return;
    }
    case "routine": {
      await run(() => api(`/api/growth/rhythm/${s.id}`, { method: "POST", body: "{}" }), (result) => `${result.created} tasks added to today’s plan (IST).`).catch(() => {});
      return;
    }
    case "icp": openIcp(); return;
    case "search": await search(); return;
    case "add-company": addCompany(); return;
    case "review": reviewEditor(lead(S.lead), d.decision); return;
    case "restore": {
      const l = lead(S.lead);
      await run(() => api(`/api/services/${l.service}/leads/${l.id}/review`, { method: "PATCH", body: JSON.stringify({ decision: "active" }) }), `${l.company} restored to active leads.`).catch(() => {});
      return;
    }
    default:
  }
}

document.addEventListener("click", (e) => {
  const el = e.target.closest("button, tr.click");
  if (!el || el.disabled || el.closest("form") && el.type === "submit") return;
  if (el.matches("tr.click") && e.target.closest("a, button, select, input")) return;
  act(el).catch((error) => notice(error.message, true));
});
document.addEventListener("keydown", (e) => {
  if ((e.key === "Enter" || e.key === " ") && e.target.matches?.("tr.click")) { e.preventDefault(); act(e.target); }
});
document.addEventListener("change", async (e) => {
  if (e.target.id === "show-approved") { S.af.show = e.target.checked; render(); }
  if (e.target.id === "show-done-tasks") { S.showDoneTasks = e.target.checked; render(); }
  if (e.target.id === "interest") {
    const l = lead(S.lead), status = e.target.value;
    const note = status === "new" ? "" : prompt("Optional: a short note about the actual response.", l.notes || "");
    if (note === null) { render(); return; }
    await run(() => api(`/api/services/${l.service}/leads/${l.id}/status`, { method: "PATCH", body: JSON.stringify({ status, notes: note }) }), "Interest saved.").catch(() => {});
  }
});
document.addEventListener("input", (e) => { if (e.target.id === "lead-q") { S.q = e.target.value; render(); } });

$("editor-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  if (!form.reportValidity()) return;
  const values = {};
  for (const f of S.editor.fields) values[f.name] = f.type === "rhythm"
    ? f.value.map((_, i) => ({ on: form.elements[`rhythm_on_${i}`].checked, time: form.elements[`rhythm_time_${i}`].value }))
    : form.elements[f.name].value.trim();
  try {
    await run(() => S.editor.submit(values), "Saved.");
    $("editor").close();
  } catch (error) {
    $("editor-error").textContent = error.message;
    $("editor-error").hidden = false;
  }
});
document.addEventListener("submit", async (e) => {
  if (e.target.id !== "room-form") return;
  e.preventDefault();
  const f = e.target.elements;
  await run(() => api(`/api/growth/leads/${S.lead}`, { method: "PUT", body: JSON.stringify({ service: S.sel, stage: f.stage.value, owner: f.owner.value.trim(), room_notes: f.room_notes.value }) }), "Lead room saved.").catch(() => {});
});
$("icp-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await run(() => api(`/api/services/${S.sel}/icp`, { method: "PUT", body: JSON.stringify(icpPayload()) }), "ICP saved. No search was run.");
    $("icp-dialog").close();
  } catch (error) { $("icp-error").textContent = error.message; $("icp-error").hidden = false; }
});

matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () => render());

// Refresh read-only dashboard data without replacing an open form or lead edits.
let refreshingDashboard = false;
function canRefreshDashboard() {
  return Boolean(S.growth && !S.busy && !document.hidden && S.page === "service" && !S.lead
    && !document.querySelector("dialog[open]")
    && !document.activeElement?.matches("input, textarea, select, [contenteditable=true]"));
}
async function refreshDashboard() {
  if (refreshingDashboard || !canRefreshDashboard()) return;
  refreshingDashboard = true;
  try {
    await load();
    if (canRefreshDashboard()) render();
  } catch { /* Keep the saved display; manual refresh still reports errors. */ }
  finally { refreshingDashboard = false; }
}
setInterval(refreshDashboard, 60000);

(async () => {
  try { await load(); render(); }
  catch (error) { $("main").innerHTML = `<section class="panel"><div class="panel-b"><h2>Could not load the workspace</h2><p class="note">${esc(error.message)}</p><button class="btn" type="button" onclick="location.reload()">Try again</button></div></section>`; }
})();
