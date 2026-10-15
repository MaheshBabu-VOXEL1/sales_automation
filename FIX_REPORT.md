# Fix report: CLAUDE_LIVE_VERIFICATION_REPORT.md, section F

Date: 2026-10-15. Scope: code defects in section F, BIM and Training draft automation only. Outlook and sending are out of scope.

Nothing is committed, pushed or deployed. Production settings, budgets, environment variables and campaigns are unchanged.

**Overall verdict stays "Partially ready."** These are code fixes verified locally. Production still has the draft rhythm off, budgets that are too small, and unverified hosting continuity (F-C1, F-C2 and the operational side of F-H1).

## Test evidence

```
python -m unittest discover -s tests          (SQLite)
Ran 137 tests in 18.831s
OK (skipped=5)                                 the 5 PostgreSQL-only concurrency tests

python tests/postgres_runner.py               (disposable PostgreSQL 17.11)
Ran 137 tests in 69.241s
OK (skipped=1)                                 the legacy SQLite-file migration test

node --check web/app.js
OK
```

- **Environment:** Python 3.10.11, SQLite, PostgreSQL 17.11 (same version as production), psycopg 3.3.6, Node 22.15.0.
- **Regression tests:** `tests/test_audit_fixes.py` has 28 tests. The suite had 104 tests before these fixes.
- **Mocks:** every provider (Gemini, Brave, Apollo) is mocked, so no paid calls were made.
- **Fault injection:** I turned each latest fix off in turn to confirm its test catches the bug:
  - setting the 7-day room limit to 0 makes the room test fail
  - disabling the service-focus check makes the focus test fail
  - restoring the earlier name-prefix domain matching makes `test_shared_domain_prefix_does_not_imply_affiliation` fail
  - restoring keyword-based focus, or "any one phrase is enough" matching, makes `test_generic_search_keyword_cannot_satisfy_required_focus` fail
- **Duplicate summary:** the duplicate daily-summary test fails against the earlier `automation.py`.

## PostgreSQL verification (2026-10-15)

**Setup.**
- A throwaway `postgres:17` Docker container (17.11, the same version production reports).
- Bound to `127.0.0.1:55432` only, with its data held in memory (`--tmpfs`) and a random one-time password.
- Removed after the run (`--rm`). The password file was deleted.

**Isolation from production.**
- `tests/postgres_runner.py` refuses any URL that isn't localhost and whose database name doesn't end in `_test`.
- It clears any inherited `DATABASE_URL`, so it can't reach the production database.
- It drops and recreates the test schema before every test.
- No production URL, credential or data was used, read or changed.

**Proof the run used PostgreSQL.** After the run, the test database held all 18 application tables (including `worker_heartbeat`) and about 7,500 committed transactions.

**What the first run found.** 33 of 132 tests failed or errored. None were application bugs:

| Cause | Tests affected | Fix (test code only) |
|---|---|---|
| Test helpers read rows back after INSERT/UPDATE. SQLite allows this; PostgreSQL raises "the last operation didn't produce records". | 19 | The `sql()` helpers in four test files return rows only when the statement produces them. |
| When those helpers errored inside Outlook `setUp`, its login-credential patches were never undone. That leaked into later tests as 401 responses. | 9 | Resolved by the helper fix. |
| Legacy-migration tests created a SQLite-style `id INTEGER PRIMARY KEY` table. PostgreSQL doesn't auto-number it. | 2 | Use an identity column on PostgreSQL. |
| `tuple(row)` on psycopg dict rows returns column names. | 1 | Read the named columns. |
| A test asserted the database is "sqlite". | 1 | Expects "postgresql" in the PostgreSQL run and checks the URL isn't exposed. |
| A test migrates a legacy SQLite *file*. | 1 | Skipped on PostgreSQL. |

I checked the application code for the same pattern (positional row access). Its only `lastrowid` use is on the SQLite-only path. No application changes were needed.

