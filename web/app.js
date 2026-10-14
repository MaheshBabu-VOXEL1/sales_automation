const state = { service: null, icp: null, compatibleBackend: true, leads: [], filter: "all", budget: null, history: {}, reviewing: null };
const countries = [["US", "USA"], ["AE", "UAE"], ["SA", "Saudi Arabia"], ["IN", "India"], ["SG", "Singapore"]];
const countryCode = (name) => countries.find((item) => item[1] === name)?.[0] || null;
const leadCountry = (lead) => lead.country || (lead.source_id?.startsWith("apollo/") && state.icp?.countries?.length === 1 ? state.icp.countries[0] : "");
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const safeUrl = (value) => { try { const u = new URL(value); return ["https:", "http:"].includes(u.protocol) ? u.href : null; } catch { return null; } };

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const data = await response.json();
  if (!response.ok) {
    const error = new Error(data.error || `Request failed (${response.status})`);
    error.budget = data.budget;
    throw error;
  }
  return data;
}

const providerNames = { apollo: "Apollo", brave: "Brave", gemini: "Gemini" };
const requestCounts = (counts) => Object.entries(providerNames).filter(([key]) => counts[key]).map(([key, name]) => `${name} ${counts[key]}`).join(", ") || "none";

function renderBudget(budget) {
  state.budget = budget;
  const panel = $("#budget");
  if (!budget) { panel.classList.add("hidden"); return; }
  const cards = Object.entries(providerNames).map(([key, name]) => {
    const limit = budget.limits[key];
    const need = budget.estimate[key];
    if (!need && !budget.used[key] && !budget.held[key]) return `<div><strong>${name}</strong><small>Not used by this search</small></div>`;
    const held = budget.held[key] ? `; ${budget.held[key]} held by unfinished searches` : "";
    return `<div><strong>${name}: ${budget.used[key]} of ${limit || "no limit set"} requests</strong><small>This search: up to ${need}${held}</small></div>`;
  });
  cards.unshift(`<div><strong>Searches: ${budget.searches_used} of ${budget.limits.searches || "no limit set"}</strong><small>Counted even if a search fails</small></div>`);
  panel.innerHTML = `<h3>Paid search budget for ${esc(budget.month)} (UTC)</h3><div class="budget-grid">${cards.join("")}</div>`
    + (budget.allowed ? "" : `<p class="budget-blocked">Search blocked: ${budget.blocked_reasons.map(esc).join(" ")}</p>`)
    + `<p class="budget-note">Counts are provider requests sent by this app, including failed ones, not billed credits or money. Check each provider's dashboard for actual charges. Limits are set by whoever manages the server environment.</p>`;
  panel.classList.remove("hidden");
}

async function loadBudget() {
  try { renderBudget(state.icp?.search_mode === "Apollo + Brave" ? await api("/api/budget") : null); }
  catch (error) { renderBudget(null); message(`Could not load the search budget: ${error.message}`, true); }
}

function message(text, error = false) {
  const box = $("#message");
  box.textContent = text;
  box.classList.toggle("error", error);
  box.classList.remove("hidden");
}

