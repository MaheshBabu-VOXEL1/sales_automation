# VOXEL1 sales automation — project handoff for Claude

**Prepared:** 14 October 2026

**Repository:** `D:\sale automation` (`MaheshBabu-VOXEL1/sales_automation`, branch `main`)

**Latest audited commit:** `57c8f7a` — Gemini screening status for company candidates

**Current deployment:** <https://sales-automation-u8lk.onrender.com/>

**Working-tree update, 14 October 2026:** Another developer (Claude) has added a monthly request-budget implementation locally after commit `57c8f7a`. These changes are **uncommitted in this checkout** at the time of this update. The screenshot of Searches 0/5, Apollo 0/60 and Brave 0/8 came from Claude's **local preview using temporary test values**. They are **not Render settings, an approved budget or evidence of live provider usage**. The preview demonstrated that a worst-case 10-request search is blocked by an 8-request test cap. On Render, unset caps default to 0 and block all paid searches until Voxel1 chooses and configures real limits. A fresh local run passed 42 Python tests and JavaScript syntax check. No paid search was run during this review.
**Purpose of this file:** Explain the founder's overall plan, the narrower pilot that exists today, the implementation gaps, and a safe sequence for continuing development. Read the current code before changing it; this is a dated handoff, not a substitute for a fresh audit.

## 1. Sources and certainty

- The primary source for the founder's full plan is the 22-section **VOXEL1 AI B2B Sales Automation Master Specification**, prepared 13 October 2026, at `D:\Downloads\VOXEL1_AI_B2B_SALES_AUTOMATION_MASTER_SPEC.md`. Its status is **proposed specification**, not proof that a feature has been built. The earlier analysis is [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md); its initial “empty repository” audit is historical and no longer describes this repository.
- The user also shared a Claude artifact link: <https://claude.ai/artifact/RYs5R2rDJpSsa9jQFiMEMv#26c7d406-2e2f>. Its content was **not independently retrievable during this handoff**, so do not claim this file is a verbatim account of that artifact. Compare it with the local master specification if it becomes accessible through an authorized route.
- Current behavior below was checked against [`server.py`](server.py), [`provider_search.py`](provider_search.py), [`web/index.html`](web/index.html), [`web/app.js`](web/app.js), tests, and an earlier user screenshot of the screening-status interface and 11 saved India companies. That earlier screenshot did not prove a new Gemini-screened search was run or that every provider integration is available on the hosted account. The separate budget screenshot is Claude's local preview, not evidence of Render configuration.
- Do not place or quote API keys, database URLs, passwords, or contact exports in this file, code, logs, screenshots, or a Claude prompt. Server-side environment variables hold secrets.

## 2. What the founder (“sir”) wants

The founder wants **one Voxel1-owned, AI-assisted B2B sales workspace**, using third-party APIs for specialist data and communication rather than seven disconnected products. The intended end-to-end path is:

`Approved ICP → discover genuine companies → assess fit with evidence → find decision-makers → selectively enrich business contacts → draft and approve outreach → send eligible messages → track replies → human follow-up and meetings → report results and cost.`

A parallel marketing path creates drafts, gets human approval, then publishes to authorized Voxel1 LinkedIn/Instagram accounts when permissions are available. The full master specification groups the product into seven modules:

| Module in the founder's plan | Required end state |
| --- | --- |
| 1. ICP Manager | Approved, versioned targeting by service, geography, sector, size, roles, exclusions, owner and goal. |
| 2. Lead Discovery | Bounded web/company search, domain deduplication, source-backed fit reasons, candidate rejection and review. Raw hits and verified buyers must be counted separately. |
| 3. Apollo Contacts | Role-based person search; optional, budget-controlled business-contact enrichment; source, availability, verification and usage records. |
| 4. AI Email Campaigns | Grounded draft, preview/edit, explicit human approval, eligible sending from Voxel1 mailbox, replies, opt-outs and follow-ups. |
| 5. Human Calling + WhatsApp | Employee-owned call tasks and manually logged outcomes. WhatsApp only with qualifying opt-in, approved templates/rules and official API access. |
| 6. Appointments | Availability, prospect acceptance, confirmed booking, reschedule/cancel and visible failure states. |
| 7. Social Publishing | Voxel1 LinkedIn/Instagram drafts, media review, approval, authorized scheduling/publishing and result tracking. |

