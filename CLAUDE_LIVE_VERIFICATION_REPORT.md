# Voxel1 Growth Engine — Live Verification Report

Audit of the BIM Services and Training workspaces against the "draft creation first" requirement. Outlook, OAuth, sending and publishing were out of scope and were not tested.

---

## A. Overall verdict: **Partially ready**

The code for automation up to reviewable drafts exists, and isolated tests show it working. **Production is not running it.**

- The deployed frontend matches commit `b8f5e93` byte-for-byte, and the code behaves as documented in isolated simulation. Scheduling, once-per-day claims, pause/resume, explicit "needs input" blockers and the review controls all worked.
- The production database tells a different story:
  - **Complete draft rhythm has never been enabled.** BIM still runs the older "discover + email drafts" campaign.
  - **Training has no campaign at all.**
  - The only automated work production has ever recorded is one BIM discovery and four email drafts, all on 2026-10-15.
  - None of the 10 BIM or 7 Training rhythm activities has run live.
- The production budget cannot support the full rhythm. 4 of 5 monthly searches and 38 of 60 Brave requests are already used. A full BIM rhythm uses about 4 search reservations a day, so it would report **needs budget** on its first day.
- **Live draft quality is weak.** It is safe in tone, but it is generic. It omits the Scan-to-BIM objective and once states an unverified AI-screening claim as fact. One draft is addressed to a contact whose "verified" email belongs to an unrelated organisation.

**Does the draft-only scope meet the boss's expectation?** The *software* can, once configured. The *live system* does not yet "finish all tasks up to draft creation" automatically for either service. Configuration, budget, hosting proof and data-quality work are needed before a pilot.

---

## B. Verification context

| Item | Value |
|---|---|
| URL | https://sales-automation-u8lk.onrender.com/ |
| Date/time | 2026-10-15, about 14:45–15:15 IST (09:15–09:45 UTC) |
| Deployed version | Frontend files match `b8f5e93` exactly (SHA-256 of committed `web/app.js`, `web/index.html` and `web/style.css` equals what the server returns). `/draft-rhythm-guide` serves the `b8f5e93` guide (identical hash). Backend version inferred from this; no version endpoint exists. |
| Repository commit | `b8f5e93` on `main`, in sync with `origin/main`. Untracked: `CLAUDE_READ_ORDER.md`, `PROJECT_STATUS.md`. |
| Hosting | Render web service. Database is PostgreSQL 17.11 (`/api/system`); `render_internal_host: false`. Render plan not visible to me. |
| Account | The user's existing signed-in browser session (shared login). I did not enter credentials. |
| Services | BIM Services and Training |
| Test environments | (1) **Live, read-only:** browser UI plus same-origin GET requests. (2) **Isolated local copy:** same code, scratch SQLite DB, no provider keys, port 8006. (3) **Simulation script:** scratch SQLite, Gemini and Brave mocked, no network. (4) **Unit tests:** repository suite. |
| Production changes made | **None.** No saves, approvals, edits, rejections, pauses or provider calls on production. I opened the Sales Goal dialog and closed it without saving. |

---

## C. Results table

Evidence key: **L** = live browser/API, **I** = isolated local copy (real code, test DB), **S** = simulation with mocked providers, **C** = source inspection, **T** = unit tests (mocked).

