# Workflow verification — 16 October 2026

Scope: today's draft-first workflow, through human review. No delivery integration,
publication, paid-plan purchase, budget increase or permanent-hosting deployment.

## Live output review

Reviewed saved records, job results and generation events read-only. A local audit
is retained in data/live-workflow-audit.json; it contains business records and is
ignored by Git. Credentials are excluded from reports.

| Sample | Assessment | Disposition |
|---|---|---|
| Nesma email 33 | Scan-to-BIM in body, neutral role greeting for masked name, call question, opt-out; broader disciplines/LOD are website-derived and still require owner confirmation | Remains pending |
| Jacobs new live email | Scan-to-BIM and laser-scan modelling, brief discovery question, no assumed project/location/relationship, proper opt-out | New live test saved pending; no send |
| DAR email 2 | Named greeting despite current domain mismatch; service focus only in title | Historical item retained pending; do not send without correction/contact verification |
| DAR email 5 | Neutral greeting and Scan-to-BIM in body | Recipient still needs verification |
| LinkedIn 14–17 | Focus present; some references to current Saudi projects lack recorded project evidence; capability statements need owner review | Retained pending; edit before approval |
| WhatsApp 18–21 | Focus and short call request; some broad capability claims and project assumptions need review | Retained pending; opt-in not proven, no delivery |
| Nesma room 23 | Separates known facts, unverified assessment and unknown project/budget/timing; suggested scope is not an approved customer requirement | Internal pending review; room outline unchanged |
| Contact map 13 | Explicitly labels unverified bid authority, introductions, masked names and domain mismatch | Internal review only |
| Summary 22 | Lists source job outcomes, failures and missing inputs; service-wide inventory is labelled | Historical summary retained; self-running line corrected for future summaries |

Duplicate-looking emails were generated at distinct event times (for example DAR
items 2 and 5; Nesma items 4, 7 and 33). History alone does not identify who clicked
or prove a scheduler duplication. The scheduler already avoids saved first-contact
emails; the manual AI route lacked that reuse check. It now returns the latest
pending/approved first-contact email instead of spending again. Existing items
and audit history are preserved; rejected drafts can be deliberately replaced.

## Draft context coverage

- Email, LinkedIn, WhatsApp, partner, academic, follow-up and cross-sell paths use
  recorded lead facts and the campaign focus; outbound focus validation applies.
- BIM company knowledge reaches supported outreach, room and public-post paths.
  Held/withdrawn facts are excluded. Website-published facts are not owner approval.
- Room prompts separate AI screening assessments from facts. Internal rooms and
  scope-call briefs, and public educational posts, do not share the outbound
  exact-focus validator. Social prompts receive the offering and scoped knowledge.
- There is no Training knowledge pack. The Training offer is explicit in its
  email prompt; no BIM delivery-company description is forced into that prompt.
- This is prompt/rule validation, not an independent fact-check of arbitrary AI text.

## BIM activity audit

| Activity | Actual live status or prerequisite |
|---|---|
| Discovery | Saved successful run; further discovery blocked at search cap 5/5 |
| 06:00 tenders / 06:30 awards | needs input: Brave storage rights unconfirmed |
| 07:00 mapping | Saved internal contact map awaiting review |
| 07:30 rooms | Saved pending rooms; legacy failed SAPAC job requires review, no blind retry |
| 09:00 outreach | Saved pending messages; two legacy channel failures retained with uncertainty warning |
| 10:00 partner | needs input: actual PMC/consultant and matching saved lead |
| 11:00 follow-up | no action: no eligible recorded sent email older than three days or proposal/scope call |
| 14:00 clients | Scheduled; missing actual client records is an explicit tested blocker |
| 16:00 content | Scheduled; all live content targets 0, so no live social generation expected |
| 18:00 summary | Scheduled; prior-day saved summary reviewed, final-time execution tested in isolation |

Future activities were exercised with fixture clocks and data, not by moving the
production clock or inventing customer records.

## Training verification

Isolated Training fixtures use a college buyer, department role, a Training goal,
BIM training focus, fixture partner/client/proof data, and social targets. Tests
exercise rooms, Email/LinkedIn/WhatsApp drafts, content on all three channels,
daily summary, repeat-run idempotency and service isolation. Provider responses
are mocked and outputs remain pending. Existing tests cover pause, missing inputs,
budget failures, approvals, edits/rejections and room application.

All 11 current Training leads have ai_screened=0. Some names indicate service or
education suppliers; names alone cannot establish fit. Do not activate a live
Training campaign until buyers are reviewed. No live Training records were changed.

## Operating arrangement

One laptop app uses the existing shared PostgreSQL database. Render web service
must remain suspended, per the user's operating arrangement. That remote setting
was not independently inspected this session. Logs and process identities are
saved locally. Use Ctrl+C for a visible launcher; for this background run, stop
only the recorded Python listener process after checking that jobs are idle.
Restart from this workspace with:

    powershell -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1 -Run -HostedWorkerStopped