**Non-negotiable boundaries:** Employees make and conduct every phone call; there is no AI caller or autodialer. No unattended LinkedIn cold-DM bot or unauthorized scraping. A phone number does not grant WhatsApp consent. Do not send outreach or publish content without the relevant permissions and human approval. AI may suggest, classify and draft, but it must not invent project facts, purchase intent, contact details or provider outcomes.

The source specification's Hyderabad example is just an example. The user later established five target markets: **USA, UAE, Saudi Arabia, India and Singapore**. The user also narrowed the **current implementation focus to two service pipelines: Training and BIM Services**; the broader seven-module vision remains a later roadmap. The user expects **one click on Search companies to automate the remaining research steps**, not a workflow that makes them manually research each company. The stated volume is **below 500 companies per month**, initially using free/low-cost access to test quality. They do **not** want another credit-consuming search now.

## 3. What is implemented today

This is a **working first research slice**, not a complete CRM or the full seven-module product. Avoid a misleading percentage such as “80% done”: the two research-related modules are partial, while the outbound/meeting/social modules are largely absent.

| Area | Current verified implementation | What it does **not** yet establish |
| --- | --- | --- |
| Two services | Separate Training and BIM Services home cards, ICP settings, lead lists and interest statuses. | No additional service pipelines requested for this pilot. |
| ICP form | Saves countries, sectors, employee range, decision-maker titles, positive/exclusion keywords, campaign goal and notes. Saving an ICP is not a paid provider search. | No approval, owner, priority, version history or immutable approved ICP binding. Notes and goal are not search filters. |
| One-click research | With Apollo and Brave keys, `Search companies` requests one bounded Apollo company page (up to 10 candidates), checks a BIM/Revit result on each company's own domain with Brave, optionally asks Gemini whether it is a plausible buyer, then searches Apollo people for relevant roles. | It is not a country-wide exhaustive search. It uses one Apollo page, fixed BIM/Revit terms, no multiple query strategy, no saved per-company evidence trail or verified-buyer decision. |
| AI screening | With `GEMINI_API_KEY`, Gemini reviews candidate company details and transient Brave snippets. Only an explicit `qualified: true` proceeds. Failure or uncertainty skips that new candidate. New approvals are stored as `ai_screened=1`; older leads have no recorded screening history. The UI has a **Gemini-screened** filter. | A plausible buyer is not a guaranteed buyer or proof of a current training/BIM need. The boolean does not store the model's rationale, evidence, timestamp or prompt/model version. Historical leads are not retroactively classified. |
| Basic exclusions | Clear job boards/publications are filtered on new searches before follow-up provider calls. | Existing saved examples such as “Construction Jobs” can still appear in **All**. No complete exclusion taxonomy or approved customer/suppression list. |
| Contacts | Apollo person search can supply a name/title. `APOLLO_ENRICH_DETAILS=1` optionally enriches at most three companies and three people per click; verified work email and company phone may appear if returned. Missing fields stay blank. | Default enrichment is off. Person search alone does not yield email/phone. No phone reveal, asynchronous phone workflow, contact-level records, identity review or complete channel eligibility. |
| Review UI | Lead table, source/website links, country summary, status filter and manually set “Needs review / Interested / Not interested”. | “Interested” is a human-entered status, not AI evidence. There is no separate approve/reject ICP-fit decision, reason codes, scoring, structured research report or outreach queue. |
| Storage/deployment | SQLite locally; PostgreSQL when `DATABASE_URL` is configured. Render web service on `main`. Password-protected `/login` page with a shared account and session cookie. | Render's actual database retention, backups, app uptime and current provider balances have not been verified in this handoff. Shared login is not per-employee role-based access. |
| Tests | The latest local run passed **42 Python tests** after Claude's uncommitted budget changes; JavaScript syntax and diff checks passed. Tests mock provider responses. | Passing mocks do not prove live Apollo/Brave/Gemini quality, entitlements, monthly cost or that every production search works. |