async function openService(service) {
  state.service = service;
  state.filter = "all";
  state.history = {};
  $("#home").classList.add("hidden");
  $("#workspace").classList.remove("hidden");
  $("#message").classList.add("hidden");
  $("#service-title").textContent = service === "training" ? "Training" : "BIM Services";
  $("#service-eyebrow").textContent = service === "training" ? "TRAINING PIPELINE" : "BIM SERVICES PIPELINE";
  $("#lead-search").value = "";
  document.querySelectorAll(".tabs button").forEach((button) => button.classList.toggle("active", button.dataset.filter === "all"));
  try {
    const [icp, leads] = await Promise.all([api(`/api/services/${service}/icp`), api(`/api/services/${service}/leads`)]);
    state.compatibleBackend = Array.isArray(icp.countries);
    state.icp = state.compatibleBackend ? icp : { ...icp, countries: countries.map((item) => item[1]) };
    const providerMode = icp.search_mode === "Apollo + Brave";
    $("#source-badge").textContent = `Source: ${icp.search_mode || "OpenStreetMap city samples"}`;
    $("#country-search-hint").textContent = providerMode ? "Apollo searches the selected countries. This pilot checks up to 10 companies per click." : "Without Apollo and Brave keys, search uses city samples in the five listed countries.";
    $("#search-disclaimer").textContent = providerMode ? `Apollo finds companies and people; Brave checks for matching BIM/Revit website pages without storing its search results. ${icp.ai_qualification_enabled ? "Gemini also screens new matches for plausible buyers; uncertain matches are skipped. AI can still be wrong." : "AI buyer screening is off."} ${icp.enrichment_enabled ? "Apollo may use credits to enrich city, company phone and one verified work email for up to three matches per click." : "City, email and phone enrichment is off."} These are candidate matches, not verified purchase intent. No messages are sent.` : "The public-map source covers one city sample in each listed country, not the whole country. Other countries need Apollo and Brave keys. Data © OpenStreetMap contributors. No messages are sent.";
    const form = $("#icp-form");
    for (const field of ["name", "notes", "employee_min", "employee_max", "titles", "keywords", "exclusions", "goal"]) form.elements[field].value = icp[field] ?? "";
    form.querySelectorAll('[name="categories"]').forEach((box) => { box.checked = (icp.categories || []).includes(box.value); });
    form.querySelectorAll('[name="countries"]').forEach((box) => { box.checked = state.icp.countries.includes(box.value); });
    form.elements.other_countries.value = state.icp.countries.filter((name) => !countryCode(name)).join(", ");
    $("#discover").disabled = !state.compatibleBackend;
    form.querySelector('button[type="submit"]').disabled = !state.compatibleBackend;
    $("#icp-updated").textContent = "ICP saved";
    state.leads = leads;
    renderLeads();
    await loadBudget();
    if (!state.compatibleBackend) message("An older Voxel1 server is running. Stop that server, start 'python server.py' again from D:\\sale automation, then refresh this page. Country settings cannot be saved or searched until it is restarted.", true);
  } catch (error) { message(error.message, true); }
}

function icpPayload() {
  const form = $("#icp-form");
  const chosen = [...form.querySelectorAll('[name="countries"]:checked')].map((item) => item.value);
  const other = form.elements.other_countries.value.split(",").map((item) => item.trim()).filter(Boolean);
  return {
    name: form.elements.name.value.trim(), notes: form.elements.notes.value.trim(),
    categories: [...form.querySelectorAll('[name="categories"]:checked')].map((item) => item.value),
    countries: [...chosen, ...other],
    employee_min: form.elements.employee_min.value, employee_max: form.elements.employee_max.value,
    titles: form.elements.titles.value.trim(), keywords: form.elements.keywords.value.trim(),
    exclusions: form.elements.exclusions.value.trim(), goal: form.elements.goal.value.trim(),
  };
}

async function saveIcp(showMessage = true) {
  if (!state.compatibleBackend) throw new Error("Restart the running Voxel1 server and refresh this page before saving the ICP.");
  const icp = await api(`/api/services/${state.service}/icp`, { method: "PUT", body: JSON.stringify(icpPayload()) });
  if (!Array.isArray(icp.countries)) {
    state.compatibleBackend = false;
    $("#discover").disabled = true;
    $("#icp-form").querySelector('button[type="submit"]').disabled = true;
    throw new Error("The running server did not save country focus. Restart 'python server.py' from D:\\sale automation and refresh.");
  }
  state.icp = icp;
  $("#icp-updated").textContent = `Saved ${new Date(icp.updated_at).toLocaleString()}`;
  renderLeads();
  if (showMessage) message("ICP saved for this product.");
}

async function loadLeads() {
  state.leads = await api(`/api/services/${state.service}/leads`);
  renderLeads();
}

const isActive = (lead) => (lead.review_decision || "active") === "active";
const reasonLabel = (code) => state.icp?.review_reasons?.[code] || code || "No reason recorded";
const shortDate = (value) => value ? new Date(value).toLocaleDateString() : "";

function whyListed(lead) {
  const apollo = lead.source_id?.startsWith("apollo/");
  const reason = lead.match_reason ? esc(lead.match_reason) : "No reason recorded. Saved before the app recorded why candidates were listed; verify fit on the website.";
  let ai;
  if (lead.ai_screened && lead.ai_reason) ai = `Gemini${lead.ai_model ? ` (${esc(lead.ai_model)})` : ""}${lead.screened_at ? `, ${esc(shortDate(lead.screened_at))}` : ""}: “${esc(lead.ai_reason)}” AI judgement, not proof of need.`;
  else if (lead.ai_screened) ai = "Gemini marked it a plausible buyer on an earlier search; its reason was not recorded.";
  else ai = apollo ? "Gemini screening not recorded." : "Public map candidate; not AI-screened.";
  return `<div class="why-listed"><small>${reason}</small><small class="ai-line">${ai}</small></div>`;
}