Keep the laptop awake. Background execution does not survive sleep/shutdown.
Permanent supervision and a continuous-uptime pilot are future hosting work.

## Business decisions

WORKFLOW_INPUTS.md contains the actual fields and templates required. Missing
partner/client/proof data, owner knowledge approval, contact verification, social
targets and Brave rights cannot be resolved from app login credentials. They
remain explicit prerequisites, without made-up values or cap changes.

## Final verification results

- SQLite: 176 tests, OK, five PostgreSQL-only skips.
- PostgreSQL 17.11: 176 tests, OK, one SQLite-only legacy migration skip.
  All PostgreSQL concurrency tests and new retry/Training tests passed.
- JavaScript syntax, dashboard refresh guards and Git diff checks passed.
- Live Gemini draft: item 34, Jacobs, created 16 October at 12:08:53 IST;
  model gemini-3.5-flash-lite; pending; no delivery.
- Before/after ledger: Gemini 74 → 75. Apollo 32 and Brave 46 unchanged.
  Pending drafts 32 → 33. Search runs remain 5. All original item revisions/states,
  campaigns and caps were preserved.
- Browser retry round-trip: disposable mock-provider app, one pending output and
  working review link. No fabricated production failure was inserted.
- Evidence: data/live-final-check.json, data/sqlite-final-tests.log,
  data/postgres-final-tests.log and data/live-draft-jacobs-20261016.jpg.

Portable PostgreSQL was downloaded from EDB's official distribution and used only
for the disposable localhost voxel1_test database. It is not a Windows service
and is stopped after verification. Source: https://www.postgresql.org/download/windows/.

Technical draft-workflow implementation and verification is complete for this
checklist. Business activation is still conditional on WORKFLOW_INPUTS.md.
The app is draft-ready with documented blockers, not proof of live outreach,
all future provider success or continuous uptime. No commit, push or deployment
to Render was performed.

## Final live handover

Final Python listener PID: 2692; launcher PID: 21756. The worker completed a tick
at 12:15:41 IST without an error. Browser first-contact reuse returned item 34;
ledger verification after that action still shows Gemini 75 and 33 pending items.
No second request or duplicate was created. The test PostgreSQL listener on
55432 is stopped. The app remains running with the pending Jacobs draft open.

## Setup visibility follow-up

The live Daily Rhythm now includes Workflow setup, with explicit prerequisite
messages and a working Review Sales Goal setup link. Zero-target future social
slots and activities outside campaign dates no longer imply imminent execution.
No settings were saved during browser verification. Four new setup-guidance
checks bring the local suite to 180 tests, OK with five PostgreSQL-only skips.
The earlier PostgreSQL suite remains 176 tests, OK with one SQLite-only skip;
no database mutation/schema behavior was added in this display follow-up.
Screenshot: data/workflow-setup-live.jpg. Live app listener: PID 23200,
launcher PID 7976. Business inputs remain outstanding as listed in WORKFLOW_INPUTS.md.

## Partner requirement restored — latest owner decision, 16 October

The owner requested undoing the no-partner preference after confirming sir's
original scope. BIM partner_enabled is now true. Today's original needs_input
outcome was restored from the disable audit event. All other campaign fields
were preserved; no draft generation, cap change or sending was performed.
Partner details are once again required for this activity to produce a draft.
This supersedes the earlier owner decision to disable partners. The optional
setting remains available in the product, but is currently enabled for BIM.

## Remaining workflow verification completed for the deferred-input scope

After sir deferred partner/client setup, verified login, current worker health,
approval queue filtering, saved draft viewing and the editor/cancel path in the
live app. The Jacobs item 34 body contains Scan-to-BIM and remains pending.
No production approval, send, reject, edit-save or new Gemini call was made in
this verification pass. Existing prior corrections remain intact.

The final read-only comparison passed: all BIM item bodies/states/revisions,
selected campaign settings and the complete budget/usage snapshot match the
start of this pass. Pending count remains 29. Gemini remains 75, Brave 46,
Apollo 32. Partner/client setup remains deferred; it is not a prerequisite for
accepting these draft-review checks. Features remain enabled and their historical
missing-input job records were preserved.

Prompt improvements are loaded in the restarted local server (listener PID 22552,
launcher PID 30880). Latest local suite: 185 tests OK, five PostgreSQL-only skips.
The previous PostgreSQL suite covers 176 tests; it was not rerun for these prompt
changes. Evidence: data/remaining-final-verification.json,
data/remaining-workflow-verification.json, data/remaining-review-verification.jpg
and data/sqlite-final-tests.log.

Still not claimed: a new successful Apollo/Brave search in this pass, independent
provider-plan storage-rights verification, a live Training campaign, zero future
AI errors, publishing/sending, or an uninterrupted 24-hour run. Overnight operation
still requires an awake host or a deployed server. No schedule claims were cleared
just to force a paid test. No commit or deployment to Render was performed.

