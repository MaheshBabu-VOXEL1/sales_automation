# Office-computer overnight run — Claude handoff

## Request from Mahesh

Run this Growth Engine on this office Windows computer overnight, using the API
settings in the local `.env` and the existing Render PostgreSQL database. The
Render **web service** must be suspended first; PostgreSQL must remain running.
Prepare and check BIM's scheduled draft workflow. Collect evidence and report
what actually ran, what was blocked, and what still needs work.

This is a real run against the shared business database, not a disposable demo.
Scheduled discovery and drafting may use the existing provider allowances.
Keep the existing request caps. Do not buy credits or increase caps without the
owner's explicit decision. Outputs must remain reviewable drafts.

## Read before starting

- `start-local.ps1` and the current startup code in `server.py`.
- `DRAFT_RHYTHM_GUIDE.md` and `FIX_REPORT.md`.
- `claudePlane.md` and `MEETING_REQUIREMENTS_ANALYSIS.md` for business context.
- The existing knowledge-pack documentation/files if present. Check their actual
  approval state; a website claim does not become approved because it is in a file.

Use paths relative to this extracted project directory. Do not assume it is
still `D:\sale automation`, or that this computer has the same Python setup.
Inspect the current files rather than relying on a previous test count/version.

## 1. Confirm the copy and machine

1. Confirm the ZIP was extracted to a normal writable directory.
2. Confirm it includes `server.py`, `requirements.txt`, `web`, the application
   Python modules, knowledge-pack files, `start-local.ps1`, and **`.env`**.
   A GitHub ZIP will not include the Git-ignored `.env` or untracked launcher.
3. Treat `.env` as secret. Never print it, paste values in chat, include them in
   reports/screenshots, or commit it. Inspect only whether values are present.
4. Check Python 3.10+ and install dependencies if necessary:

   ```powershell
   python --version
   python -m pip install -r requirements.txt
   ```

   If `python` is unavailable, check `py -3`. Install Python or use its explicit
   path if needed. Ensure the launcher uses that same Python installation.
5. Check whether port 8001 already has a server. Identify it before starting
   another instance. Do not terminate unrelated processes or an earlier QA server
   simply because its port or name looks similar.
6. Keep power and internet connected. Disable automatic **computer sleep while
   plugged in** for this test, recording the original setting for restoration.
   Display sleep is fine. Locking Windows is fine; signing out is not.
   A laptop must not sleep when its lid closes. Keep ventilation unobstructed.

## 2. Confirm the hosted worker is stopped

Ask Mahesh to confirm that Render's `sales_automation` **web service status is
Suspended**, or verify it in the dashboard if access is available. A confirmation
dialog alone is not proof of suspension. Do not delete the service, suspend the
database, or change Render environment variables.

The app's own Pause controls are shared database settings: pausing in Render also
pauses the local worker. They are not a way to stop only the hosted process.

If suspension is not confirmed, complete safe preparation but do not start the
local worker. The existing startup recovery logic must not run alongside the
hosted worker. Only one application worker should use this database during the test.

## 3. Validate configuration without starting automation

Run from this project folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1
```

This only loads/checks required values. It does not establish that API keys work.
The execution-policy override applies to this invocation, not the machine policy.

Check the PostgreSQL driver and perform a read-only connection check with a short
timeout. Use `.env`'s `DATABASE_URL`, which must be the **External Database URL**
for access from this computer. Do not log the URL or unsanitized connection errors.
Do not silently switch to SQLite if the connection fails.

**Do not run the test suite with this production DATABASE_URL.** Test helpers
create and change tables. Do not seed, reset, migrate destructively, or import QA
fixtures into this database. Normal additive application startup is expected.

Before starting, record a sanitized baseline in `data/overnight-baseline.json`:
local/UTC times, row counts, campaign configuration excluding private material,
pause state, item IDs/states/revisions, existing job IDs/results, worker timestamp,
and monthly budget usage/remaining amounts. No credentials or personal contacts.
Use a read-only connection. Create `data` if missing; it is Git-ignored.

## 4. Start the local server

Only after confirming the hosted service is suspended:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1 -Run -HostedWorkerStopped
```

The flag records a condition YOU must verify; it does not suspend Render itself.

Starting the server also starts the real worker, which can execute already-due
campaign jobs immediately within existing caps. It does not wait for a browser.

Keep the server alive after Claude's turn ends. Use a persistent terminal where
available. If a detached process is needed, start it hidden, redirect stdout and
stderr to separate files under `data`, and record the exact process/PID and stop
procedure. Never put secrets in command-line arguments. Do not depend on an
execution-tool session that is automatically killed when the agent finishes.

Open **http://localhost:8001** (or the configured local port), sign in privately,
and verify the existing records. If a ZIP lacks `.git`, `/api/version` may report
`unknown`; record that limitation instead of inventing a commit hash.

## 5. Prepare BIM for this test

Inspect the saved campaign first and preserve existing useful settings. Previously
BIM used the older discovery/email mode; Training had no campaign. Recheck current
state because another session or person may have changed it.