The recent screenshot confirms that the deployed table has the **Gemini-screened** tab and shows 11 existing India companies with “Gemini screening not recorded.” These rows are *legacy saved candidates*, not 11 newly approved buyers. A new paid search has deliberately **not** been triggered to populate the filter. Do not delete or silently relabel these records. If cleanup is needed, provide a reviewable candidate rejection/archive action and preserve history.

## 4. How the current search actually works and where credits can be spent

1. The user chooses Training or BIM Services and saves the service-specific ICP.
2. Clicking **Search companies** starts provider requests. Current code allows at most one running search process at a time and asks Apollo for up to **10 company candidates per click**. That limit is **per click, not a monthly cap**.
3. Obvious job boards/publications and companies without a website are skipped. Each remaining candidate can cause one Brave on-domain search for BIM/Revit evidence.
4. If Gemini is configured, each candidate with a matching page can cause one Gemini classification. Only affirmative results continue. A matching keyword plus affirmative AI result is still a *candidate*, not a guarantee of buyer fit.
5. Each retained candidate can cause an Apollo people-search call. With optional enrichment enabled, up to the first three retained candidates can additionally cause one person match and one organization enrichment each. Missing Apollo values remain missing.
6. Leads are upserted by service and Apollo ID. Existing manually entered interest status and notes are preserved. A previously saved lead becomes marked Gemini-screened only if a later search explicitly approves that same Apollo record.

For a rough volume model, **50 clicks × 10 Apollo candidates = at most 500 candidate slots**, not 500 unique or qualified companies. That pattern can also generate up to roughly 500 Brave requests, 500 Gemini calls and 500 Apollo people searches; actual counts depend on filtering and errors. Optional enrichment could add up to 150 person and 150 organization enrichments across 50 clicks. These are **call-count bounds from code, not a price quote**. Repeated clicks can revisit the same companies and consume provider usage. Claude has now added local monthly **request** caps and a request ledger, but there is still no verified cap on the provider's actual billed credits/money or duplicate-request cache. The user is therefore right to postpone another search.

Current provider mode requires `APOLLO_API_KEY` and `BRAVE_SEARCH_API_KEY`. Gemini is optional and uses `GEMINI_API_KEY`. If both company-search keys are absent, the app uses a limited OpenStreetMap city sample, which does not meet the complete five-country discovery goal. `APOLLO_ENRICH_DETAILS=1` is the optional enrichment switch. Do not expose or change any key while preparing this handoff. Provider pricing and account entitlements must be read from the user's current dashboards/official terms before assigning monetary values; the original specification's October 2026 numbers are planning assumptions, not current charges.

## 5. Gap assessment against the full founder plan

