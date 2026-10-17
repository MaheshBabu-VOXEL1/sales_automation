# Failed-draft recovery — 16 October 2026

## Changes prepared in this workspace

- Daily Rhythm job history now shows the safe, specific reason for a new Gemini
  drafting failure: for example missing answer text, incomplete JSON, token limit,
  HTTP status, timeout, invalid fields or failed content rules.
- Provider HTTP bodies, raw model replies, prompts and credentials are not shown.
- The failed job retains an opaque failure token. This is an optimistic-concurrency
  marker, not a credential. It changes after each new confirmed generation failure.
- **Retry failed draft** appears for today's individual room, email, LinkedIn and
  WhatsApp jobs when the recorded failure is known to precede output persistence.
- The confirmation says a retry can consume another Gemini request and sends
  nothing. A new request requires explicit user action; there are no auto-retries.

## Safety checks

1. The endpoint requires the existing app sign-in and same-origin write checks;
   public demo mode cannot run retries.
2. Validate service, job identity, today's IST date, active campaign, workflow
   setting, pause state, active screened lead and current failure token.
3. Reject completed/running/changed jobs, jobs listing saved outputs, interrupted
   jobs and failures with uncertain persistence outcomes.
4. If a matching saved first-contact draft or current room output already exists,
   link the existing item rather than calling Gemini. Sent/rejected records are
   preserved; this action does not create a replacement for a human-rejected draft.
5. Check current Gemini allowance, counting both used and held requests. The
   generation path still performs its authoritative atomic reservation.
6. Keep the five daily attempts per draft type/channel, including retries. If all
   five attempts were already consumed, a retry is blocked without spending.
   Additionally permit at most two explicit retries for one job in one day.
7. Claim using a database compare-and-swap, serialize daily counters, and share
   an in-process generation lock with manual generation. A double-click does not
   make two paid requests for the same failed attempt.
8. Keep previous failures and each retry outcome in the additive
   `agent_retry_attempts` table; log retry-requested, reused and finished events.
9. Resulting outputs remain pending. A successful channel retry refreshes the
   saved outreach summary without re-executing the whole rhythm activity.

## Important behavior for existing failures

The earlier generic "Provider or storage operation failed" records do not contain
the new evidence/token. They do **not** get a Retry button automatically. The
system cannot safely infer a historical generation-only failure from a generic
saved message. Check logs and existing outputs before a separate regeneration.
No historical error has been rewritten or reclassified by this patch.

The new action is deliberately limited to individual draft jobs. Discovery,
research, partner/client aggregates, social batches and daily summaries are not
replayed through it. This avoids duplicate partial outputs or automatic external
requests. Monthly search exhaustion does not itself block an existing-lead Gemini
draft when a Gemini allowance remains.

## Verification

- Latest full local suite: **170 tests, OK, 5 PostgreSQL-only skips**.
- Includes 14 new recovery tests and 9 response-parser tests.
- JavaScript syntax and `git diff --check`: passed.
- Recovery tests cover request accounting, preserved failures, pending approval,
  stale tokens, simultaneous clicks, existing outputs, rejected records, pause,
  service isolation, authentication, daily/monthly caps, retry limit, field-type
  validation and unknown storage outcomes.
- Providers were mocked and scratch databases used. No live retry, production
  database connection, budget increase or send/publish was performed for testing.
- A fresh PostgreSQL run is **unverified**: Docker Desktop was attempted, but its
  engine was unavailable. Earlier PostgreSQL evidence predates this retry schema
  and counter-lock change and is not evidence for this patch.
- A real browser round-trip for the new button is **unverified**. The HTTP route
  is covered by isolated handler tests; syntax checks do not prove browser behavior.

## Load the changes on the laptop

The source files here have changed; an already-running Python process must be
restarted once to load them and create the additive retry-history table. Wait for
the current job to finish, stop the laptop server with Ctrl+C and restart using
the existing `start-local.ps1 -Run -HostedWorkerStopped` command while Render is
suspended. Refresh the browser to load app.js v22.

No commit or push was performed. The older response-only ZIP does not contain this
larger retry workflow; do not use that ZIP as the complete update for this change.
The fix does not enable campaigns, raise caps, change knowledge approvals or
make past failures automatically retryable. Worker-heartbeat timing during long
batches is a separate remaining improvement.

## Laptop runtime check — 16 October 2026, 11:51 IST

Started the updated app in the background after port 8001 was confirmed free.
Python listener PID: 20296; launcher PID: 11328.
Verified real PostgreSQL-backed login, growth API, confirmation guard and refusal
of uncertain legacy retries. Worker heartbeat advanced to 11:50:46 IST with no
reported worker error. Existing items, campaign configuration and provider usage
matched the saved baseline: 32 pending items; Gemini 74 requests used.
No live draft generation, sending or publishing was performed.
Repeated automated suite: 170 tests passed, five PostgreSQL tests skipped.
Browser interaction with the new retry button remains unverified.
Logs: data/laptop-server-current.out.log and data/laptop-server-current.err.log.

## Browser verification and status improvements — midday update

The Retry failed draft button was exercised in a disposable local app using a
mock provider and scratch database. One retry created one pending draft, removed
the retry action and linked Review saved output to the correct lead/draft.
Evidence: data/retry-browser-success.jpg. No real provider call was made.
This supersedes the earlier unverified browser round-trip note.

The dashboard now refreshes read-only data every minute while idle and visible.
It skips open dialogs, lead rooms and focused fields. Worker runtime distinguishes
an active batch from the last completed heartbeat; a long batch is not proof of
continued provider progress. Two worker lifecycle regressions were added.
Latest suite: 172 tests passed, five PostgreSQL-only skips. Polling guards and
JavaScript syntax also passed. The updated laptop server has been restarted.
Fresh disposable PostgreSQL concurrency coverage remains unverified.

Latest live verification after the final restart: port 8001 belongs to Python
PID 20260 (launcher 5608). Worker runtime reports running; authentication and
retry guards pass. Production items/configuration/provider counts match baseline.
The disposable QA server was stopped after testing. The real app remains running.

## Final PostgreSQL and live evidence — supersedes earlier limitations

The final code passed 176 tests on disposable PostgreSQL 17.11 (one SQLite-only
migration test skipped), including concurrency, retry and Training tests. SQLite
passed 176 tests with five PostgreSQL skips. Logs are saved under ignored data/.
The temporary PostgreSQL cluster was stopped after testing.

An authorized live Gemini email test created pending item 34 for Jacobs, using
one request (74 → 75). A second browser first-contact action reused item 34 with
no additional request. All prior item states/revisions, campaigns and caps were
preserved. Final live listener PID 2692; launcher 21756. See
WORKFLOW_VERIFICATION.md and todayplane.md section 12 for the complete handover.
