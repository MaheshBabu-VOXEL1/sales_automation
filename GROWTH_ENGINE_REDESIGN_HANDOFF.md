# Voxel1 Growth Engine redesign — current work and continuation handoff

Prepared: 14 October 2026. For Claude or another developer continuing this work.

> **Status update, 14 October 2026 (Claude):** The redesign described below has since been completed locally. `web/app.js` and `web/extra.css` were rewritten for the new shell. `growth.py` was revised: tasks and drafts gained a type/purpose label and an optional time, approved drafts can be recorded as posted or sent by you, manual companies appear in lead history, and unknown routes return 404. Backend tests are in `tests/test_growth.py`. Every visible control was exercised in a browser against a throwaway database with fictional `.test` data, at desktop and phone width, in light and dark themes. PostgreSQL behaviour and the Render deployment remain unverified. Sections 2–6 below describe the earlier, unfinished state and are kept for history.

## 1. User request and confirmed scope

The user supplied `D:\Downloads\Voxel1 Growth EngineV2.html` and requested:

> “I want like this and all buttons should work.”

The reference contains five services. When asked which to implement, the user explicitly chose:

> **Training and BIM Services only (keep current scope).**

Apply the reference's navy/neutral design, sidebar, top bar, KPI cards, Daily rhythm, Leads, Content, approvals queue and lead-room layout to those **two** service pipelines. Keep the existing company-search, ICP, budget, candidate-review and history functionality.

The user then interrupted implementation and asked for this Markdown description. This document reports the actual partial state; it does not claim the redesign is finished.

## 2. Critical current status

**The local working tree is incomplete and is not ready to deploy.**

- Baseline commit at the start of this redesign: `e15e4dd` — `Add candidate reject/archive review with reasons and history`.
- The new backend module and route hooks have been written, but have **not been tested**.
- The HTML shell and stylesheet have been changed to the reference design.
- **`web/app.js` is still the previous Prospect Desk implementation. It does not match the new HTML.** Existing selectors refer to elements that are no longer present. The new controls are not connected, and the local page should not be represented as usable.
- `web/extra.css` is also still the previous version and needs integration with the new layout.
- No new frontend rendering, click handlers, browser validation or redesign tests have been completed.
- No application startup or migration run was performed for the redesign. Writing migration code is not evidence that it ran successfully.
- No commit or push was made for this redesign. These edits have not been deployed by Codex.
- No Apollo, Brave or Gemini request was made. No paid search, outbound message or social publication was triggered.
- Prior test totals from earlier work do **not** certify these new changes.

Do not push the partial working tree to `main`: Render deploys that branch. Finish the frontend/backend integration and validation first. If the user needs the previous local interface immediately, preserve the unfinished files before intentionally restoring only the affected frontend files from the baseline; do not discard unrelated work.

## 3. Files changed so far

| File | Actual change | Status |
| --- | --- | --- |
| `growth.py` | New Python module implementing persistent settings, tasks/drafts, approvals, lead-room metadata, manual lead creation and events. | Written; untracked at handoff; not tested. |
| `server.py` | Imports `growth`; initializes its tables; exposes read/write routes; checks paused state before new searches. | Modified; not tested. |
| `web/index.html` | Replaced the old page layout with a Growth Engine header, sidebar/main containers and editor dialogs. Preserved the ICP form inside a dialog. | Partial shell; no matching JavaScript yet. |
| `web/style.css` | Copied the reference's main custom stylesheet, including navy/neutral palette, panels, tables, sidebar, cards and dark-theme rules. | Base design only; needs responsive/visual review and integration fixes. |
| `web/app.js` | No redesign changes yet. | Must be rewritten/adapted; currently incompatible with the new shell. |
| `web/extra.css` | No redesign changes yet. | Must be reviewed for obsolete/conflicting rules and new dialog/form styles. |

The reference HTML is read as design/sample data. It has not been imported as live business records. Its sample customers, won deals, engagement counts, scheduled posts and simulated agent activity are **not evidence of real Voxel1 work**.

## 4. Backend additions already written

### Tables created by `growth.init`

These are additive tables; the existing `leads`, ICP, budget and review tables are retained.

