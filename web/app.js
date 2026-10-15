/* Voxel1 Growth Engine: Training and BIM Services workspaces.
   Everything shown comes from the server. Nothing is sent, posted or scheduled from here. */

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
    else b.push(`<button class="btn pri" data-item="approve" data-id="${id}">Approve</button>`);
    b.push(`<button class="btn" data-item="edit" data-id="${id}">Edit</button>`);
    b.push(`<button class="btn" data-item="reject" data-id="${id}">${i.kind === "task" ? "Skip" : "Reject"}</button>`);
  } else if (i.state === "approved") {
    b.push(`<button class="btn" data-item="copy" data-id="${id}">Copy text</button>`);
    b.push(`<button class="btn" data-item="download" data-id="${id}">Download</button>`);
    b.push(`<button class="btn pri" data-item="complete" data-id="${id}">Record as ${i.kind === "content" ? "posted" : "sent"}</button>`);
    b.push(`<button class="btn" data-item="reopen" data-id="${id}">Reopen</button>`);
  } else {
    b.push(`<button class="btn" data-item="reopen" data-id="${id}">Reopen</button>`);
  }
  return `<div class="actions">${b.join("")}</div>`;
}
const draftText = (i) => S.open[i.id] && i.body ? `<div class="draft">${esc(i.body)}</div>` : "";

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
  const plan = todayRows(s.id).filter((r) => r.kind === "task");
  const done = plan.filter((r) => r.state === "done").length;
  const goal = st.goal, won = wonCount(s.id);
  const seg = goal ? `<span class="seg">${Array.from({ length: Math.min(goal, 20) }, (_, i) => `<i class="${i < won ? "won" : ""}"></i>`).join("")}</span>` : '<span>Set a goal to track progress</span>';
  const next = items(s.id, "task").filter((i) => i.state === "pending").sort(byDue)[0];
  const now = paused(s.id)
    ? `<b>Paused.</b> New searches, approvals and task completion are blocked until you resume. A search already running is not cancelled.`
    : next ? `<b>Next:</b> ${esc(next.title)} <span class="muted">· ${esc(fmtWhen(next))}${next.owner ? " · " + esc(next.owner) : ""}</span>`
      : `<b>No open tasks.</b> View live agent jobs or add today’s task plan from Daily rhythm.`;
  return `<div class="crumb">Growth Engine <span>/</span> ${S.lead ? `<button type="button" data-act="back">${esc(s.name)}</button> <span>/</span> Lead room` : esc(s.name)}</div>
  <div class="ph">
    <div class="ph-l"><span class="av lg av-${s.id === "training" ? "train" : s.id}">${s.code}</span><div style="min-width:0"><div class="title-row"><h1>${esc(s.name)}</h1>${badge}</div><p>${esc(st.strategy || "No strategy written yet.")}</p></div></div>
    <div class="ph-r"><button class="btn" type="button" data-act="edit-goal">Sales Goal</button><button class="btn" type="button" data-act="pause">${settings(s.id).paused ? "Resume workspace" : "Pause workspace"}</button></div>
  </div>
  <section class="kpis" aria-label="Key figures">
    <div class="kpi"><span>Sales goal ${esc(S.growth.sales_progress?.[s.id]?.quarter || "(all time)")}</span><b>${won}<small> / ${goal}</small></b>${seg}</div>
    <div class="kpi"><span>Active leads</span><b>${leads.length}</b><span>${leads.filter((l) => l.email || l.phone).length} with email or phone</span></div>
    <div class="kpi"><span>In pipeline</span><b>${pipeline}</b><span>engaged to negotiation</span></div>
    <div class="kpi"><span>Today’s plan</span><b>${done}<small> / ${plan.length}</small></b><span>tasks done</span></div>
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

function agentPanel(s) {
  const campaign = S.growth.campaigns.find((c) => c.service === s.id);
  const jobs = S.growth.jobs.filter((j) => j.service === s.id);
  const messages = items(s.id, "outreach");
  const meetings = activeLeads(s.id).filter((l) => detail(l.id).stage === "meeting").length;
  return `<section class="panel"><div class="panel-h"><div><h2>Live agent workflow</h2><p class="note">${campaign ? `${esc(campaign.objective)} · Discovery ${esc(campaign.search_time)} / drafts ${esc(campaign.draft_time)} IST, every day. ${paused(s.id) ? "Paused." : "Active during campaign dates."}` : "Set a Sales Goal to start scheduled lead discovery and approval-ready drafts."}</p></div><button class="btn pri" data-act="campaign">${campaign ? "Edit Sales Goal" : "Set Sales Goal"}</button></div>
    <div class="panel-b"><p class="note">${activeLeads(s.id).length} active leads · ${messages.filter((i) => i.state === "pending").length} messages awaiting approval · ${messages.filter((i) => i.state === "done").length} recorded sent · ${meetings} currently at meeting stage · ${wonCount(s.id)} won${campaign?.quarter ? ` in ${esc(campaign.quarter)}` : " (all time)"}. Lead, message and meeting counts are service-wide.</p>${campaign?.content_targets ? `<p class="note">Daily content targets: ${Object.entries(campaign.content_targets).map(([channel, count]) => `${esc(channel)} ${count}`).join(" · ")}. Content preparation is manual.</p>` : ""}</div>
    <div class="panel-b">${S.growth.automation_missing?.length ? `<p class="blocked">Server setup needed: ${S.growth.automation_missing.map(esc).join(", ")}. Add these server environment settings and restart; never paste API keys into goal fields.</p>` : ""}<p class="note">Uses Apollo, Brave and Gemini within server budgets. Up to one search and five draft attempts per day. No messages are sent. Scheduled work requires the hosting server to stay running. <button class="linkish" data-act="refresh-jobs">Refresh results</button></p></div>
    <div class="tw"><table><thead><tr><th>Day (IST)</th><th>Job</th><th>Status</th><th>Result</th></tr></thead><tbody>${jobs.length ? jobs.map((j) => {
      const r = JSON.parse(j.result || "{}");
      return `<tr><td>${esc(j.day)}</td><td>${esc(j.job)}</td><td>${esc(j.state.replaceAll("_", " "))}</td><td>${esc(r.message || `${r.found ?? 0} found; ${r.added ?? 0} added`)}${r.warnings?.length ? `<span class="sub">${esc(r.warnings.join(" "))}</span>` : ""}${r.item_id ? '<button class="linkish" data-act="approvals">Review draft in Approvals</button>' : ""}</td></tr>`;
    }).join("") : '<tr><td colspan="4" class="empty-cell">No jobs have run yet.</td></tr>'}</tbody></table></div></section>`;
}

function rhythm(s) {
  const schedule = S.growth.rhythm_settings.find((r) => r.service === s.id);
  const rows = todayRows(s.id);
  const later = items(s.id, "task").filter((i) => i.state === "pending" && i.due && i.due > today()).sort(byDue);
  const groups = [["Marketing", ["Marketing"]], ["Content", ["Content"]], ["BD", ["BD"]], ["Outreach", ["Outreach"]], ["Sales", ["Sales", "Account"]]];
  const tasks = rows.filter((r) => r.kind === "task");
  const phases = groups.map(([name, labels]) => {
    const it = tasks.filter((r) => labels.includes(r.label));
    const d = it.filter((r) => r.state === "done").length;
    return `<div class="phs"><div class="h"><span class="ty ${name}">${name === "Sales" ? "Sales &amp; account" : name}</span><span class="num">${d}/${it.length}</span></div><div class="mbar"><i style="width:${it.length ? (d / it.length) * 100 : 0}%"></i></div></div>`;
  }).join("");
  const row = (i) => {
    const l = i.lead_id ? lead(i.lead_id) : null;
    const typeCell = i.kind === "task" ? (i.label ? `<span class="ty ${esc(i.label)}">${esc(i.label)}</span>` : '<span class="ty plain">Task</span>') : `<span class="ty Content">${i.kind === "content" ? "Content" : "Outreach"}</span>`;
    return `<tr><td class="t">${esc(fmtWhen(i))}</td><td>${typeCell}</td>
      <td><b class="strong">${esc(i.title)}</b>${l ? `<span class="sub">Lead: <button class="linkish" type="button" data-lead="${l.id}">${esc(l.company)}</button></span>` : ""}${i.kind !== "task" ? `<span class="sub">${esc(i.channel)} draft${i.label ? " · " + esc(i.label) : ""}</span>` : ""}${draftText(i)}${itemButtons(i)}</td>
      <td>${who(i.owner)}</td><td>${itemStatus(i)}</td></tr>`;
  };
  return `${agentPanel(s)}<section class="panel">
    <div class="panel-h"><div><h2>${esc(s.name)} daily rhythm</h2><span class="note">Working-day template from Voxel1 Growth Engine V2 · All times IST (Asia/Kolkata)</span></div>
      <div class="actions"><button class="btn" type="button" data-act="auto-rhythm">${schedule.enabled ? "Disable daily planning" : "Enable daily planning"}</button><button class="btn pri" type="button" data-act="routine">Add rhythm to today’s plan</button></div></div>
    <div class="tw"><table><thead><tr><th>Time (IST)</th><th>Type</th><th>Activity and purpose</th></tr></thead>
      <tbody>${S.growth.rhythm_templates[s.id].map(([time, label, title, purpose]) => `<tr><td class="t">${esc(time)}</td><td><span class="ty ${esc(label)}">${esc(label)}</span></td><td><b class="strong">${esc(title)}</b><span class="sub">${esc(purpose)}</span></td></tr>`).join("")}</tbody>
    </table></div><div class="panel-f"><span class="note">${schedule.enabled ? "Daily planning enabled: the server creates one plan each weekday from 06:00 IST while this workspace is active." : "Daily planning is disabled. Enable it to create weekday plans automatically."} Tasks remain for your team to execute. These template tasks are separate from the live jobs above. No sending or publishing. Missed days are not backfilled.</span></div>
  </section>
  <section class="panel">
    <div class="panel-h"><div><h2>Today’s plan</h2><span class="note">Tasks your team has planned, plus drafts waiting for approval. Nothing here runs by itself.</span></div>
      <div class="actions"><button class="btn" type="button" data-act="routine">Add rhythm to today’s plan</button><button class="btn pri" type="button" data-act="new-task">New task</button></div></div>
    <div class="phases">${phases}</div>
    <div class="tw"><table>
      <thead><tr><th>When</th><th>Type</th><th>Activity</th><th>Owner</th><th>Status</th></tr></thead>
      <tbody>${rows.length ? rows.map(row).join("") : `<tr><td colspan="5" class="empty-cell">Nothing planned for today. Use <b>New task</b>, or <b>Add rhythm to today’s plan</b> to create the reference rhythm tasks for ${esc(s.name)}.</td></tr>`}</tbody>
    </table></div>
    <div class="panel-f"><label class="fshow"><input type="checkbox" id="show-done-tasks" ${S.showDoneTasks ? "checked" : ""}> Show all completed and skipped tasks</label></div>
  </section>
  <section class="panel">
    <div class="panel-h"><h2>Coming up</h2><span class="note">${later.length} scheduled task${later.length === 1 ? "" : "s"}</span></div>
    <div class="tw"><table>
      <thead><tr><th>When</th><th>Type</th><th>Activity</th><th>Owner</th><th>Status</th></tr></thead>
      <tbody>${later.length ? later.map(row).join("") : '<tr><td colspan="5" class="empty-cell">No future tasks.</td></tr>'}</tbody>
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
    <div class="panel-h"><div><h2>Content plan</h2><span class="note">Drafts are reviewed here. Approving does not post anything: copy or download the approved text, post it yourself, then record it as posted.</span></div><button class="btn pri" type="button" data-act="new-content">New draft</button></div>
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
    <section class="panel"><div class="panel-h"><h2>Next steps</h2><div class="actions"><button class="btn" type="button" data-act="lead-task">Add task</button><button class="btn" type="button" data-act="lead-draft">Draft message</button>${active ? '<button class="btn pri" type="button" data-act="ai-draft">Write draft with AI</button>' : ""}</div></div>
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
          ${l.email ? `<p><span class="muted">${apollo ? "Verified work email (Apollo)" : "Email (unverified)"}</span><br><a href="mailto:${encodeURIComponent(l.email)}">${esc(l.email)}</a></p>` : '<p class="muted">Work email unavailable</p>'}
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
    const pri = i.kind === "outreach" ? (["proposal", "negotiation"].includes(stage) || l?.status === "interested" ? "High" : "Medium") : "Low";
    const why = pri === "High" ? (l?.status === "interested" ? "Interested lead" : "Deal at proposal stage") : i.kind === "outreach" ? "Message to a lead" : "Planned content";
    return { i, l, pri, why, type: i.kind === "outreach" ? "Outreach" : "Content" };
  }).sort((a, b) => ({ High: 0, Medium: 1, Low: 2 })[a.pri] - ({ High: 0, Medium: 1, Low: 2 })[b.pri] || byDue(a.i, b.i));
}