**New PostgreSQL-only tests** (`tests/test_postgres_concurrency.py`). These model two workers, such as during a deploy overlap, hitting the database at the same instant. All pass:
- `test_only_one_worker_claims_a_job`: 8 simultaneous claims, exactly 1 succeeds.
  - Fault injection: with a naive "check then insert" claim, this test fails.
- `test_concurrent_gemini_reservations_never_exceed_the_cap`: 12 simultaneous reservations against a cap of 5. Exactly 5 succeed and 5 are recorded.
- `test_concurrent_search_reservations_never_exceed_the_cap`: 10 simultaneous reservations against a cap of 3. Exactly 3 succeed.
- `test_two_workers_running_the_rhythm_together_create_no_duplicates`: two full rhythm passes at the same moment. No duplicate jobs, one daily summary, and exactly one Gemini call per saved draft.
- `test_heartbeat_upsert_from_two_workers`: concurrent heartbeat writes leave one consistent row.

**Upgrade of a production-shaped database.**
- I built a PostgreSQL database with the currently deployed code (`b8f5e93`, from `git archive`): a lead, a recorded-sent and a pending email, a legacy campaign, a job, and an old-scheme room event.
- I then started the new code on it twice.
- Results:
  - Row counts in all 8 checked tables are unchanged.
  - Item titles, states and revisions are unchanged.
  - The campaign objective is unchanged, and `service_focus` stays unset.
  - The only change is the new `worker_heartbeat` table.
  - Restarting is idempotent.

## Status by issue

| Issue | Status | Regression tests (`tests/test_audit_fixes.py`) |
|---|---|---|
| F-H3: screening note stated as fact; service focus ignored | **Fixed** (separate required service focus, checked in the output) | `test_outbound_facts_omit_screening_note_and_carry_service_focus`, `test_write_draft_prompt_has_focus_but_not_screening_note`, `test_scheduled_email_draft_gets_campaign_keywords`, `test_rhythm_messages_get_focus_without_screening_note`, `test_draft_missing_service_focus_is_discarded`, `test_generic_search_keyword_cannot_satisfy_required_focus` |
| F-M1: applied rooms redrafted daily | **Fixed** (search-only redrafts limited to one per lead per 7 days) | `test_applied_room_is_not_redrafted_daily_as_search_hits_change`, `test_new_search_urls_refresh_room_at_most_weekly`, `test_team_update_refreshes_room_without_waiting`, `test_legacy_room_digest_does_not_trigger_mass_redraft` |
| F-M2: graphic headline overflow, silent truncation | **Fixed** (also measured in a local browser) | `test_graphic_headline_fits_width_and_marks_truncation`, `test_short_graphic_text_is_unchanged` |
| F-M3: sent outreach could be reopened or edited | **Fixed** (no "correct record" action yet) | `test_recorded_sent_outreach_cannot_be_reopened_or_edited`, `test_ui_hides_reopen_for_recorded_sent_outreach` |
| F-H2 (code part): domain mismatch, "Verified" label, named drafts | **Fixed** (exact registrable-domain match only; webmail flagged; no affiliation inferred from similar names). Checked in a local browser; **unverified on the deployed site**. | `test_contact_domain_mismatch`, `test_shared_domain_prefix_does_not_imply_affiliation`, `test_browser_domain_check_mirrors_server`, `test_mismatched_contact_is_not_named_in_drafts` |
| F-H2 (data part): bad leads, unscreened Training leads | **Unresolved** (needs manual review in production) | — |
| F-H1 (code part): logging, heartbeat, last tick, version | **Fixed**. Checked in a local browser; **unverified on the deployed site**. | `test_worker_logs_traceback_and_records_heartbeat`, `test_failed_job_is_logged_with_context`, `test_version_endpoint_and_worker_status_in_snapshot` |
| F-H1 (ops part): always-on plan, uptime check, alerting | **Unresolved** (operations) | — |
| F-M4: status semantics | **Fixed** | `test_missing_input_is_needs_input_not_needs_you`, `test_provider_failure_in_social_is_still_needs_you`, `test_reused_draft_is_not_reported_as_drafted` |
| R1: duplicate daily summary after a Sales Goal save (regression from F-M4) | **Fixed** | `test_goal_save_does_not_rerun_jobs_that_already_saved_outputs` |
| R2: a shared domain prefix was treated as proof of affiliation (reproduced: `acme.com` contact at `acmesteelworks.com` was named in drafts) | **Fixed** | `test_shared_domain_prefix_does_not_imply_affiliation`, `test_browser_domain_check_mirrors_server` |
| R3: a generic search keyword could satisfy the service focus (reproduced: keywords "Scan-to-BIM, BIM coordination" let a "BIM coordination" draft pass a Scan-to-BIM campaign) | **Fixed** | `test_generic_search_keyword_cannot_satisfy_required_focus` |
| F-M6: login limiter keyed on the proxy address | **Fixed in code; unverified on Render** | `test_login_limiter_uses_trusted_forwarded_hop`, `test_one_users_failures_do_not_lock_out_another` |
| F-L5: API accepted `complete` on briefs | **Fixed** | `test_briefs_cannot_be_completed` |
| Section 12.3: PostgreSQL behaviour untested | **Verified on disposable PostgreSQL 17.11**; not yet on the production database | Full suite via `tests/postgres_runner.py`, plus `tests/test_postgres_concurrency.py` (5 tests) |
| F-L9: no version endpoint | **Fixed** (part of F-H1) | `test_version_endpoint_and_worker_status_in_snapshot` |
| F-C1, F-C2: rhythm not enabled; caps too low | **Unresolved** (configuration; out of scope by instruction) | — |
| F-M5: multi-instance recovery | **Unresolved** | — |
| F-L1–F-L4, F-L6–F-L8 | **Unresolved** (not in this pass) | — |