| Table | Purpose and key fields |
| --- | --- |
| `growth_settings` | One row each for `training`, `bim`, and `global`; `paused`, `goal`, `strategy`. Default goals are 0, not the reference's sample sales targets. |
| `growth_items` | Internal tasks, content drafts or outreach drafts; service, optional lead ID, title, body, owner, channel, due date, state, revision, creation/update timestamps. |
| `growth_leads` | Existing lead ID with service, sales stage, owner and private room notes. |
| `growth_events` | Workspace actions, linked item/lead IDs where relevant, JSON details and timestamp. This is not per-user attribution; the app still uses shared-account authentication. |

New tables use the server's existing SQLite/PostgreSQL identity strategy. Real PostgreSQL migration behavior has not been exercised for this redesign.

### Routes wired into `server.py`

All writes go through the existing authentication and same-origin checks. The new `growth_write` helper maps validation failures to HTTP 400 and stale-revision conflicts to HTTP 409.

| Method and route | Intended behavior implemented in Python |
| --- | --- |
| `GET /api/growth` | Returns workspace settings, items, lead-room metadata and up to 200 recent growth events. Also reports email/social/calendar connections as false. |
| `PUT /api/growth/settings/{service}` | Saves pause state, goal and strategy for `training`, `bim`, or `global`. |
| `POST /api/growth/companies` | Adds a manually entered company to the existing leads table. Uses a generated `manual/…` source ID; validates service, website scheme and basic email format. |
| `PUT /api/growth/leads/{lead_id}` | Saves sales stage, owner and room notes for an existing lead in the specified service. |
| `POST /api/growth/items` | Creates a task, content draft or outreach draft. |
| `PATCH /api/growth/items/{item_id}` | Edits an item or applies an action using its current revision. |

`POST /api/services/{service}/discover` now checks whether that service or the global workspace is paused before starting discovery. Existing budget checks still follow. **Pause stops new searches; it does not cancel an already-running provider call.** UI wording must reflect that.

### Data and action rules implemented in the new module

- Sales stages: `new`, `engaged`, `meeting`, `proposal`, `negotiation`, `won`, `lost`.
- Item kinds: `task`, `content`, `outreach`.
- Channels: Internal, Email, LinkedIn, Instagram, WhatsApp and Phone. These are labels, not active provider connections.
- Item states: `pending`, `approved`, `rejected`, `done`.
- Actions: `approve`, `reject`, `complete`, `reopen`.
- Approving requires a nonempty content/outreach body. Tasks are completed, not approved.
- Only tasks can be marked complete. A content/outreach approval never sends or publishes anything.
- Paused workspaces reject approval/completion actions. Draft editing remains possible.
- Editing an item resets its state to pending and increments its revision, invalidating prior approval.
- PATCH requires the current revision. Conditional updates reject conflicting concurrent edits.
- Linked leads must belong to the same service as the work item.
- Input lengths, goals and dates are validated. These checks still need tests and review.

## 5. Frontend shell already written

`web/index.html` currently contains:

- Voxel1 Growth Engine top bar.
- Workspace state, won/goal and approvals counter placeholders.
- Approvals, Dark mode and Pause all buttons.
- Empty `#side` and `#main` containers for dynamic rendering.
- A shared `#editor` dialog and form for future task/draft/lead/settings editing.
- An `#icp-dialog` containing the previous ICP form.
- A status-message element `#notice`.
- References to `/style.css?v=12`, `/extra.css?v=12` and `/app.js?v=12`.

The reference stylesheet was extracted into `web/style.css`. No screenshot comparison or layout validation has been done. The new shell needs JavaScript and additional styles before it works.

## 6. Intended next implementation work

### A. Complete the JavaScript application