| # | Feature | Expected behavior | Actual behavior | Status | Evidence | Required change |
|---|---|---|---|---|---|---|
| 1.1 | Site loads, deployed version | Loads; latest commit deployed | Loads in about 3–5 s ("Loading your workspace…"). Frontend is byte-identical to `b8f5e93`. | PASS | L | Add a `/api/version` endpoint returning the commit SHA. |
| 1.2 | Login protection | Unauthenticated access blocked | No cookie: `/api/*` returns 401; `/` and `/draft-rhythm-guide` redirect to `/login`; writes return 401. Sign-in itself was not exercised (I don't enter passwords). | PARTIAL | L, C | None for gating. A person should do one sign-in/sign-out test. |
| 1.3 | Both workspaces | BIM and Training selectable | Both available with their own header, KPIs, rhythm, leads and content | PASS | L | — |
| 1.4 | Service separation | Records not mixed | BIM shows 7 leads and 3 BIM drafts; Training shows 11 leads and 0 drafts. Approvals filters show BIM 3 / Training 0. All queries filter by `service`. | PASS | L, C | — |
| 1.5 | Navigation | Tabs, Approvals, lead room work | Daily rhythm, Leads, Content, Approvals, "Open lead" → lead room all worked. No console errors other than the 401s my own unauthenticated probes caused. | PASS | L | — |
| 1.6 | Mobile (375 px) | No horizontal page scroll | `scrollWidth` = 375. KPI cards scroll inside their own row. | PASS | L | — |
| 1.7 | Performance | Responsive | `/api/growth` took 2.7 s and `/api/budget` 1.6 s, each opening a new PostgreSQL connection | PARTIAL | L, C | Connection pooling; split the snapshot. |
| 2.1 | Sales Goal fields | Objective, strategy, countries, size, roles, keywords, dates, content targets | All present in the dialog (live and local) | PASS | L, I | — |
| 2.2 | Saves and persists | Values survive refresh | Local: every field, including Complete draft rhythm, target/partner/client accounts, intro paths, proof and consent, persisted after reload | PASS | I | — |
| 2.3 | Complete draft rhythm option | Available and persists | Available. Production still set to "Keep current discovery / selected drafting". | PASS (feature) / not enabled live | L, I | Business decision to enable (see H). |
| 2.4 | Invalid values | Rejected with clear messages | End before start, impossible date, draft before discovery, content target over 10, bad quarter, min size above max, and missing budget confirmation are all rejected with clear messages | PASS | I | — |
| 2.5 | Contradictory but accepted values | Warn | A campaign that ended in 2020 saves and "activates" silently. A quarter outside the campaign dates is accepted. | PARTIAL | I | Warn when the campaign is already over, or when the quarter falls outside the dates. |
| 2.6 | Jobs use saved configuration | Jobs read current config | Every tick reads `agent_campaigns.config`. Research uses saved countries and keywords; drafts use objective and strategy. | PASS | C, S | — |
| 2.7 | Goal changes vs existing drafts | Clear rules | Saving never edits existing drafts. It affects only future jobs, and releases today's `needs_input`/`needs_budget` slots. Completed and uncertain jobs are not replayed. | PASS | C, T | Say this in the dialog. |
| 2.8 | Numeric target vs strategy | Distinct | Distinct fields (quarterly won target vs strategy/objective). Production shows "Sales goal (all time) 0/0" because the legacy campaign has no goal or quarter. | PASS | L, C | — |
| 3.1 | Real automated jobs live | Saved jobs and outputs | All-time job table: 1 `discovery` (done, 4 leads) plus 4 `draft:*` email drafts, all on 2026-10-15. **No `rhythm:*` jobs ever.** | PARTIAL | L | Enable the full rhythm and fund the budget. |
| 3.2 | Server vs manual output | Distinguishable | Live jobs come from the worker (`agent_jobs`). Outputs carry `rhythm_output_created`/`ai_drafted` events. | PASS | L, C | — |
| 3.3 | Runs without a browser | Background worker | A daemon thread ticks every 30 s inside the web process. Live: discovery ran at 11:33 IST and drafts at 11:41 IST rather than 06:00/09:00. Probably the campaign was created then and caught up, but I couldn't confirm the cause. | PARTIAL | L, C | Log the worker heartbeat and campaign-save time. |
| 3.4 | Once per day / duplicates | No duplicates | `INSERT … ON CONFLICT … RETURNING` claims per (service, IST day, job). A repeated tick added 0 items in every simulation. Live: refreshing created nothing. | PASS | S, T, L | — |
| 3.5 | Restart recovery | No replay | `recover()` marks `running` jobs `interrupted`; it never retries them. Open search reservations keep their full estimate. | PASS (code) | C, T | — |
| 3.6 | Multiple workers | Safe | Claims are atomic in the database. But `recover()` at start-up marks **another live instance's** running jobs interrupted (for example, during a zero-downtime deploy overlap). README states "one server process". | PARTIAL | C | Make instance count 1; store the owner instance on claims. |
| 3.7 | Campaign dates | Future and ended campaigns skipped | Start/end compared as IST date strings. Covered by tests. | PASS | C, T | — |
| 3.8 | Missed activities | Defined | Same day: all overdue slots run at the next tick (catch-up burst). Past days are never backfilled. | PASS (as documented) | C, S | — |
| 3.9 | 24/7 continuity | Proven | Not provable from a browser visit. Only one day of jobs exists. Render plan unknown (free web services sleep when idle, which stops the in-process worker). Worker errors log only "Daily planning failed" with no detail. | NOT TESTED / unproven | L, C | See section G. |
| 4.1 | Service / global pause | Blocks new work and paid calls | Simulation: global pause at 09:05 meant no further claims. `claim()`, `active()` before each paid call, and `save_item` all check pause. Not exercised live (would interrupt production). | PASS (S/T) | S, T, C | — |
| 4.2 | In-flight request when paused | Defined | The in-flight request finishes. Research and discovery stop before the next request. A generated draft is discarded if pause began during generation, and it still counts against budget. | PASS (code) | C, T | — |
| 4.3 | Resume | Due work proceeds once | Resumed at 14:05: deferred slots ran once, same totals as the unpaused run (13 Gemini calls), 0 duplicates | PASS | S | Consider spreading resumed work out instead of running it all at once. |
| 5 | BIM rhythm (10 activities) | Each produces output or an explicit blocker | Live: none executed (rhythm disabled). Simulation, production-like inputs: 06:00/06:30 `needs_input` (Brave storage rights), 07:00 mapping brief, 07:30 room drafts, 09:00 LinkedIn/WhatsApp drafts, 10:00 `needs_input` (no partner), 11:00 `no_action`, 14:00 `needs_input` (no client), 16:00 three social drafts but `needs_you` (proof missing), 18:00 summary but `needs_you` (research blocked). With complete inputs, all produce outputs. | PARTIAL (works in S; not live) | S, L | Enable live; provide inputs (H). |
| 6 | Training rhythm (7 activities) | Same | Live: no campaign. Simulation: 06:00 `needs_input`, 09:00 academic draft, 10:00 LinkedIn/WhatsApp drafts, 11:00 `no_action`, 14:00 `needs_input`, 16:00 social `needs_you`, 18:00 summary. The UI rhythm table omits the 18:00 summary row. | PARTIAL | S, L | Create the Training campaign; show the 18:00 row. |
| 7.1 | Apollo discovery | Relevant companies | Live run 4: Apollo 10, Brave 8, Gemini 6 requests, 4 Saudi leads added. Older leads from multi-country searches (USA/UAE) remain active in BIM. | PARTIAL | L | Review and archive off-target leads. |
| 7.2 | Contact accuracy | Provider status ≠ accuracy | DAR Engineering's contact shows a "Verified work email (Apollo)" on an **unrelated development-bank domain**, and the 09:00 draft is addressed to that person. Company phones are correctly labelled "not a direct line". Obfuscated names are handled ("To the BIM Manager"). | FAIL (data) | L | Flag an email whose domain doesn't match the company website. |
| 7.3 | Training lead quality | Plausible buyers | 11 Training leads: **0 Gemini-screened**, none with a recorded reason. Several look like BIM vendors, training/e-learning providers, a job board or a trade publication. | FAIL (data) | L | Rescreen or archive; re-run discovery with a Training-specific profile. |
| 7.4 | Brave research and storage rights | Blocked without `BRAVE_SEARCH_STORAGE_ALLOWED=1`, with explanation | Simulation: `needs_input` with a clear message, no request made, nothing stored. Other drafting continued. Not enabled live (rights unconfirmed; correctly left alone). | PASS | S, T | Confirm the Brave plan before enabling. |
| 7.5 | Research coverage | Explicit | Briefs state queries, named accounts covered and first-5 countries; 60 accounts batch into 12 queries | PASS (S/T) | S, T | — |
| 7.6 | Publisher links | Support the claims | No live research briefs exist to open | BLOCKED | L | Needs live research output. |
| 7.7 | Gemini screening | Not treated as intent | UI labels it "AI judgement, not proof of need". But a draft restated the screening note as fact (see E). | PARTIAL | L | Tighten the prompt (F-H3). |
| 8 | Draft quality, all types | Reviewed live for both services | Live: only 4 BIM first-contact emails exist. No Training drafts, rooms, LinkedIn/WhatsApp, partner, follow-up, customer, social or brief outputs exist live. | PARTIAL / BLOCKED for 10 of 11 types | L | Enable the rhythm, then review real outputs. |
| 9.1 | Drafts in the correct workspace and Approvals | Yes | Live: 3 pending BIM drafts in BIM and in Approvals, counts consistent (header 3, filters 3) | PASS | L | — |
| 9.2 | View, edit, reject, approve | Work and persist | Local: approve → `approved`; reject → `rejected`; edit persists and returns the item to pending with a new revision; stale edit → 409 | PASS | I | — |
| 9.3 | Safe rendering | No HTML injection | Seeded `<img onerror>` and `<script>` were shown as literal text; 0 injected elements | PASS | I | — |
| 9.4 | Approval does not send | No delivery | Approval changes state only; Outlook queue stayed empty | PASS | I | — |
| 9.5 | Room needs Apply to room | Explicit | "Record as sent" on a room → 400 "Use Apply to room". Apply replaced the outline and kept owner and stage. | PASS | I | — |
| 9.6 | Stale room overwrite | Blocked | Team edited notes after approval: apply with the old timestamp → 409. After reload, apply succeeds and **replaces the newer team note** without the draft being re-reviewed. | PARTIAL | I | After a room conflict, require re-approval or show a diff. |
| 9.7 | Room revision without a loop | One revision per real change | Rooms are redrafted daily after apply because each day's unverified search matches change the context fingerprint (see F-M1). 4 days gave 4 room drafts for one lead. | FAIL | S | Exclude volatile research hits from the fingerprint. |
| 9.8 | Briefs use Mark reviewed | Not "sent" | UI shows "Mark reviewed" and no Record-as-sent button. The API still accepts `complete` on a brief. | PASS (UI) | I, C | Reject `complete` for briefs on the server. |
| 9.9 | Recorded-sent integrity | Sent record preserved | A "done" (recorded sent) message has a **Reopen** button, and edit also works. Either one returns it to pending and erases the sent state. | FAIL | I, C | Lock done outreach; use "correct record" with audit. |
| 10.1 | Graphic preview, SVG, PNG | 1080×1080, works | Preview `<img>` decodes 1080×1080. SVG served with a strict Content-Security-Policy. PNG export reproduces as a 1080×1080 PNG of about 134 KB. Edited text updates the card. Missing item → 404. | PASS | I | — |
| 10.2 | Long titles and special characters | No clipping | Characters are escaped correctly. **Headline clipping:** a realistic all-caps line "COORDINATION WORK WITHOUT" ends at x=1090 on a 1080-wide card. Title is cut to 4 lines and the paragraph to 300 characters, with no ellipsis. | FAIL | I | Measure width/size per line; add an ellipsis. |
| 10.3 | Nature of graphics | Typography cards | Navy/white text-only SVG cards; no photographs, no AI imagery | PASS | C, I | — |
| 10.4 | Live graphics | Inspect | No Instagram/Facebook drafts exist live | BLOCKED | L | — |
| 11.1 | Shared Gemini cap | All draft types count | Every path calls `reserve_ai_draft` first. Simulation usage ledger shows room, social, LinkedIn/WhatsApp, partner, academic and cross-sell all counted. | PASS | S, T, C | — |
| 11.2 | Search/Brave caps | Respected, not raised | Research reserves a search slot plus N Brave requests atomically; budget-blocked → `needs_budget`. Caps are environment-only. | PASS | C, T | — |
| 11.3 | Failed requests counted | Counted | Failed Gemini attempts are counted; interrupted searches hold their full estimate | PASS | T, C | — |
| 11.4 | Live budget sufficiency | Enough for the rhythm | Searches 4/5, Brave 38/60, Gemini 37/100, Apollo 22/100 (2026-10) | FAIL (config) | L | Raise caps deliberately (H). |
| 11.5 | Releasing blocked work | Releases without replay | Saving the goal sets today's `needs_input`/`needs_budget` slots to `retry_ready`; done and uncertain jobs untouched | PASS | T, C | — |
| 12.1 | Test suite | Passes | `python -m unittest discover -s tests` → **Ran 104 tests, OK** (8.3 s, Python 3.10.11) | PASS | T | — |
| 12.2 | JS syntax | Valid | `node --check web/app.js` (Node 22.15.0) → OK | PASS | T | — |
| 12.3 | PostgreSQL behavior | Tested | Tests are SQLite-only. PostgreSQL appears only as one mocked connection test. Production runs PostgreSQL and hasn't exercised the rhythm SQL. | PARTIAL | C | Add a PostgreSQL CI job. |
| 12.4 | Secrets | Not exposed | `/api/growth` reports only names of missing variables. No keys in the frontend; the DB URL is never returned. | PASS | L, C | — |

---

## D. Live evidence

### D1. Live browser/API (production, read-only)

- **Campaigns:** only `bim`. Objective "Find companies needing Scan-to-BIM services in Saudi Arabia and prepare outreach to book discovery meetings". Start 2026-10-15, no end; discovery 06:00, drafts 09:00 IST; countries [Saudi Arabia]; min size 500; roles "BIM Manager, Head of Design, Technical Director". **No `full_rhythm`, `quarter`, `content_targets` or account/proof fields.** Training: no campaign.
- **All jobs ever recorded** (newest first, UTC):
  - `bim/2026-10-15/draft:21` needs_approval → item 4 (06:12:03)
  - `draft:20` → item 3 (06:11:52)
  - `draft:19` → item 2 (06:11:41)
  - `draft:18` → item 1 (06:11:31)
  - `discovery` done: found 4, added 4, leads 18–21 (06:04:22)
- **Search runs (2026-10):**
  - #1–#3 on 2026-10-14
  - #4 at 2026-10-15T06:03:32Z: estimate Apollo 17 / Brave 10 / Gemini 10; actual 10 / 8 / 6
- **Budget:** searches 4/5; Apollo 22/100; Brave 38/60; Gemini 37/100; nothing held.
- **Items:** 4 total, all BIM Email First contact.
  - Items 2–4 are pending.
  - Item 1 is `done` at revision 3 (updated 06:37:40Z). Someone recorded it as sent. I left it untouched.
- **Flags:** daily planning disabled for both services; no pauses (BIM, Training, global all 0); `automation_missing: []`, so all keys and caps are present.
- **UI text:** both rhythm tables show "Draft rhythm disabled — Enable Complete draft rhythm in Sales Goal" on every row. The UI does not claim work is happening.
- **Lead room:** DAR Engineering's room shows "Verified work email (Apollo)" on a domain unrelated to the company website, and labels the company phone as "not a direct line". Address redacted here.

### D2. Isolated local copy (real code, test DB, records labelled `[TEST]`)

Approve, reject, edit, stale-edit 409, safe rendering, room apply and stale-conflict 409, Mark reviewed, Reopen of a recorded-sent item, graphics (SVG/PNG/edit/clipping), and Sales Goal validation and persistence. Results are in table rows 2.x, 9.x and 10.x.

### D3. Simulation (mocked Gemini/Brave, scratch DB)

Script: scratchpad `simulate.py` and `roomloop.py` (not committed).

- **Production-like day:** results in rows 5 and 6. 13 Gemini calls, 0 Brave calls, 0 duplicates on re-tick.
- **Complete inputs, 3 days:** 23 → 36 → 49 items; 28 Gemini and 12 Brave calls; 0 duplicates. Partner and customer drafts are reused rather than re-requested.
- **Pause 09:05 → resume 14:05:** nothing claimed while paused; identical final state; no duplicates.
- **Room redraft after apply:** 1, 2, 3, 4 room drafts over 4 days for one lead.

### D4. Unit tests (mocked providers)

104 passing. These prove control flow, accounting and data boundaries. They don't prove live provider behaviour or PostgreSQL SQL.

---

## E. Draft-quality feedback

Only four live drafts exist, all BIM first-contact emails from the older pipeline. No live examples exist for Training, LinkedIn or WhatsApp messages, partner or academic, follow-up, customer enquiry, room outline, social posts or briefs. **Those types could not be quality-reviewed.** Mocked simulation text says nothing about quality.

**What's good**
- Honest, restrained tone. No pilots, prices, case studies or invented results. Every email has an opt-out line and "The Voxel1 team" sign-off.
- Handles a missing name properly: item 4 opens "To the BIM Manager at Nesma & Partners" because the provider name was obfuscated.
- Each message has one clear next action (short call).

**What's weak**
1. **Objective not reflected.** Every subject says "Scan-to-BIM…", but no body mentions Scan-to-BIM, laser scanning or point clouds. Bodies describe generic "modelling, coordination, and documentation".
2. **Unverified claim stated as fact.** Item 4: "We noticed your work in Saudi Arabia and your implementation of BIM and ISO 19650 certification." That comes from the Gemini screening note, which the system itself labels unverified. Item 1 similarly says "As a firm actively utilizing BIM standards". The prompt says screening notes aren't facts, but the model still used them.
3. **Wrong-person risk.** Item 2 is addressed by name to a contact whose "verified" email is at an unrelated organisation.
4. **Repetitive template.** All four bodies share the same three sentences in slightly different order. There's no project, tender or role-specific angle, because no research or room facts feed these legacy drafts.
5. **Weak call to action.** "How we can support your upcoming work" doesn't connect to the discovery-meeting objective (no proposed agenda or scope question).

**Factual-risk controls seen in code:** the rule check (`ai_draft.check_rules`) blocks prices, pilots, cities and case studies. It does not block an unverified screening note being stated as fact. Public posts receive no lead data (test-covered).

---

## F. Defects and improvements

### Critical

**F-C1. The complete draft rhythm is not running in production, for either service.** *(Configuration and operations, not a code bug.)*
- **Reproduce:** BIM → Daily rhythm shows "Draft rhythm disabled" on every row. Training → "Set a Sales Goal to start…". All-time `agent_jobs` contains no `rhythm:*` row.
- **Impact:** the boss's direction ("finish all tasks up to draft creation") isn't being delivered live. Only BIM email drafts after discovery are produced.
- **Fix:** after F-C2 and the data clean-up, set BIM and Training Sales Goals with "Automate all rhythm activities up to review drafts", real inputs and campaign dates.

**F-C2. The monthly caps can't fund the rhythm.** *(Configuration.)*
- **Evidence:** searches 4/5 and Brave 38/60 used on 2026-10-15.
- **What a full day uses:**
  - BIM reserves a search slot for 06:00, 06:30 and 18:00 research, plus discovery: about 4 searches a day.
  - Training uses 1–2 a day.
  - Each research activity can use up to 12 Brave requests.
- **Impact:** day one ends in `needs_budget` for research. Discovery has only one search left this month.
- **Fix:** the account owner sets caps based on cost, roughly 150+ searches/month for both services and Brave sized at about 12 × research runs. Or turn research off until the Brave storage-rights plan is confirmed.

### High

**F-H1. Continuous operation is unproven and hard to monitor.**
- `server.py:973-985` runs the worker as a thread inside the web process.
- On failure it logs only "Daily planning failed" with no exception, service or job detail.
- There's no heartbeat or "last tick" visible in the UI, and no alerting.
- The Render plan is unknown. A free web service sleeps when idle, and the worker sleeps with it.
- **Fix:**
  - Confirm a paid, always-on instance with instance count 1.
  - Log `logging.exception` with job context.
  - Persist a `worker_heartbeat` row and show "last tick" in the UI.
  - Add an external uptime check and a daily "jobs ran" alert.

**F-H2. Lead and contact data quality.**
- **BIM:** DAR Engineering's contact email domain doesn't match the company website, yet it's labelled "Verified work email (Apollo)" and a named draft was prepared. Leads from earlier USA/UAE searches remain active in a Saudi campaign.
- **Training:** all 11 leads are unscreened, with no recorded reason. Several look like competitors, training providers, a job board and a trade publication. Training outreach would therefore stall at `needs_input`.
- **Fix:**
  - Add a domain-mismatch warning, and don't use a mismatched contact's name in drafts.
  - Show "Apollo email status" instead of "Verified".
  - Review and archive bad leads, then re-run Training discovery with a buyer-specific profile.

**F-H3. Drafts restate the AI screening note as fact and ignore the campaign service focus.**
- **Code:** `ai_draft.write_draft` / `lead_facts` pass `ai_reason`. The rule check doesn't catch "We noticed your … certification".
- **Fix:**
  - Pass the screening note under an "internal_assessment_do_not_quote" key, or omit it from outbound drafts.
  - Pass service keywords (for example Scan-to-BIM) explicitly.
  - Add a check that each draft mentions the campaign's service focus.

### Medium

**F-M1. Daily room redraft loop after apply.**
- `draft_outputs.room_context` puts the **current day's** research hits into the context fingerprint (`draft_outputs.py:29-36`). Once a room is applied, each new day's different (or missing) search matches change the fingerprint.
- `room_candidates` then drafts a new room, up to 5 a day per service, each costing Gemini.
- **Reproduce (simulation):** apply the room each morning → 4 drafts in 4 days for one unchanged lead.
- **Fix:** fingerprint only stage, team updates and *new* verified signals since the last applied draft. Or require a lead-specific signal not previously seen.

**F-M2. Graphic headline clipping and silent truncation.**
- `draft_outputs.graphic_svg` wraps the title at 25 characters, 62 px bold, with no width measurement. All-caps lines overflow (measured right edge 1090 px).
- Titles are cut to 4 lines and the paragraph to 300 characters, with no ellipsis.
- **Fix:** shrink the font for uppercase or wide text, or wrap at about 20 characters for uppercase. Add "…" when truncated. Add a test that checks the estimated text width.

**F-M3. Reopening or editing a recorded-sent message erases the sent record.**
- `web/app.js:136-137` shows Reopen for `done` items, and `growth.save_item` allows edits that reset the state to `pending`.
- **Impact:** the follow-up rhythm (based on `state='done'`) loses the record. The message can be approved and "sent" again, and the sent history no longer reflects reality.
- **Fix:** make `done` outreach immutable. Add a separate "correct record" action with an audit event.

**F-M4. Status semantics don't match the guide.**
- Missing consented proof makes the 16:00 activity `needs_you`, although the guide reserves that status for provider failures. Research blocked by rights makes 18:00 `needs_you` too.
- Partner and customer jobs report "drafted" when they reused an existing pending draft.
- **Fix:** use `needs_input` for missing proof; say "existing draft still awaiting review" when reusing one.

**F-M5. Multi-instance and restart edge.**
- `automation.recover()` at start-up marks every `running` job `interrupted`, including jobs another live instance is still running during a deploy overlap.
- **Fix:** record the instance ID on claims, or pin the Render service to a single instance with no overlap.

**F-M6. The login rate limiter is keyed on the proxy address.** *(Source; plausible, not tested live.)*
- `server.py:765` uses `client_address`. Behind Render's proxy, all users may share one address, so five failed attempts by anyone could lock everyone out for a minute.
- **Fix:** use the trusted `X-Forwarded-For` hop.

### Low

- **F-L1.** No warning when a campaign has already ended or the quarter falls outside the campaign dates.
- **F-L2.** The Training rhythm table doesn't show the 18:00 daily summary that the code produces.
- **F-L3.** The Training header says "Active" with no campaign. Better: "No campaign".
- **F-L4.** After a room-apply conflict, a reload lets the older approved draft overwrite a newer team note without re-review.
- **F-L5.** The API accepts `complete` on briefs (the UI hides it).
- **F-L6.** Social posts get only two alternating variation prompts; expect repetition over weeks.
- **F-L7.** Sessions live in memory, so every deploy or restart signs users out.
- **F-L8.** `/api/growth` takes about 2.7 s per load; there's no connection pooling.
- **F-L9.** No version endpoint.

### Test gaps

- No PostgreSQL integration test for the rhythm/claim SQL; production runs PostgreSQL.
- No multi-day room fingerprint test. The existing test covers only a same-day apply.
- No graphic width/overflow test.
- No test that `done` outreach can't be reopened or edited.
- No test of worker exception handling or logging.
- Every provider is mocked, so no live-format contract test for Gemini/Brave responses.

---

## G. Automation reliability

**Proven by code plus isolated runs**
- Once-per-service-per-IST-day claims, with no duplicates on re-tick or refresh.
- Pause blocks new claims and the next paid request. Resume completes today's unclaimed work once.
- Restart doesn't replay running or uncertain work.
- Campaign start/end dates are respected.
- Past days aren't backfilled.
- Missing inputs, rights and budget produce explicit statuses, never fabricated output.
- Every Gemini, Brave and search attempt is reserved against the caps before it's sent.

**Proven live**
- The worker ran unattended once on 2026-10-15: discovery, then 4 drafts about 8 minutes later.
- Nothing was duplicated across my refreshes.

**Unproven**
- That the process stays up 24/7. Only one day of jobs exists, and the Render plan and sleep behaviour are unknown.
- That slots fire near their scheduled times. Live jobs ran at 11:33/11:41 IST, not 06:00/09:00; the cause is unknown.
- PostgreSQL behaviour of the rhythm queries and claims under real load.
- Recovery after a real restart mid-job.
- Behaviour during a deploy overlap of two instances.

**Evidence needed:** 7 consecutive days of `agent_jobs` rows for both services with timestamps close to schedule; a visible worker heartbeat; Render logs showing no restarts or sleeps; and an uptime monitor.

---

## H. Missing prerequisites

**Configuration and business inputs (not bugs)**
1. Decision to enable **Complete draft rhythm** for BIM and create a **Training** campaign. Needs: objective, quarterly target and quarter, countries, roles, sizes, dates, and daily LinkedIn/Instagram/Facebook targets.
2. **Real named target accounts** (about 60 for BIM), **actual PMC/consultant partners** and a **college/university** saved as leads, **actual existing clients** (for Training, VITALS/XIM customers), and **known introduction paths**.
3. **Approved proof / trainee-story facts**, with written permission for public use.
4. **Budget:** caps sized for daily research plus discovery plus drafting. The current 5 searches/month and 60 Brave requests aren't enough.
5. **Brave plan with storage rights**, confirmed by the account owner before `BRAVE_SEARCH_STORAGE_ALLOWED=1`. Until then, research activities stay `needs_input`.
6. **Hosting:** an always-on paid Render instance, single instance, plus monitoring and alerting.
7. **Lead clean-up:** archive off-target Training and BIM leads; verify the DAR Engineering contact.

**Application changes (bugs and improvements):** F-H1 logging and heartbeat, F-H2 domain check, F-H3 prompt facts, F-M1 to F-M6, plus the Low items and test gaps.

---

## I. Recommended next steps (draft automation only)

1. **Fix F-H3 and F-M1, and add the F-H2 domain warning.** Do this before turning on more automated drafting, so the volume increase doesn't multiply weak or redundant drafts.
2. **Fix F-M2 (graphic overflow) and F-M3 (immutable sent records)**, with tests. Add a PostgreSQL CI job.
3. **Add worker observability (F-H1):** exception logging, a heartbeat and a "last run" in the UI, plus a version endpoint.
4. **Confirm hosting:** always-on, single instance, and an uptime monitor.
5. **Clean the lead data:** archive bad Training leads and verify BIM contacts.
6. **Set budget caps deliberately** for a two-service rhythm, and decide on Brave storage rights. If they aren't confirmed, accept research as `needs_input`.
7. **Enter the real business inputs** in each Sales Goal, then enable Complete draft rhythm, BIM first.
8. **Run a 7-day observed pilot:** review every output type for both services each day, and track job timestamps, budget use, blockers and duplicates.
9. **Then extend to Training,** and only afterwards to platform integrations.

---

## J. Plain-English summary

1. **What's working?** The site is up, private and on the latest code. BIM and Training are kept separate. The Sales Goal form has every field, validates input and saves correctly. Approvals, edit, reject and room-apply controls behave safely, and approving never sends anything. Pause and resume work, and nothing runs twice. Graphics export as 1080×1080 SVG and PNG. Budget accounting is careful, and all 104 tests pass. On production, the older "discover then draft emails" automation did run by itself once.
2. **What isn't working?** The full draft rhythm isn't switched on in production, and Training has no campaign, so almost none of the scheduled activities have ever run live. The budget caps are too small for it. Lead data has real problems: a contact email from an unrelated organisation, and Training leads that look like competitors or job boards. Live email drafts are generic, skip the Scan-to-BIM focus, and once present an AI guess as fact. In testing, room drafts get regenerated every day after being applied, long all-caps graphic headlines run off the card, and a "sent" record can be reopened and lost.
3. **What couldn't be verified?** 24/7 operation of the hosted worker; on-time firing of scheduled slots; quality of 10 of the 11 draft types, since none exist live; publisher-link accuracy of research, since none exists; PostgreSQL behaviour of the new rhythm code; and the sign-in flow itself (I don't enter passwords).
4. **Feedback.** The guardrails are good: no invented partners, clients, proof or sends. The next gains come from better input data and sharper prompts, not more automation. Each draft should use the campaign's specific service and only verified facts.
5. **What to change first.** Stop drafts stating screening guesses as facts and add the service focus. Fix the daily room redraft. Add contact-domain checks. Add worker logging and a heartbeat. Then set realistic budgets and real business inputs, and enable the rhythm for BIM.
6. **Evidence still needed before saying "everything works."** Seven straight days of on-schedule job records for both services with no duplicates. Real, reviewed examples of every draft type for both services. Confirmed always-on hosting with monitoring. A PostgreSQL test run. Confirmed Brave storage rights, or research consciously left off.