## What changed

### F-H3
- **Screening note removed from outbound facts.** `ai_draft.lead_facts` no longer sends `ai_reason` to outbound drafts. The internal room draft still sees it, labelled `unverified_screening_assessment`.
- **Required service focus.** A new Sales Goal field, "Required service focus" (`service_focus`, up to 200 characters), is separate from the optional search keywords. `ai_draft.campaign_focus` reads only this field; search keywords never become a drafting requirement. Saving without the field keeps the earlier value, and saving it blank removes the requirement. Existing campaigns have no value until someone sets it. The focus is passed as `campaign_service_focus` to:
  - scheduled and manual email drafts (`server.ai_draft_lead`)
  - rhythm messages (`rhythm_engine.message`)
  - the proposal draft
- **Prompt rules.** The prompts forbid "we noticed / researched" claims and require the service focus in those exact words.
- **Output check.** `ai_draft.focus_missing` requires **every** comma-separated focus phrase to appear in the generated subject and body. It compares letters and digits only, so "Scan to BIM" satisfies "Scan-to-BIM", but generic "BIM" or "BIM coordination" does not.
  - It covers outbound email (`ai_draft.write_draft`) and outbound rhythm messages (LinkedIn, WhatsApp, partner, academic, follow-up, customer) in `draft_outputs.generate`.
  - A draft with no keyword is discarded and nothing is saved. The attempt still counts against the Gemini cap and isn't retried automatically.
  - Internal call preparation, rooms and public posts are exempt.

### F-M1
- **Fingerprint.** `draft_outputs.room_context` fingerprints only:
  - lead facts
  - the stage
  - the latest team-update event

  It no longer includes the day's search hits.
- **Event record.** Each room-draft event records `fingerprint: 2`, the signal URLs it saw, and the rhythm `day`.
- **When a room is redrafted:**
  - A changed fingerprint (stage, team update, lead facts) triggers a redraft straight away.
  - Unverified search URLs that no earlier draft saw trigger at most one redraft per lead every 7 days (`SIGNAL_REDRAFT_DAYS`).
  - Repeating or vanishing search results never trigger one.