| Requirement | Progress | Main gap / proof needed |
| --- | --- | --- |
| ICP Manager | **Partial** | Add approved versions, owner/roles, priority and search-job binding. Verify the actual Training and BIM buyer definitions with Voxel1. |
| Company Discovery | **Partial** | Build multi-query discovery, normalized domain dedupe, persistent permitted provenance/reason codes, fit review, exclusion/customer list, meaningful country coverage and quality evaluation. Do not retain Brave response text unless the applicable terms permit it. |
| Apollo Contacts | **Partial** | Contact records, selective enrichment approval, usage and field provenance; phone reveal only after account/API capability and budget check. |
| Budget control | **New local implementation; not yet verified live** | Claude added monthly search/provider request caps, worst-case preview/confirmation, server-side reservation, usage ledger and concurrency tests. Review the code and deployment state. These are **request caps, not provider credits or money**; reconcile them with provider dashboards, and add alerts/actual-credit accounting if needed. |
| Mailbox/email campaigns | **Not built** | Provider choice, OAuth, approved Voxel1 facts, grounded drafts, approvals, sender eligibility, deduplicated sending, replies, bounce/opt-out handling. |
| Human call tasks | **Not built** | Assigned queue, scripts, reminders, employee-recorded outcomes and do-not-call handling. No automated calls. |
| WhatsApp | **Not built** | Opt-in evidence, approved templates, official API, webhooks, opt-out and human takeover. Later phase only. |
| Appointments | **Not built** | Calendar authorization, availability, acceptance, booking/reconciliation, reminders and cancellation. |
| Social publishing | **Not built** | Draft/review/schedule and authorized LinkedIn/Instagram company-account publishing. Later phase only. |
| Security/operations | **Partial** | Individual roles, audit, retention/export, backups and restore tests, secret rotation, monitoring, durable jobs and provider-failure recovery. |
| Analytics | **Minimal** | Current counters are saved candidates/contacts/manual interest. Need qualified-company denominator, actual usage and cost, send/reply/human call/meeting metrics when those workflows exist. |

Do not call the project “complete” merely because the Render page is live. The first **research pilot** is partially implemented; the founder's complete end-to-end workflow remains substantially unbuilt.

## 6. Immediate next steps **without spending search credits**

1. **Keep the paid search paused.** Do not click `Search companies`, call Apollo/Brave/Gemini directly, buy plans, enable phone reveal, or run outreach as part of the next review slice. Claude's local 8-request Brave test cap was only a preview value. On Render, unset limits are 0 and the new code will block paid searches until Voxel1 chooses real limits. Existing saved leads remain available for UI testing.
2. **Confirm and save the two ICPs** (Training and BIM Services) with Voxel1-approved target sectors, 1–5 countries, employee range, decision-maker roles, exclusions and service claims. Saving ICP settings alone does not run a provider search. The user's current focus is two services and fewer than 500 companies/month; do not expand scope by default.
3. **Review and finish the new budget protection before the next live search.** Claude's local code adds per-provider request estimates, a visible preview, monthly limits, atomic server-side reservations and a usage ledger. Its tests cover blocked requests making **zero** vendor calls and concurrent reservations. Inspect the final diff, confirm the changes are committed/deployed when intended, test migration against the actual persistent database, and compare estimated requests with provider billing. Keep the distinction between request counts, credits and money visible.
4. **Improve candidate truthfulness from existing data and fixtures.** Add review/archival for legacy false positives; preserve old history. Show whether a lead is AI-screened, when, for which service/ICP version, and what *permitted* evidence/reason supports inclusion. Evaluate false positives using a small team-labeled fixture set; do not claim “guaranteed buyer.” Fix UI readability such as contact labels that currently run together in the narrow table view.
5. **Prepare a bounded live pilot plan, but do not run it yet.** Define success thresholds (relevant companies, actual business contacts, spend per usable contact), sample geography, maximum charged calls, who approves it and how to inspect provider dashboards after each test. A sensible first authorized sample is substantially smaller than the monthly <500 target. Actual pilot execution waits for the user's decision to spend credits.

**Suggested next Claude task:** finish review of the budget slice already added (database migration + server-side guard + UI confirmation + tests + operator documentation). Preserve the current two pipelines, database records and login. Use mocked provider responses for validation. Show the final diff, deployment state and exact remaining gaps before requesting any paid live search. Do not copy the screenshot's temporary test caps to Render; real limits require Voxel1's decision.

## 7. Sequence after the no-credit work