1. Load `/api/growth`, both service ICPs and both lead lists using the existing authenticated API.
2. Render only Training and BIM Services in the sidebar.
3. Render metrics from saved data. Do not display fictional revenue, hot leads, room opens, forecasts or running agents.
4. Implement Daily rhythm as a real saved internal task list with due dates, owners and completion state. No scheduler exists yet: do not claim autonomous daily execution.
5. Implement Leads with search/status filters and selectable lead rooms. Preserve existing reject/archive/restore and event history behavior from the baseline `web/app.js`.
6. Implement lead-room stage, owner, private notes, contact/source details, related tasks/drafts and history. A private internal room is not yet a publicly shared client page.
7. Implement Content with new/edit/view draft controls, due dates, channel labels, approval/rejection/reopen and export/download of draft text. Approval must say “Approved draft”; it must not say “Sent”, “Published” or “Scheduled by the agent”.
8. Implement an approvals queue with service/type/state filters and links to related leads. Reuse backend revision checks; show conflict errors and reload the changed item.
9. Wire service and global pause/resume buttons to saved settings. Explain that pause blocks new searches and approval/completion, not already-running requests.
10. Wire sales-goal/strategy editing, theme switch, modal close/cancel/save and navigation/back controls.
11. Restore ICP saving and search-budget presentation. A search still requires the existing budget confirmation and server-side caps. Do not make a paid search while developing.
12. Add clear loading, empty, validation, failed-request and stale-data states. Every rendered action must have an actual handler.

### B. Preserve the current research workflow

- Training and BIM service IDs remain `training` and `bim`.
- Existing saved leads and manually entered review/interest history must survive migration and redesign.
- Keep Apollo/Brave/Gemini secrets on the server.
- Preserve monthly request caps, usage reservations and the explicit confirmation of estimated requests.
- Preserve Gemini screening provenance and the difference between plausible buyer fit and confirmed interest.
- Preserve candidate rejection/archive suppression during future searches.
- Keep provider-unavailable and missing-contact states honest.
- Do not seed the reference's example companies into production data.

### C. Validate before committing or deploying

Backend tests should cover:

- Creating, editing and reloading tasks/drafts/settings.
- Editing invalidates approval; stale revisions cannot overwrite newer changes.
- Service isolation and invalid lead links.
- Paused/global-paused searches make zero provider calls.
- Approval/completion restrictions and validation errors.
- Legacy leads/reviews survive additive initialization; initialization is repeatable.
- Existing budget, search, login and candidate-review tests still pass.
- PostgreSQL behavior, particularly additive tables, `RETURNING id`, transactions and conditional updates, is actually checked or explicitly reported as unverified.

Browser checks should exercise every button in both services: navigation, tabs, filters, task/draft creation and editing, approval/rejection/reopen, lead rooms, stages, review/archive/restore/history, ICP modal, goals, pause/resume, theme and cancellation. Reload the page to prove persistence. Check desktop and narrow layouts, keyboard focus, dialogs and readable contact text. Use fictional local fixtures with `.test` domains; never turn fixtures into production results.

Useful local commands after implementation:

```powershell
python -m unittest discover -s tests
node --check web/app.js
git diff --check
```

Use an isolated temporary database for development/testing. Do not point a local test server at Render's production database. No paid provider access is required to complete the UI and mocked integration tests.

## 7. Features that still require separate integrations

The current request authorizes a functional redesign, but working internal buttons are not evidence of working external delivery. This partial implementation does not add:

- Mailbox OAuth or real email sending/reply tracking.
- WhatsApp permission capture or messaging.
- LinkedIn/Instagram publication or analytics.
- Calendar booking or automatic reminders.
- Autonomous scheduled research, tender monitoring or task execution.
- Publicly shared client rooms or engagement tracking.

These must be explicitly shown as unconnected or omitted from actionable delivery controls until implemented. Existing user instructions keep calls human-only and paid searches paused. The reference's wording about agents sending/publishing must not become false success messages.

## 8. Suggested message to Claude

> Please continue the interrupted Growth Engine redesign in `D:\sale automation`. Read `GROWTH_ENGINE_REDESIGN_HANDOFF.md` and inspect the working tree before changing anything. Use `D:\Downloads\Voxel1 Growth EngineV2.html` as the design reference, but keep only Training and BIM Services. Codex wrote an untested `growth.py`, server route hooks, a new HTML shell and reference CSS; `web/app.js` is still the old implementation and is incompatible with the shell. Finish the UI/backend integration so every visible button works with persisted data, preserve the existing research/budget/review features, and use mocks for testing. Do not spend API credits, send messages or publish content. Do not present simulated reference data as real results. Validate the complete local app and report limitations before deployment.

## 9. Reporting status accurately

This handoff is the deliverable for the user's latest request. The redesign remains **partially written, untested, uncommitted and undeployed**. The next developer must finish the frontend and verify backend behavior before claiming that “all buttons work.”