function sourceCell(lead) {
  const source = safeUrl(lead.source_url);
  if (!source) return "—";
  const label = lead.source_id?.startsWith("apollo/") ? "Apollo company record: website" : lead.source_id?.match(/^(node|way|relation)\//) ? "OpenStreetMap record" : "Source";
  return `<a class="source-link" href="${esc(source)}" target="_blank" rel="noopener noreferrer">${label} ↗</a>`;
}

function historyText(item) {
  const d = item.detail || {};
  const when = new Date(item.created_at).toLocaleString();
  const note = d.note ? ` Note: “${esc(d.note)}”` : "";
  if (item.event === "discovered") return `${when}: added by ${esc(d.source || "search")}.`;
  if (item.event === "found_again") return `${when}: found again by ${esc(d.source || "search")}.`;
  if (item.event === "interest") return `${when}: interest changed from ${esc(d.from)} to ${esc(d.to)}.${note}`;
  if (item.event === "review") return d.to === "active" ? `${when}: restored to active candidates.${note}` : `${when}: ${d.to === "rejected" ? "rejected" : "archived"}: ${esc(reasonLabel(d.reason))}.${note}`;
  return `${when}: ${esc(item.event)}`;
}

function renderLeads() {
  const leads = state.leads;
  const active = leads.filter(isActive);
  const excluded = leads.length - active.length;
  $("#stat-total").textContent = active.length;
  $("#stat-total-label").textContent = excluded ? `Active candidates (${excluded} rejected/archived)` : "Active candidates";
  $("#stat-contact").textContent = active.filter((lead) => lead.email || lead.phone).length;
  $("#stat-interested").textContent = active.filter((lead) => lead.status === "interested").length;
  $("#stat-not").textContent = active.filter((lead) => lead.status === "not_interested").length;
  $("#country-summary").innerHTML = (state.icp?.countries || []).map((name) => `<span><strong>${esc(name)}</strong><small>${active.filter((lead) => leadCountry(lead).toLowerCase() === name.toLowerCase() || leadCountry(lead) === countryCode(name)).length} companies</small></span>`).join("");
  const text = $("#lead-search").value.trim().toLowerCase();
  const matchesFilter = (lead) => state.filter === "excluded" ? !isActive(lead)
    : isActive(lead) && (state.filter === "all" || (state.filter === "ai_screened" ? Boolean(lead.ai_screened) : lead.status === state.filter));
  const visible = leads.filter((lead) => matchesFilter(lead) && lead.company.toLowerCase().includes(text));
  $("#empty").classList.toggle("hidden", visible.length > 0);
  $("#empty").textContent = state.filter === "excluded" ? "No rejected or archived companies." : leads.length ? "No companies match this filter." : "No companies yet. Set your ICP and choose “Search companies.”";
  $("#lead-rows").innerHTML = visible.map((lead) => {
    const web = safeUrl(lead.website);
    const apollo = lead.source_id?.startsWith("apollo/");
    const email = lead.email ? `<span class="contact-line"><small>${apollo ? "Verified work email from Apollo" : "Public email (unverified)"}</small><a href="mailto:${encodeURIComponent(lead.email)}">${esc(lead.email)}</a></span>` : "<small>Work email unavailable</small>";
    const phone = lead.phone ? `<span class="contact-line"><small>${apollo ? "Company phone, not a direct line" : "Public phone (unverified)"}</small><a href="tel:${encodeURIComponent(lead.phone)}">${esc(lead.phone)}</a></span>` : "";
    const person = lead.contact_name ? `<span class="contact-line"><strong>${esc(lead.contact_name)}</strong><small>${esc(lead.contact_title)}</small>${lead.contact_name.includes("*") ? "<small>Name partly hidden by provider</small>" : ""}</span>` : "<small>Decision-maker not found</small>";
    const historyButton = `<button type="button" class="link-button" data-action="history" data-id="${lead.id}">${state.history[lead.id] ? "Hide history" : "History"}</button>`;
    const review = isActive(lead)
      ? `<select class="status-select ${esc(lead.status)}" data-id="${lead.id}" aria-label="Interest status for ${esc(lead.company)}"><option value="new" ${lead.status === "new" ? "selected" : ""}>Needs review</option><option value="interested" ${lead.status === "interested" ? "selected" : ""}>Interested</option><option value="not_interested" ${lead.status === "not_interested" ? "selected" : ""}>Not interested</option></select>${lead.notes ? `<small class="contact-line">${esc(lead.notes)}</small>` : ""}<div class="review-actions"><button type="button" class="link-button danger" data-action="rejected" data-id="${lead.id}">Reject</button><button type="button" class="link-button" data-action="archived" data-id="${lead.id}">Archive</button>${historyButton}</div>`
      : `<span class="excluded-badge ${esc(lead.review_decision)}">${lead.review_decision === "rejected" ? "Rejected" : "Archived"}</span><small class="contact-line">${esc(reasonLabel(lead.review_reason))}${lead.reviewed_at ? `, ${esc(shortDate(lead.reviewed_at))}` : ""}</small>${lead.review_note ? `<small class="contact-line">“${esc(lead.review_note)}”</small>` : ""}<div class="review-actions"><button type="button" class="link-button" data-action="active" data-id="${lead.id}">Restore</button>${historyButton}</div>`;
    const row = `<tr><td data-label="Company"><strong>${esc(lead.company)}</strong><small>${esc(lead.category)}</small>${web ? `<div><a class="source-link" href="${esc(web)}" target="_blank" rel="noopener noreferrer">Website ↗</a></div>` : ""}</td><td data-label="Why listed">${whyListed(lead)}</td><td data-label="Location">${esc(lead.city)}<br><small>${esc(leadCountry(lead))}</small></td><td data-label="Contact">${person}${email}${phone}</td><td data-label="Review / interest">${review}</td><td data-label="Source">${sourceCell(lead)}</td></tr>`;
    const items = state.history[lead.id];
    const history = items ? `<tr class="history-row"><td colspan="6" data-label="History">${items.length ? `<ul class="history-list">${items.map((item) => `<li>${historyText(item)}</li>`).join("")}</ul>` : "<small>No history recorded yet. Events are recorded from this version onward.</small>"}</td></tr>` : "";
    return row + history;
  }).join("");
}

function openReview(lead, decision) {
  state.reviewing = { lead, decision };
  const form = $("#review-form");
  const reasons = Object.entries(state.icp?.review_reasons || {}).filter(([code]) => decision === "archived" || code !== "no_current_need");
  form.elements.reason.innerHTML = `<option value="">Choose a reason</option>` + reasons.map(([code, label]) => `<option value="${esc(code)}">${esc(label)}</option>`).join("");
  if (decision === "archived") form.elements.reason.value = "no_current_need";
  form.elements.note.value = "";
  $("#review-title").textContent = `${decision === "rejected" ? "Reject" : "Archive"} ${lead.company}`;
  $("#review-help").textContent = decision === "rejected"
    ? "Rejected companies leave the active list and are skipped by later paid searches. Nothing is deleted; you can restore it."
    : "Archived companies leave the active list for now and are skipped by later paid searches. Nothing is deleted; you can restore it.";
  $("#review-submit").textContent = decision === "rejected" ? "Reject" : "Archive";
  $("#review-error").classList.add("hidden");
  $("#review-dialog").showModal();
}

async function saveReview(lead, decision, reason = "", note = "") {
  const updated = await api(`/api/services/${state.service}/leads/${lead.id}/review`, { method: "PATCH", body: JSON.stringify({ decision, reason, notes: note }) });
  state.leads = state.leads.map((item) => item.id === updated.id ? updated : item);
  if (state.history[lead.id]) state.history[lead.id] = await api(`/api/services/${state.service}/leads/${lead.id}/history`);
  renderLeads();
  message(decision === "active" ? `${lead.company} restored to active candidates.` : `${lead.company} ${decision === "rejected" ? "rejected" : "archived"}. Its record and history are kept.`);
}

document.querySelectorAll(".service-card").forEach((card) => card.addEventListener("click", () => openService(card.dataset.service)));
$("#back").addEventListener("click", () => { $("#workspace").classList.add("hidden"); $("#home").classList.remove("hidden"); state.service = null; });
$("#icp-form").addEventListener("submit", async (event) => { event.preventDefault(); try { await saveIcp(); } catch (error) { message(error.message, true); } });
$("#discover").addEventListener("click", async () => {
  const button = $("#discover");
  button.disabled = true;
  try {
    await saveIcp(false);
    let body = {};
    if (state.icp.search_mode === "Apollo + Brave") {
      await loadBudget();
      const budget = state.budget;
      if (!budget) return;
      if (!budget.allowed) { message(`Search not started: ${budget.blocked_reasons.join(" ")}`, true); return; }
      if (!confirm(`This search may send up to: ${requestCounts(budget.estimate)} requests.

These are worst-case request counts; providers may charge credits for them. Continue?`)) { message("Search cancelled. No provider requests were sent."); return; }
      body = { confirmed: true, estimate: budget.estimate };
    }
    button.textContent = "Searching…";
    message("Searching companies and checking public website evidence. This can take a few minutes.");
    const result = await api(`/api/services/${state.service}/discover`, { method: "POST", body: JSON.stringify(body) });
    await loadLeads();
    await loadBudget();
    const searched = result.coverage.length;
    const failures = result.coverage.filter((item) => item.error).map((item) => item.country);
    message(`${result.source}: checked ${searched} selected countr${searched === 1 ? "y" : "ies"}. Found ${result.found} candidate companies; ${result.added} added.${result.warnings?.length ? ` Some checks failed: ${result.warnings.join(" ")}` : ""}${failures.length ? ` Search errors: ${failures.join(", ")}.` : ""}${result.skipped_reviewed ? ` Skipped ${result.skipped_reviewed} rejected or archived compan${result.skipped_reviewed === 1 ? "y" : "ies"}.` : ""}${result.usage ? ` Provider requests sent: ${requestCounts(result.usage.actual)} (estimate was up to ${requestCounts(result.usage.estimate)}).` : ""}`, Boolean(result.warnings?.length || failures.length));
  } catch (error) {
    message(error.message, true);
    if (error.budget) renderBudget(error.budget); else if (state.icp?.search_mode === "Apollo + Brave") await loadBudget();
  }
  finally { button.disabled = !state.compatibleBackend; button.textContent = "Search companies"; }
});
document.querySelectorAll(".tabs button").forEach((button) => button.addEventListener("click", () => {
  state.filter = button.dataset.filter;
  document.querySelectorAll(".tabs button").forEach((item) => item.classList.toggle("active", item === button));
  renderLeads();
}));
$("#lead-search").addEventListener("input", renderLeads);
$("#lead-rows").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const lead = state.leads.find((item) => String(item.id) === button.dataset.id);
  if (!lead) return;
  try {
    if (button.dataset.action === "history") {
      if (state.history[lead.id]) delete state.history[lead.id];
      else state.history[lead.id] = await api(`/api/services/${state.service}/leads/${lead.id}/history`);
      renderLeads();
    } else if (button.dataset.action === "active") {
      await saveReview(lead, "active");
    } else {
      openReview(lead, button.dataset.action);
    }
  } catch (error) { message(error.message, true); }
});
$("#review-cancel").addEventListener("click", () => { $("#review-dialog").close(); state.reviewing = null; });
$("#review-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const { lead, decision } = state.reviewing || {};
  if (!lead) return;
  const form = $("#review-form");
  try {
    await saveReview(lead, decision, form.elements.reason.value, form.elements.note.value.trim());
    $("#review-dialog").close();
    state.reviewing = null;
  } catch (error) {
    $("#review-error").textContent = error.message;
    $("#review-error").classList.remove("hidden");
  }
});
$("#lead-rows").addEventListener("change", async (event) => {
  const select = event.target.closest(".status-select");
  if (!select) return;
  try {
    const selected = select.value;
    const note = selected === "new" ? "" : prompt("Optional: add a short note about the actual response (or leave blank).", "");
    if (note === null) { renderLeads(); return; }
    const updated = await api(`/api/services/${state.service}/leads/${select.dataset.id}/status`, { method: "PATCH", body: JSON.stringify({ status: selected, notes: note ?? "" }) });
    state.leads = state.leads.map((lead) => lead.id === updated.id ? updated : lead);
    renderLeads();
    message("Interest status saved.");
  } catch (error) { message(error.message, true); await loadLeads(); }
});