| Order | Build/decision | Exit evidence |
| --- | --- | --- |
| A. Validate search-cost guard | Review/ship Claude's local monthly request caps, per-click preview, usage ledger, retry rules and concurrency tests. Extend later to actual credit/money accounting and alerts. | A capped or unauthorised search is blocked on the server before contacting providers; estimates and actuals are visibly distinct. The 8-versus-10 screenshot demonstrates this only with temporary local test values. |
| B. Research quality | Approved ICP versions; multiple bounded searches; domain dedupe; manual URL intake; fit reasons and review queue; legacy false-positive archival. | A reviewer can inspect *why* each company is included, reject it and see true unique/qualified counts. |
| C. Measured micro-pilot | Only after Voxel1 approves a small credit allowance: run a few searches, check Apollo/Brave/Gemini usage dashboards, label relevance and coverage per country. | Actual company/contact yield and spend are documented; no extrapolated guarantee for all five markets. |
| D. Contact depth | Add person/contact entities and approved selective enrichment, with field provenance and verification states. | Missing email/phone remains blank; measured usable-contact rate and credit cost. |
| E. Sales MVP | Choose corporate mailbox/calendar; build grounded email drafts, human approval, suppression, guarded sends, reply tracking, human call tasks and meetings. | Authorized test workflow from approved lead to reply/human follow-up/meeting, with no unapproved send or auto-call. |
| F. Later channels | Permission-gated WhatsApp and LinkedIn/Instagram company publishing. | Live actions only with confirmed access/consent, approval, audit and duplicate protection. |
| G. Production hardening | Individual roles, backups/restore, monitoring, retention, failure recovery and load/security review. | Operations owner can recover and audit a failed or ambiguous workflow. |

The master specification's indicative phase windows were P0 days 1–5, P1 days 6–20, P2 days 21–60, P3 days 61–100 and P4 days 101–160 for one developer. Those are **old planning estimates**, not elapsed progress or a promise. Re-estimate after agreeing the narrowed two-service pilot, provider entitlements and budget.

## 8. Decisions Voxel1 still needs to make

- Approve exact buyer definitions and exclusion examples for Training versus BIM Services. A BIM service provider can be a competitor for one offer but a potential partner for another; do not use a single unreviewed assumption for both.
- Set the **actual monthly spend cap** in money and/or provider credits, the per-search allowance, and who can change it. “Below 500 companies/month” is a volume target, not a spend limit.
- Confirm the current Apollo account's endpoint access, remaining credits, enrichment terms and permitted contact use; confirm Brave allowance/storage rights and Gemini billing/quota. Do not infer these from a key existing.
- Decide whether the present 11 legacy candidates should remain, be reviewed/archived, or be re-evaluated in a **later explicitly budgeted** run. Do not silently purge or automatically spend to re-screen them.
- Before email: choose Voxel1's corporate mailbox and sender, approved offer/claims, reviewer, test recipients, opt-out policy and acceptable send volume.
- Before WhatsApp/social/calendar: supply account owners, permissions, consent/approval process and provider-specific setup. These decisions are not needed for the next no-credit code slice.

## 9. Handoff rules for the next Claude session

1. Begin with `git status`, latest commit, `README.md`, this handoff, `IMPLEMENTATION_PLAN.md`, and the actual code/tests. Treat this file as project context; the **human user's latest request and current repository state take precedence**.
2. Do not repeat the original `IMPLEMENTATION_PLAN.md` statement that the repository is empty. It is now a deployed Python prototype with tests.
3. Keep the two-service pilot usable while extending it. Add one API + UI + database/test slice at a time. Do not rewrite into React/FastAPI merely because the original specification recommends those technologies; justify a migration only if needed.
4. Make real-provider calls only after the user authorizes a bounded, reviewable test and knows it may consume credits. The next task is safe to complete with mocks and existing saved data.
5. Never represent a candidate as a guaranteed buyer, an obfuscated Apollo name as a complete identity, a company phone as a personal number, or a manually set interest status as an AI finding.
6. Report what was implemented, what tests passed, whether a deployment actually completed, what live behavior was or was not verified, whether credits were used, and the next unresolved decision.