function approvalsPage() {
  const f = S.af, all = approvalRows();
  const open = all.filter((a) => a.i.state === "pending");
  const list = all.filter((a) => (f.show || a.i.state === "pending") && (f.p === "all" || a.pri === f.p) && (f.s === "all" || a.i.service === f.s) && (f.t === "all" || a.type === f.t));
  const cnt = (fn) => open.filter(fn).length;
  const chips = (key, opts) => opts.map(([v, label, n]) => `<button class="fchip" type="button" data-af="${key}:${v}" aria-pressed="${f[key] === v}">${esc(label)}${n !== undefined ? ` <span class="num">${n}</span>` : ""}</button>`).join("");
  return `<div class="crumb">Growth Engine <span>/</span> Approvals</div>
  <div class="ph"><div class="ph-l"><div><h1>Approvals</h1><p>Drafts waiting for a decision across Training and BIM Services. Approving records your decision only; nothing is sent or posted from this app.</p></div></div></div>
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
      <div class="fgroup"><span class="lbl">Type</span>${chips("t", [["all", "All"], ["Outreach", "Messages", cnt((a) => a.type === "Outreach")], ["Content", "Content", cnt((a) => a.type === "Content")]])}</div>
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
  const name = kind === "task" ? "task" : kind === "content" ? "content draft" : "message draft";
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
    help: kind === "task" ? "" : existing && existing.state !== "pending" ? "Saving changes returns this draft to “Needs approval”." : "Drafts are never sent or posted from this app. Approve them here, then send or post them yourself.",
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
    approve: "Approved draft. Nothing was sent or posted — copy it and send it yourself.",
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
    case "back": S.lead = null; S.view = "leads"; render(); return;
    case "pause": {
      const on = !settings(s.id).paused;
      await run(() => api(`/api/growth/settings/${s.id}`, { method: "PUT", body: JSON.stringify({ paused: on }) }), on ? `${s.name} paused.` : `${s.name} resumed.`).catch(() => {});
      return;
    }
    case "approvals": S.page = "approvals"; S.lead = null; render(); return;
    case "refresh-jobs": await run(async () => {}, "Results refreshed.").catch(() => {}); return;
    case "edit-goal":
    case "campaign": {
      const c = S.growth.campaigns.find((c) => c.service === s.id);
      const t = c?.targeting || S.icp[s.id];
      const st = settings(s.id);
      const year = Number(today().slice(0, 4)), month = Number(today().slice(5, 7));
      openEditor({ title: `${s.name}: Sales Goal`, help: "Set the sales outcome and the direction for this agent. Saving activates daily discovery and drafting within the dates below, using server provider budgets. Times are IST. Pause controls still apply. Existing jobs are not repeated today. Content targets guide manual planning; sending is not connected.",
        fields: [
          { name: "goal", label: "Quarterly target (won sales)", type: "number", min: 0, value: st.goal, required: true },
          { name: "quarter", label: "Sales quarter (YYYY-Q1 to YYYY-Q4)", value: c?.quarter || `${year}-Q${Math.ceil(month / 3)}`, required: true, max: 7 },
          { name: "strategy", label: "Strategy", type: "textarea", rows: 3, max: 1000, value: st.strategy, full: true },
          { name: "objective", label: "Service focus and campaign objective", value: c?.objective || t.goal || "", required: true, max: 500, full: true },
          { name: "countries", label: "Target countries (comma separated)", value: t.countries.join(", "), required: true },
          { name: "industries", label: "Industries (comma separated: architecture, construction, engineering, real_estate, education)", value: t.categories.join(", "), required: true, full: true },
          { name: "keywords", label: "Service keywords", value: t.keywords, max: 500 },
          { name: "titles", label: "Decision-maker roles", value: t.titles, max: 500 },
          { name: "employee_min", label: "Minimum company size", type: "number", value: t.employee_min, optional: true },
          { name: "employee_max", label: "Maximum company size", type: "number", value: t.employee_max, optional: true },
          { name: "exclusions", label: "Exclude keywords", value: t.exclusions || "", max: 500, optional: true },
          { name: "start", label: "Start date (IST)", type: "date", value: c?.start || today(), required: true },
          { name: "end", label: "End date (blank = ongoing)", type: "date", value: c?.end || "", optional: true },
          { name: "search_time", label: "Daily discovery (IST)", type: "time", value: c?.search_time || "06:00", required: true },
          { name: "draft_time", label: "Daily drafts (IST)", type: "time", value: c?.draft_time || (s.id === "bim" ? "09:00" : "10:00"), required: true },
          ...["LinkedIn", "Instagram", "Facebook"].map((channel) => ({ name: `posts_${channel}`, label: `${channel} posts per day (0–10)`, type: "number", min: 0, value: c?.content_targets?.[channel] || 0, required: true })),
        ], submitLabel: "Save Sales Goal and activate",
        submit: (v) => api(`/api/growth/campaign/${s.id}`, { method: "PUT", body: JSON.stringify({ ...v, goal: Number(v.goal), accept_budget: true,
          content_targets: Object.fromEntries(["LinkedIn", "Instagram", "Facebook"].map((channel) => [channel, Number(v[`posts_${channel}`])])),
          targeting: { ...t, categories: v.industries.split(",").map((x) => x.trim()).filter(Boolean), countries: v.countries.split(",").map((x) => x.trim()).filter(Boolean), keywords: v.keywords, titles: v.titles, exclusions: v.exclusions, employee_min: v.employee_min, employee_max: v.employee_max, goal: v.objective } }) }),
      }); return;
    }
    case "new-task": itemEditor("task", s.id); return;
    case "new-content": itemEditor("content", s.id); return;
    case "lead-task": itemEditor("task", s.id, null, S.lead); return;
    case "lead-draft": itemEditor("outreach", s.id, null, S.lead); return;
    case "ai-draft": {
      const leadId = S.lead, sent = S.growth.items.some((i) => i.lead_id === leadId && i.kind === "outreach" && ["approved", "done"].includes(i.state));
      openEditor({
        title: "Write draft with AI",
        help: "Gemini writes a first email using only what this app knows about the lead. It counts as one Gemini request against the monthly limit. The draft waits for your edits and approval; nothing is sent.",
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
  for (const f of S.editor.fields) values[f.name] = form.elements[f.name].value.trim();
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

(async () => {
  try { await load(); render(); }
  catch (error) { $("main").innerHTML = `<section class="panel"><div class="panel-b"><h2>Could not load the workspace</h2><p class="note">${esc(error.message)}</p><button class="btn" type="button" onclick="location.reload()">Try again</button></div></section>`; }
})();