The intended BIM goal is to find Scan-to-BIM opportunities in Saudi Arabia and
prepare relevant outreach. Use those already agreed inputs; do not invent sales
targets, partners, clients, outcomes, account lists or proof.

- Set **Required service focus** to `Scan-to-BIM` for this BIM campaign.
- Enable **Complete draft rhythm** for the BIM overnight test and save the
  campaign, preserving its legitimate targeting, strategy and other settings.
- Confirm campaign dates include the next morning. If they do not, ask for the
  intended test dates before changing them. Use this machine's actual IST date.
- Confirm the global and BIM controls permit execution. If intentionally paused
  by someone else, establish the reason before resuming. Leave Training's
  campaign/configuration unchanged.
- Inspect desired daily social targets. If all are zero, explain that no social
  drafts will be produced and obtain the owner's desired counts rather than
  choosing extra paid work silently.
- Keep `BRAVE_SEARCH_STORAGE_ALLOWED=0` unless the owner confirms the account has
  result-storage rights. Missing rights should appear as **needs input**.
- Missing real partners, customers and approved proof should remain visible
  blockers; do not add fictional data to make the rhythm appear complete.
- Confirm any knowledge pack is connected and distinguish approved material from
  unapproved website-derived claims. Do not approve new claims on the owner's behalf.

Budget warning: the last reported monthly balance was only **1 search and 22 Brave
requests**, plus a limited Gemini balance. These figures may have changed. Read
the current ledger and caps. Local execution shares the same database ledger and
does not reset allowances. If the owner has not approved higher caps, keep them
and label this a limited overnight execution/blocker test, not a full-rhythm pass.

Do not send/publish anything, connect Outlook/WhatsApp/social platforms, approve
drafts, apply rooms, or mark work as sent merely to exercise the interface.

## 6. Verify before Mahesh leaves

- Confirm existing leads and drafts are present in the local interface.
- Confirm BIM shows the saved required focus/full-rhythm setting and the intended
  active dates and pause state.
- Observe at least two advancing worker heartbeats. Expect the 30-second wait
  **plus execution time**, not an exact 30-second interval. Record actual times.
- Check the worker logs for connection/startup failures without exposing secrets.
- Verify Windows sleep is disabled while plugged in and the server process will
  survive Claude finishing its response. Leave the machine powered on.
- Tell Mahesh the local URL, exact process/log locations, what is enabled, the
  remaining budgets, expected blockers, and how to stop the server.

Record these checks in `OVERNIGHT_RUN_REPORT.md`. If a prerequisite prevents
launch, record **not started** and the precise next action. Do not claim success.

## 7. What to check the next morning

Unless a separate monitor has actually been installed, Claude does not wake itself
up automatically. On Mahesh's next request, read the saved jobs, timestamps,
provider ledger and local logs and complete `OVERNIGHT_RUN_REPORT.md`.

Compare with the baseline and report:

| Check | Evidence to collect |
|---|---|
| Worker availability | Last heartbeat plus available logs; two morning samples alone cannot prove uninterrupted overnight uptime |
| 06:00 tender research | Saved result or explicit rights/budget/provider blocker |
| 06:30 project/award research | Same, including actual coverage |
| 07:00 decision-maker mapping | Linked internal brief and accurate source-based limitations |
| 07:30 room preparation | Pending room drafts or clear blocker; no silent overwrite |
| Later activities | Check only activities already due at the observation time; mark future ones not yet due |
| Draft quality | Campaign focus, supported facts, suitable tone, useful next step; no invented certification or relationship |
| Duplicate prevention | Jobs and output IDs compared with baseline; avoid replaying jobs manually |
| API costs/usage | Actual ledger change by provider and configured cap |
| Data integrity | Earlier item states/revisions retained unless a legitimate recorded action explains a change |

Use **PASS / FAIL / BLOCKED / NOT YET DUE / UNVERIFIED** with supporting timestamps,
job IDs and output IDs. Separate application defects from missing business inputs,
rights and budget. Keep contact details and secrets out of the report.

A night ending before 09:00 cannot verify 09:00 outreach or afternoon content.
No paid call should be made just to label a future slot passed. A successful first
night is evidence for the pilot, not proof of seven days of reliable operation.

## 8. Switch back to Render tomorrow

1. Allow any in-flight provider task to finish where practical.
2. Stop this local server with **Ctrl+C** and wait for exit. If it was started
   detached, stop only the recorded process and its own worker process, checking
   its identity first. Confirm the listener/process has stopped.
3. Only then resume the Render web service. Keep the PostgreSQL database running.
4. Wait for Render to become Live, sign in and verify the same saved overnight
   records plus advancing worker heartbeat and expected campaign state.
5. Existing due-but-unclaimed activities may run when Render resumes. State that
   clearly; do not reset claims, clear history or change dates to force retries.
6. Restore the office computer's original power settings when overnight testing
   is finished and report the handover. Render Free can sleep again after resume;
   this overnight arrangement does not solve permanent cloud availability.

Do not commit, push, redeploy code or change API caps as part of this handoff.
The report should end with what worked, what failed/blocked, draft-quality feedback,
and the next specific changes needed.