## Live Apollo/Brave/Gemini discovery verification — 16 October, 16:16–16:18 IST

The user authorized a live discovery check before reporting to sir. Ran one
confirmed BIM Saudi Arabia search through the app, within existing limits.
Search run 6 completed successfully (HTTP 200), with no provider warnings.

- Apollo: 9 requests (1 company search, 3 people searches, 2 people matches,
  3 organization enrichments).
- Brave: 8 website search requests.
- Gemini: 6 buyer-screening requests.
- Returned 3 matching existing companies: El Seif Engineering Contracting,
  DAR ENGINEERING and Saudi Pan Kingdom Company - SAPAC. Added 0 new leads.
- These results prove a successful fresh execution of the search pipeline,
  not that new unique companies were found. Search currently uses the first
  candidate page; repeated searches can return the same companies.
- El Seif has a recorded work email with matching domain; DAR retains a mismatch;
  SAPAC has no work email. Recorded phones are not verified direct/mobile numbers.

After the refresh updated SAPAC, the real worker automatically created room item
35, job room:20:816569f7bca1, at 16:17:59–16:18:00 IST. It remains pending, with the
existing room outline unchanged. This used one additional Gemini room_draft
request, separate from the six screening requests. No test force/retry or clock
change was used. No message was sent or published.

Current usage: Apollo 41/100, Brave 54/100, Gemini 82/150; searches 6/15.
Held requests: 0. Pending approvals increased from 29 to 30 because of room 35.

Short live scheduler observation: five authenticated read-only samples between
16:17:47 and 16:19:59 IST, three distinct completed heartbeats, all reads successful,
no recorded worker error. The real 16:00 activity was recorded at 16:00:12 IST
and correctly reported zero social targets as missing input. Targeted rhythm and
worker tests also passed (12 + 2 tests). This is not a full-day uptime test.

A read-only follow-up in this chat is scheduled for the evening summary. It checks
worker health and the real 18:00 job at/after 18:10 IST, without forcing any work or
spending test requests. Automation ID: verify-voxel1-scheduled-evening-run.
Keep the laptop awake, the app/server running and Codex available for local checks.
The follow-up is intended to pause after its final result today. The 18:00 scheduled
outcome remains unverified until it occurs. Do not report 24/7 uptime from this test.

Evidence: data/live-discovery-20261016-verification.json,
data/live-discovery-provider-evidence.json, data/discovery-to-draft-evidence.json,
data/live-scheduler-observation.json and data/live-discovery-auto-room.jpg.

Evening follow-up health sample, 16 October at 16:44:33 IST: localhost:8001 was
reachable (listener PID 22552); completed worker tick 16:44:13 IST, about 20 seconds
old; worker running, idle, no recorded error. Read-only check only; no provider
requests, jobs, budgets or campaign settings changed. Evidence:
data/evening-health-20261016T111433Z.json. The 18:00 outcome is not yet due and
remains pending verification; follow-up stays active.

Evening follow-up health sample, 16 October at 17:41:35 IST: localhost:8001 was
reachable, listener PID 22552. Last completed tick 17:40:51 IST (about 45 seconds
old), worker running and processing a batch, no recorded worker error. Read-only
health check; no job/provider calls or settings changed. Evidence:
data/evening-health-20261016T121135Z.json. The 18:00 activity is not yet due;
its outcome remains pending verification, and the follow-up stays active.

### Terminal evening verification — 16 October 2026, 18:04 IST
BIM 18:00 job `rhythm:9` completed at 18:01:05 IST (`needs_review`), saving one pending Daily summary, item 37, at 18:01:03 IST. Evening research recorded one Brave request at 18:01:01 IST; no research issue was attached to the job. Usage Apollo 41 / Brave 55 / Gemini 82, held zero. Healthy worker tick 18:04:30 IST; no current worker error. Historical channel/room failures and deferred/missing setup still appear honestly in the summary. The check was read-only and triggered no work or external delivery. This proves this scheduled execution only, not continuous 24-hour uptime. Evidence: `data/evening-verification-20261016T123438Z.json`.

### Temporary test access for sir — 16 October 2026
User requested a shareable test link. Started a Cloudflare quick tunnel to the existing server on localhost:8001; no additional app worker was started. URL: https://kiss-feet-wit-challenging.trycloudflare.com
Public checks passed: HTTPS landing page 200 with login form; anonymous /api/growth returned 401. Authentication remains required. Authenticated public verification was blocked by automatic approval review because it would transmit local credentials through the external tunnel; no credentials were transmitted by that check. User/sir must perform interactive login. This URL is temporary and requires the laptop awake, internet connected, app server and tunnel running. No messages were sent to sir. Tunnel PID is recorded privately in data/sir-test-tunnel.pid; logs under data/sir-test-tunnel.*.log.