- **Deployment safety.** Rooms drafted under the old fingerprint are redrafted only after a new team update. Deploying this doesn't set off a wave of redrafts.

### F-M2
- `graphic_svg` wraps text by estimated pixel width. The estimate is deliberately conservative for uppercase, wide and full-width characters.
- Over-long words are broken.
- Text ends with "…" whenever the title or paragraph is cut.

### F-M3
- `growth.save_item` rejects any action or edit on outreach in state `done`.
- The UI shows "Recorded as sent; locked" instead of Reopen.

### F-H2
- **Domain comparison.** `ai_draft.contact_domain_mismatch` compares the email domain with the website's registrable domain (`www.`, subdomains and `com.sa`/`co.uk`-style suffixes).
- **Only an exact registrable-domain match counts.** Affiliation is never inferred from similar names: `acme.com` vs `acmesteelworks.com` and `khansaheb.com` vs `khansahebcivilengineering.com` are both flagged for a person to confirm. An earlier draft of this fix accepted name prefixes; that was removed (R2).
- **Webmail is always a mismatch:** gmail, yahoo, outlook, hotmail and similar.
- **JavaScript copy.** `web/app.js` mirrors the check. A Node test runs the browser function on the same cases and compares the results with Python.
- **UI and drafts:**
  - The lead room shows a warning on a mismatch.
  - The label reads "Apollo email status: verified".
  - A mismatched contact's name and title are left out of draft facts.
  - The decision-maker map flags the mismatch.

### F-H1
- `server.worker_tick` runs each step (rhythms, automation, Outlook) separately, logging failures with `logging.exception`. One failing step no longer skips the others.
- `automation.finish` logs the traceback with the service, day and job name when a job fails.
- A heartbeat is saved in the new `worker_heartbeat` table and returned as `worker` in `/api/growth`.
- The UI shows "Last worker tick". It warns when the tick is more than 5 minutes old or the last tick had errors.
- `GET /api/version` returns `{"commit": …}` without login, using `RENDER_GIT_COMMIT` or else `git rev-parse HEAD`.

### F-M4
- Missing consented proof (16:00) and research blocked by input or plan rights (18:00) now end in `needs_input`. `needs_you` stays reserved for provider and storage failures.
- Reused pending drafts are reported as "Existing draft still awaiting review; no new draft was prepared."

### R1 (regression from F-M4)
- **Cause:** a Sales Goal save released every `needs_input` job for the day, including the social and summary activities that had already saved drafts. Re-running them created a second daily summary, and with Brave rights enabled it could have repeated the paid evening research.
- **Fix:** `automation.save` now skips jobs whose result lists saved outputs (`item_ids`). Blocked jobs with no output are still released.
- **Trade-off:** if research input is fixed later the same day, that day's evening research and summary don't re-run. They run normally the next day.

### F-M6
- **Client address.** The login limiter uses `Handler.client_ip()`. Behind Render (the `RENDER` env var, which Render sets itself), it takes the rightmost `X-Forwarded-For` entry, the one the trusted proxy appends.
- **Locally,** the header is ignored.
- **Optional override.** `VOXEL1_TRUSTED_PROXY_HOPS` overrides the hop count. It isn't required, and no production setting was changed.

### F-L5
- `complete` on a brief is rejected server-side.

## Data safety and compatibility

- The only schema change is additive: `CREATE TABLE IF NOT EXISTS worker_heartbeat`.
- No existing rows are rewritten or migrated. Older room-draft events are read as they are.
- New fields (`fingerprint`, `signal_urls`, `day`) are added only to new events.
- The new SQL (`INSERT … ON CONFLICT(name) DO UPDATE … excluded.*`, with `?` placeholders converted by `server.run`) has now been run on both SQLite and PostgreSQL 17.11, including concurrent writes.
- Upgrading a `b8f5e93`-built PostgreSQL database preserved all rows (see "PostgreSQL verification").
- Existing `done` outreach rows stay as they are; they just can't be reopened anymore.

