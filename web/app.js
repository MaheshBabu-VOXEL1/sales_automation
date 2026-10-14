const state = { service: null, icp: null, compatibleBackend: true, leads: [], filter: "all" };
const countries = [["US", "USA"], ["AE", "UAE"], ["SA", "Saudi Arabia"], ["IN", "India"], ["SG", "Singapore"]];
const countryCode = (name) => countries.find((item) => item[1] === name)?.[0] || null;
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const safeUrl = (value) => { try { const u = new URL(value); return ["https:", "http:"].includes(u.protocol) ? u.href : null; } catch { return null; } };

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
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
    $("#search-disclaimer").textContent = providerMode ? "Apollo finds companies and people; Brave links matching BIM/Revit website pages. These are candidate matches, not verified purchase intent. Email and phone are not enriched. No messages are sent." : "The public-map source covers one city sample in each listed country, not the whole country. Other countries need Apollo and Brave keys. Data © OpenStreetMap contributors. No messages are sent.";
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

function renderLeads() {
  const leads = state.leads;
  $("#stat-total").textContent = leads.length;
  $("#stat-contact").textContent = leads.filter((lead) => lead.email || lead.phone).length;
  $("#stat-interested").textContent = leads.filter((lead) => lead.status === "interested").length;
  $("#stat-not").textContent = leads.filter((lead) => lead.status === "not_interested").length;
  $("#country-summary").innerHTML = (state.icp?.countries || []).map((name) => `<span><strong>${esc(name)}</strong><small>${leads.filter((lead) => lead.country?.toLowerCase() === name.toLowerCase() || lead.country === countryCode(name)).length} companies</small></span>`).join("");
  const text = $("#lead-search").value.trim().toLowerCase();
  const visible = leads.filter((lead) => (state.filter === "all" || lead.status === state.filter) && lead.company.toLowerCase().includes(text));
  $("#empty").classList.toggle("hidden", visible.length > 0);
  $("#empty").textContent = leads.length ? "No companies match this filter." : "No companies yet. Set your ICP and choose “Search companies.”";
  $("#lead-rows").innerHTML = visible.map((lead) => {
    const web = safeUrl(lead.website);
    const source = safeUrl(lead.source_url);
    const email = lead.email ? `<span class="contact-line"><a href="mailto:${encodeURIComponent(lead.email)}">${esc(lead.email)}</a></span>` : "";
    const phone = lead.phone ? `<span class="contact-line"><a href="tel:${encodeURIComponent(lead.phone)}">${esc(lead.phone)}</a></span>` : "";
    const contact = `${lead.contact_name ? `<strong>${esc(lead.contact_name)}</strong><small>${esc(lead.contact_title)}</small>` : ""}${email}${phone}` || "<small>No contact found</small>";
    return `<tr><td data-label="Company"><strong>${esc(lead.company)}</strong><small>${esc(lead.category)}</small>${web ? `<div><a class="source-link" href="${esc(web)}" target="_blank" rel="noopener noreferrer">Website ↗</a></div>` : ""}</td><td data-label="Location">${esc(lead.city)}<br><small>${esc(lead.country)}</small></td><td data-label="Public contact">${contact}</td><td data-label="Interest status"><select class="status-select ${esc(lead.status)}" data-id="${lead.id}" aria-label="Interest status for ${esc(lead.company)}"><option value="new" ${lead.status === "new" ? "selected" : ""}>Unreviewed</option><option value="interested" ${lead.status === "interested" ? "selected" : ""}>Interested</option><option value="not_interested" ${lead.status === "not_interested" ? "selected" : ""}>Not interested</option></select>${lead.notes ? `<small class="contact-line">${esc(lead.notes)}</small>` : ""}</td><td data-label="Source">${source ? `<a class="source-link" href="${esc(source)}" target="_blank" rel="noopener noreferrer">Evidence ↗</a>` : "—"}</td></tr>`;
  }).join("");
}

document.querySelectorAll(".service-card").forEach((card) => card.addEventListener("click", () => openService(card.dataset.service)));
$("#back").addEventListener("click", () => { $("#workspace").classList.add("hidden"); $("#home").classList.remove("hidden"); state.service = null; });
$("#icp-form").addEventListener("submit", async (event) => { event.preventDefault(); try { await saveIcp(); } catch (error) { message(error.message, true); } });
$("#discover").addEventListener("click", async () => {
  const button = $("#discover");
  button.disabled = true;
  button.textContent = "Searching…";
  message("Searching companies and checking public website evidence. This can take a few minutes.");
  try {
    await saveIcp(false);
    const result = await api(`/api/services/${state.service}/discover`, { method: "POST" });
    await loadLeads();
    const searched = result.coverage.length;
    const failures = result.coverage.filter((item) => item.error).map((item) => item.country);
    message(`${result.source}: checked ${searched} selected countr${searched === 1 ? "y" : "ies"}. Found ${result.found} relevant companies; ${result.added} added.${result.warnings?.length ? ` Some checks failed: ${result.warnings.join(" ")}` : ""}${failures.length ? ` Search errors: ${failures.join(", ")}.` : ""}`, Boolean(result.warnings?.length || failures.length));
  } catch (error) { message(error.message, true); }
  finally { button.disabled = false; button.textContent = "Search companies"; }
});
document.querySelectorAll(".tabs button").forEach((button) => button.addEventListener("click", () => {
  state.filter = button.dataset.filter;
  document.querySelectorAll(".tabs button").forEach((item) => item.classList.toggle("active", item === button));
  renderLeads();
}));
$("#lead-search").addEventListener("input", renderLeads);
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
