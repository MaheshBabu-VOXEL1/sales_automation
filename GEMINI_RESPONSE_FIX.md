# Gemini response handling — 16 October 2026

## What the office-computer logs establish

Three attempts failed in today's catch-up run: a room draft, LinkedIn message
for lead 15, and WhatsApp message for lead 19. The common error was
"Gemini's reply was empty or not valid JSON". Other drafts succeeded.

The raw replies were not captured, so these logs do not distinguish malformed
JSON, an empty/blocked response, output truncation, or a field-validation failure.
They do not establish that the API key is invalid, that a quota is exhausted, or
that the shared database is broken. Ordinary HTTP 200/302 lines and favicon 404
are separate from the Gemini drafting failures.

## Local patch prepared

Files: `provider_search.py`, `draft_outputs.py`, `ai_draft.py`, and
`tests/test_gemini_response.py`.

- Shared parser reads non-thought text across response parts rather than assuming
  the first part is the complete answer.
- Accepts a single complete JSON code fence, but never extracts guessed JSON from
  prose or repairs truncated content.
- Rejects blocked, incomplete and malformed responses with specific safe reasons.
- Distinguishes an output-token limit from malformed JSON when provider metadata
  identifies it. Does not change token limits or thinking configuration.
- Rejects non-object JSON and non-string email subject/body values.
- Keeps existing safety checks, approvals, request accounting and no-auto-retry
  behavior. Makes no extra paid request to parse a reply.
- Applies to room/social/message generation, email drafts and buyer screening.

Verification: `python -m unittest discover -s tests -q` with DATABASE_URL unset:
156 tests, OK, 5 PostgreSQL-only skips. The nine new tests cover response-part
handling, complete fences, blocked/partial replies, safe error messages, field
types, integration and absence of automatic request retries. `git diff --check`
passed. No production database access, live provider calls, commit or push.

This is a robustness/diagnostic improvement, not proof of the precise cause of
those three historical failures or proof that Gemini will never fail again.

## Applying on the separate office computer

This workspace is separate from the running office copy under Downloads. Changes
here do not update that copy automatically. Compare versions before transferring
files; preserve any independent office edits. An agent on that computer can review
this patch and apply the matching changes rather than blindly replacing newer code.

1. Keep Render's web service suspended while the local worker owns the database.
2. Let the current batch finish, then stop the local server with Ctrl+C.
3. Apply the reviewed changes to the office copy. Preserve `.env`, budgets,
   knowledge-pack approval state and database records.
4. Run parser tests in isolation with DATABASE_URL unset, never the whole suite
   against the shared production database.
5. Start using the existing environment-loading launcher. Check the heartbeat.
6. Failed saved jobs will not replay automatically. Do not delete jobs, clear
   claims or repeatedly save Sales Goal to force retries. Any intentional live
   regeneration is a separate paid attempt; check remaining budget and existing
   pending drafts before authorizing it.
7. Record new diagnostic messages if a future attempt fails. Never log raw model
   responses, private prompt contents, API keys or database credentials just to
   investigate a parsing issue.

Separate issue: the earlier overnight process stopped; this parser patch does
not add process supervision, explain the shutdown or prove overnight uptime.