## Verification performed (all local; nothing on the deployed site)

Checks were run by the session that started the fix work. They used mocked providers, scratch databases, and a local server started without provider keys, so it couldn't make paid calls.

- **Full suite and JavaScript syntax:** both rerun independently; results above.
- **Graphics, measured in a local browser** with `getBBox` (rendered output, not the module's width estimate):
  - Every line ends at or before x=914 on the 1080 card (the right margin is at 992).
  - This held for all-caps, `W`/`M`, long-word and CJK titles.
  - Truncated text ends with "…".
- **UI in a local browser (before the group-domain change):**
  - the lead-room domain-mismatch warning
  - "Recorded as sent; locked", with no Reopen button
  - "Last worker tick"
  - `/api/version`

  The later domain-rule changes affect only the browser function's result, which `test_browser_domain_check_mirrors_server` now compares with the server's for the same cases. The warning markup is unchanged.
- **Sales Goal field in a local browser:** the "Required service focus" and "Optional search keywords" fields display separately. A saved value of `Scan-to-BIM`, with keywords `BIM coordination, Revit modelling`, persisted and pre-filled after a reload.
- **Simulations:**
  - The duplicate-summary reproduction now leaves one summary after an evening save.
  - Repeating search results no longer redraft rooms.

## Remaining limitations

- **PostgreSQL verified only on a disposable copy.**
  - The suite and concurrency tests pass on PostgreSQL 17.11, but not on the production database itself.
  - Production specifics are untested: network latency, connection limits, and the plan's storage and backup settings.
  - The upgrade test used a small synthetic dataset shaped like production, not a copy of production data.
  - The concurrency tests use threads in one process, not two separate server processes.
  - Startup `recover()` still marks another live instance's running jobs as interrupted (F-M5). It doesn't cause duplicates, but it can mislabel them.
- **Render proxy handling unverified.** F-M6 assumes Render's proxy appends the real client IP as the last `X-Forwarded-For` entry. If another proxy (such as a CDN) sits in front, set `VOXEL1_TRUSTED_PROXY_HOPS` accordingly.
- **Real Gemini wording unverified.** All tests mock Gemini, so whether real drafts mention the service focus naturally, and how often the new focus check discards drafts, is unknown.
  - Each discard costs one Gemini request against the cap and is not retried.
  - The check matches whole phrases, and every listed phrase is required. A draft that paraphrases (for example "laser-scan to model" for "Scan-to-BIM") is discarded.
  - The phrase test is containment, not meaning. A draft that names Scan-to-BIM only in passing satisfies it.
- **Rooms can still update on news, at most weekly.** A company with steady new search coverage still gets one search-triggered room redraft per 7 days. Team updates and stage changes are unaffected by this limit.
- **Domain matching is strict.**
  - Genuine group-company contacts (such as Khansaheb's `khansaheb.com` contact for `khansahebcivilengineering.com`) are flagged, and drafts leave out their name and title until the team confirms them. There is no per-lead "confirmed domain" override yet.
  - Without a public-suffix list, unusual country suffixes may be misjudged.

  The warning is advisory.
- **Service focus not set on existing campaigns.** The live BIM campaign has no "Required service focus" yet, so no focus check applies until someone sets it in Sales Goal. Search keywords alone don't enable the check.
- **Deployed UI unverified.** The UI was checked only in a local browser, not on the deployed site.
- **Graphic width estimate.** The width comes from a character-class table, not font metrics. Browser measurements showed a safe margin, but a different rendering font could differ.
- **No corrections for sent records.** A sent record with a mistake can't be corrected yet; that needs a "correct record" action with an audit event.
- **Old error text in the heartbeat.** `last_error` keeps the most recent error text after later successful ticks. The UI compares timestamps to decide whether it's current.
- **Operational items still open.** Whether the worker stays up on Render (F-H1 operations), and the budget and configuration items (F-C1, F-C2).
