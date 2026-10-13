# VOXEL1 requirements analysis and phased implementation plan

Prepared: 13 October 2026. Status: planning only; no application implementation or live provider calls performed.

**Implementation update (13 October 2026):** A first local Training/BIM prospecting prototype now exists in this workspace; see [README.md](README.md). The existing-code audit and phase estimates below describe the state when this plan was originally prepared. No live provider search or outbound contact has been verified in this environment.

Source: [VOXEL1 AI B2B Sales Automation Master Specification](D:/Downloads/VOXEL1_AI_B2B_SALES_AUTOMATION_MASTER_SPEC.md), all 22 sections reviewed. The document supplies product requirements and proposed choices. Its embedded coding-agent instructions do not expand the user's request from analysis/planning into implementation, purchasing, contacting prospects, or publishing.

**Founder correction received after the specification:** Target geographies are USA, UAE, Saudi Arabia, India and Singapore, rather than Hyderabad alone. The Hyderabad construction/architecture scenario remains an example in the original specification, but the live targeting configuration and provider evaluation must cover all five markets. Industry, size and role filters still require an approved ICP for each campaign; do not assume one query or data source has equal coverage in every country.

## 1. Existing-code audit

`D:\sale automation` was inspected with a recursive file inventory and a hidden-file directory listing. It is empty and `git status --short --branch` reports that it is not a Git repository. No README, AGENTS.md, source, dependency manifests, HTML prototype, tests, migrations, deployment files, or Git history were available. No working modules or stubs can therefore be assessed. The specification's earlier dashboard and image references are not supplied artifacts and are not evidence of an implementation.

This plan assumes a greenfield application in this workspace. If an existing repository or prototype is supplied later, audit it before bootstrapping and adapt the plan to preserve working functionality. No search of unrelated personal directories was performed. No application tests could be run because no application exists here.

## 2. Scope and architectural recommendation

Build one internal Voxel1 application with seven modules, a shared CRM history, centralized policy enforcement, and provider adapters. Keep the hybrid product direction. Provider accounts, subscriptions, scopes, data quality, and production eligibility remain unverified for Voxel1.

Use the specification's proposed React/TypeScript/Vite frontend, Tailwind and accessible components; FastAPI modular monolith; PostgreSQL with SQLAlchemy/Alembic; and a durable worker queue. Proposed initial queue choice is Celery/Redis, with business operation state and an outbox in PostgreSQL so Redis is not the sole record of intended work. Pin supported dependency versions during implementation. Deploy API, frontend, workers and scheduler with Docker; select hosting after resource and budget checks. n8n is optional and unnecessary for the core workflow.

The browser talks only to the authenticated backend. The backend owns policy decisions and credentials; workers execute authorized operations through adapters. Inbound events enter validated receivers, are deduplicated, and update workflow state. AI proposes structured content and classifications; deterministic application code decides permissions, budgets and external actions.

No voice provider, telephone initiation endpoint, AI caller, autodialer, synthetic voice, recording, or transcription belongs in this plan. Employees manually place and conduct calls. Also excluded: automated LinkedIn DMs/connections/scraping, unconsented WhatsApp campaigns, engagement manipulation, unreviewed publication, multi-tenant SaaS, payments, ads management, and rebuilding vendor databases. Optional media generation and external CRM sync require separate need and budget decisions.

## 3. Requirements coverage and dependencies

Every requirement group below includes persistence, protected API behavior, corresponding UI, audit events, and automated acceptance tests. Proposed internal APIs from specification section 8 are application contracts, not claims about vendor APIs.

| Requirement group | Required behavior | Delivery / proof |
|---|---|---|
| ICP Manager | Name, service, industries, geography, employee range, technologies, titles/seniority, exclusions, positive/negative keywords, priority, goal, owner and approval status. Immutable approved versions; changes create reviewable versions. | P1: jobs reference the selected approved version; unauthorized or unapproved jobs fail. |
| Discovery | Generate a configurable 5–15 queries under daily/weekly ICP and provider limits; normalize names/domains; remove duplicates, directories, irrelevant sites, existing customers and exclusions; retain permitted evidence, reason codes, confidence and score; approve/reject companies. | P1: raw hits and verified companies counted separately; unknown firm size or buying need never becomes an invented fact. Manual URL/CSV fallback. |
| Apollo Contacts | Search selected company domains and roles, shortlist limited people, selectively enrich with budget confirmation; record professional email/phone availability, provider status, confidence, source and channel eligibility; dedupe by provider ID/email and review uncertain identity matches. | P1: search/enrichment separate; asynchronous phone pending/succeeded/failed/timeout states; missing details remain unknown. |
| Email Campaigns | Authorized mailbox OAuth; approved Voxel1 facts and company evidence; subject/body preview, edit, rejection, specific-message or bounded batch approvals; campaign authorization; send states/provider IDs; reply threads, failures/bounces/opt-outs; follow-up suggestions. | P2: eligibility rechecked at dispatch, no duplicate send on retries, edits invalidate approval, replies stop pending campaign steps. |
| Reply handling | Interested, information request, meeting request, no interest, out-of-office, unsubscribe and unknown; preserve original evidence and permit human correction. | P2: unsubscribe suppression does not depend solely on model confidence; uncertain replies pause automation and enter review. |
| Human Calling | Available authorized phone and contact details; queue by priority, owner and due date; scripts, service talking points, reminders/history; employee-entered outcomes: not reached, spoke, interested, not interested, call back, meeting requested, do not call. | P2: every call record has a human owner; do-not-call cancels applicable tasks; no code path starts calls. |
| WhatsApp | Timestamped/source/purpose-specific opt-in and revocation; template and reply-window checks; explicit ineligibility label; approved business-initiated messages; validated incoming/delivery events; conversation UI, AI suggestions and human takeover. | P3: no permission means dispatch blocked; Apollo phone presence never creates consent. |
| Appointments | Selected corporate calendar; genuine availability, prospect acceptance, owner, attendees, event ID, link and state; reschedule/cancel/reminder/CRM updates. UTC storage and Asia/Kolkata default display. | P2: serialize app bookings, recheck availability, reconcile provider results; conflict or ambiguous result remains visible for resolution. |
| Social Publishing | BIM services, BIM training, software and construction-tech calendar; platform-specific captions/hashtags/CTA; approved uploaded images/video; draft/review/approval/scheduling/publication; provider ID/link/time/error/retry/approver history. | P2 draft preview; P3 live publishing only with rights. Manual publish fallback explicitly marked; no duplicate automatic retries. |
| Overview / Analytics | Verified companies, usable contacts, funnel, send/reply results, completed human calls, meetings, publishing/engagement, spend and failure rate; ROI only where measurable. | P1 research/usage; P2 sales funnel; P3 supported channel analytics. Separate live/demo, unknown/zero and sent/delivered. |
| Admin / RBAC | Admin, sales_manager, sales_rep, marketing_manager and viewer permissions from section 10; assigned-lead boundaries, connection health, scopes, budgets, audit and policy settings. | Basic backend enforcement in P0/P1; every later slice extends its permission tests. Viewer cannot mutate; frontend hiding is not authorization. |
| Cross-cutting UX | All ten navigation areas, global company/contact/task search, blue/neutral accessible desktop-first interface readable on tablet/mobile, truthful empty/disconnected states, provenance, credit confirmation, permission badges, human-only badge, real provider acknowledgments. | Shell P0; features added in owning phase. Keyboard/focus/contrast and responsive checks. Demo uses fictional .example domains and masked numbers. |
| Reliability / Security | OAuth, encrypted tokens, HTTP-only sessions, TLS/CORS, write protection, rate limits, event verification/deduplication, bounded retries, trace IDs, privacy-safe logs, audited exports, retention and separate encrypted backups. | Foundations P0; minimum production controls before P2 live pilot; deeper drills P4. |
| AI safeguards | Validated structured responses, source-grounded claims, prompt/model version/cost records, low-confidence review, strict separation of untrusted websites/emails from instructions. | P1 onward: no AI permission to send, change budgets, buy credits, enable connections or bypass suppression. |
| Operations / Cost | Provider caps, reservations for concurrent paid work, alerts at 50/80/100%, enrichment/message/query limits, usage reconciliation and monthly CSV of requests, credits, messages, model invocations and costs. | Budget foundation P0; enforced before first paid P1 operation; operational reports expand P2/P3. “AI calls” means model requests, never telephone calls. |

Section traceability: §§1–2 define scope, outcomes and decisions; §§3–4 map to the seven workflow rows; §§5–8 map to architecture, provider contracts, schema and API backlog; §§9–12 map to UX, roles, AI and security; §13 maps to risk gates below; §14 maps to the budget register; §15 maps to the phases; §16 maps to the pilot and QA; §§17–18 map to repository layout and slice delivery; §19 maps to the input checklist; §20 maps to exclusions; §21 maps to API verification; §22 maps to release acceptance. No entire module is silently deferred beyond the plan.

## 4. API evidence and unresolved capability checks

Public documentation was checked during this analysis. Documentation availability does not establish Voxel1 account entitlement. No paid requests or account probes were made.

| Provider | Evidence / constraint | Implementation gate and fallback |
|---|---|---|
| Apollo search | Official docs distinguish search from contact data: `POST /api/v1/mixed_people/api_search` does not return emails or phones. | Verify account/key access, relevant filters, rate limits and bounded samples across USA, UAE, Saudi Arabia, India and Singapore. Do not enrich all results automatically. [People API Search](https://docs.apollo.io/reference/people-api-search). |
| Apollo enrichment | `POST /api/v1/people/match` is separately metered. Current phone reveal documentation requires `webhook_url`; polling support was not established. HTTP success can still mean no match. | Implement correlated callback processing; verify callback authenticity mechanism rather than inventing a signature header. No guessed polling endpoint. If secure callback support is unresolved, disable phone reveal. [People Enrichment](https://docs.apollo.io/reference/people-enrichment). |
| Brave | Specification proposes search and notes storage licensing. Pricing page retrieval did not establish a usable current quotation. | Confirm search contract, plan, permitted storage/cache and actual pricing before paid use. Keep original allowance as historical planning input. Use manual domain/CSV entry if unavailable. [Brave pricing documentation](https://api-dashboard.search.brave.com/documentation/pricing). |
| Gmail | Gmail push uses Pub/Sub and mailbox history; watches expire and must be renewed. It is not a complete reply payload sent to a generic webhook. | If selected, implement watch renewal, durable history cursor and recovery sync; verify scopes and OAuth approval requirements. [Gmail push guide](https://developers.google.com/workspace/gmail/api/guides/push). |
| Microsoft email/calendar | Official Graph mail and calendar resources exist; the company provider is undecided. | Implement only the chosen live provider first. Verify exact send, change-notification, availability and event contracts and tenant permissions in P0/P2. [Mail](https://learn.microsoft.com/en-us/graph/api/resources/mail-api-overview), [Calendar](https://learn.microsoft.com/en-us/graph/api/resources/calendar). |
| Google Calendar | Free/busy lookup is documented. It should not be treated as an atomic reservation of a time slot. | Verify creation/update/cancellation and meeting-link support for the actual account. Use local booking locks plus provider reconciliation. [Free/busy reference](https://developers.google.com/workspace/calendar/api/v3/reference/freebusy/query). |
| WhatsApp | Official business policy requires recipient permission and honoring opt-outs. | Verify Cloud API version, business setup, templates, service window, webhook validation and current India rates before implementation of live dispatch. Draft-only/manual takeover while blocked. [Business policy](https://business.whatsapp.com/policy). |
| LinkedIn | Organization publishing is documented with `w_organization_social`, applicable company-page role and versioned headers. | Validate app product access, media upload/read scopes and analytics separately. Publishing access does not imply DM or all analytics access. [Posts API](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api). |
| Instagram | Direct official documentation retrieval failed in this audit; precise current contract is not verified. | P3 gate: verify chosen login flow, professional-account eligibility, scopes, app review, media formats, processing/publishing and analytics. Do not universally assume a linked Facebook Page across login flows. Manual publishing until verified. [Official platform documentation](https://developers.facebook.com/docs/instagram-platform/). |
| AI | No production provider or model selected. | Evaluate structured outputs, grounding quality, privacy, latency and actual cost on a fixed dataset. Record exact model and prompt versions. No invented native tool capabilities or approved data-processing terms. |

Mail APIs must not be assumed to expose comprehensive delivered/open/complaint events. Record provider submission and observable bounces/replies; show unavailable metrics honestly. Expand delivery/complaint handling only where the chosen provider/account offers documented signals. Pricing, licensing, OAuth scopes and country-specific legal procedures require verification at the relevant release gate.

## 5. Data and workflow design to settle before coding

Retain all 18 proposed entities: users, icps, discovery_jobs, companies, company_evidence, contacts, consents, suppression_list, campaigns, messages, message_events, call_tasks, followup_tasks, appointments, social_posts, integration_connections, usage_events and audit_logs. Use UUIDs, timestamps, foreign keys, migrations and documented state transitions.

Proposed schema refinements, needed to enforce the specification rather than expand product scope:

- Separate immutable `icp_versions` and bind discovery jobs/campaigns to a version. Persist discovery queries and source-level observations. Company existence is global; fit score, reason and qualification belong to a particular ICP/version, since one company can fit one ICP and fail another.
- Add enrichment requests with selected fields, provider person/request IDs, cost reservation and callback correlation. Distinguish requested, pending, succeeded, no data, failed and expired. Preserve field provenance and observation time. Phone availability is separate from accuracy and permission.
- Add approved service facts, AI execution metadata and evidence references so generated claims can be traced. Treat confidence as a model/provider assessment, not a calibrated probability unless evaluated.
- Bind approvals to immutable content revision/hash, recipients, sender/account, channel, media, schedule and batch bounds. Editing approved content or expanding recipients invalidates approval. Campaign authorization alone cannot authorize arbitrary future text.
- Store consent history and channel/global suppressions with explicit scope and reason; use canonical identifiers and keyed hashes where appropriate. Define how deletion and minimal suppression retention interact under the approved policy.
- Add an operation/outbox record, inbound event inbox, attempt log and budget reservations. Use database uniqueness and transactional state transitions. Worker lease/recovery and a dead-letter review queue make failures visible.
- Add conversation/thread mapping and mailbox synchronization cursors, availability/booking attempts, social media asset metadata and user-confirmed manual publish records. Store provider IDs only on confirmed provider results.
- Store measured versus estimated costs with units, currency, pricing version and reconciliation status; do not equate credits with rupees without an account-specific conversion.

All sensitive APIs under `/api/v1` enforce identity, role, record access and input validation. Preserve the specification's ICP, discovery, company, contact, campaign, message, conversation, call-task, appointment, social, analytics, usage and webhook route groups. Extend internal routes as needed for consent/revocation, suppression, approvals, connection setup, imports/exports, task history, event recovery, scheduling changes and audit review. These are proposed internal additions, not third-party endpoint definitions.

Three critical consistency rules:

1. **Dispatch authorization:** check current suppression, consent, approval revision, provider connection, campaign limit and budget immediately before dispatch. Serialize relevant app-side state changes; cancel queued work on replies/opt-outs. An already accepted external message cannot be recalled by changing the database.
2. **Ambiguous external results:** an idempotency key in our database does not create vendor idempotency. A timeout after vendor acceptance enters `unknown/reconciliation_required`; query documented provider state where possible and otherwise require operator resolution. Never blindly retry a send, enrichment charge, event creation or publication with an uncertain outcome.
3. **Calendar conflicts:** app-side locks and final availability checks prevent competing app bookings. They do not provide a distributed transaction against independent calendar edits. Detect/reconcile external conflicts and show pending/conflict states. Define this limitation explicitly in the no-double-booking acceptance test.

Web retrieval also needs bounded size/time, permitted content handling, private-network/metadata-address blocking and redirect checks. Treat fetched pages, emails, attachments and webhook payloads as untrusted data; sanitize UI rendering and keep external text out of trusted instructions.

## 6. Phased implementation backlog

The time windows below retain the specification's one-developer planning baseline. They are working-day estimates from a future start, not delivery commitments. P1's source wording mixes phase and cumulative duration; use approximately 15 days after P0 and re-estimate after access tests. External approvals can extend elapsed time. Each numbered slice should produce API + UI + tests and a reviewable demo, using fixtures where account access is unavailable.

### Phase 0 — Readiness and foundation (indicative days 1–5)

0.1 Record provider/account decisions, first ICP, approved service claims, budget/volume, roles, operating owner and build-versus-buy rationale. Acknowledge the CEO's vendor assessment as opinion; compare actual fit/access/cost if revisiting alternatives. Start social/account permission discovery early without building those modules first.

0.2 Write architecture, schema/state diagrams, provider capability matrix, threat model and acceptance contracts. Define what “verified company,” “usable contact,” “positive response” and “booked meeting” mean. Set data retention, pilot thresholds and recovery objectives with the owner.

0.3 Bootstrap the recommended frontend/backend/docs/infra layout, migrations, local PostgreSQL/queue, health/readiness endpoints, typed API client, authentication and role enforcement. Add example configuration, secret exclusions, CI, fixture adapters and an unmistakable demo shell. Outbound actions are disabled by default.

0.4 Implement shared audit, provider timeout/error contracts, usage reservations, idempotent operations, outbox/event inbox and a provider kill switch. Establish backup/export policy and encrypted token handling before real data.

**Exit:** local skeleton and negative authorization tests pass; owner approves initial ICP, access plan and capped pilot. Missing accounts do not prevent mock-mode development. Deliver ARCHITECTURE, API_INTEGRATIONS, COMPLIANCE_AND_CONSENT and OPERATIONS notes as living documents. This analysis has not yet delivered that running skeleton.

### Phase 1 — ICP → verified companies → selected contacts (indicative days 6–20)

1.1 Complete versioned ICP fields/editor/approval/history; test unauthorized edits, approved-version pinning and invalid filters.

1.2 Build bounded query generation, Brave adapter/fixture, jobs UI, permitted evidence fetch/storage, normalization and exclusions. Test repeated URLs/subdomains, directories, missing evidence, irrelevant results, provider outages and query caps.

1.3 Build evidence-based scoring/review with accepted/rejected reasons; distinguish rule failures, uncertainty and AI suggestions. Test unsupported buying claims and prompt injection. Add manual company URL/CSV intake with validation and dedupe.

1.4 Add Apollo people search shortlist, selective paid enrichment confirmation, asynchronous phone callback state, credit accounting and field provenance. Test no-match 200 responses, partial enrichment, duplicate/late callback, timeout, identity mismatch and concurrent budget reservation.

1.5 Deliver lead/contact views, basic search, research KPIs, integration status and usage CSV. Run a bounded live research sample only with approved accounts/budget.

**Dependencies:** approved ICP and claims, search licensing, Apollo access and pricing, selected AI data policy. **Exit:** target up to 50 relevant companies, each counted as verified only with suitable evidence; report actual yield, missing fields and cost per usable contact. Finish this chain before WhatsApp or live social work.

### Phase 2 — Core sales MVP (indicative days 21–60)

2.1 Implement consent/suppression administration, campaigns, immutable message approvals and bounded batch manifests before outbound email. Test stale approvals, contact reassignment, unauthorized batch expansion and demo-mode sends.

2.2 Connect the chosen mailbox through OAuth; draft grounded subject/body with evidence preview; send approved eligible messages through guarded workers. Verify SPF/DKIM/DMARC and approved outbound procedures before live tests. Exercise token expiry, quota errors and timeout-after-acceptance reconciliation.

2.3 Add inbox history/webhook intake, thread mapping, reply categories, bounce/rejection handling where observable, human review and stop/cancel follow-up logic. Test duplicate/out-of-order notifications, unsubscribe versus queued sends, unknown replies, history gaps and provider downtime.

2.4 Implement assignment, follow-up reminders and human call history/outcomes with visible human-only badge; DNC integration and scripts grounded in approved services. No telephony connector is needed.

2.5 Add slot proposals, acceptance capture, booking, meeting-link status, rescheduling/cancellation/reminders and synchronization. Test UTC/timezones, parallel bookings, external conflicts, token expiry and unknown create outcomes.

2.6 Add sales funnel/usage/failure dashboards and social draft/review previews for the pilot. Establish staging, production secret management, structured redacted logs, alerting, TLS, daily separate encrypted backups and a successful restore exercise before any production pilot.

**Dependencies:** mailbox/calendar ownership and consent, outbound policies, sender authentication, approvers and authorized test recipients. **Exit:** real permitted company → selected contact → reviewed email → reply → human follow-up/meeting demonstrated, plus 20 grounded drafts and recovery evidence. No uncontrolled follow-up sequences.

### Phase 3 — Controlled multichannel rollout (indicative days 61–100)

3.1 Add WhatsApp opt-in capture, eligibility explanation, supported templates/window rules, approved sending, event ingestion, opt-out and human takeover. Test absent/revoked permission, expired window, rejected template, duplicate events and takeover pausing suggestions/actions.

3.2 Add media upload validation/storage and platform-specific social drafts, review, scheduling, guarded publication and reconciliation for LinkedIn and Instagram. Test account role loss, edited media after approval, processing failures, late workers and ambiguous publish results. Recheck permission at dispatch. Manual publishing has a separate recorded actor/result.

3.3 Expand reporting with only permission-supported engagement metrics, bounded bulk approvals, operating dashboards and sales-team UAT. Include one LinkedIn and one Instagram draft/review artifact; publish only if authorized access is ready.

**Dependencies:** account/API permission checks from section 4, opt-in method/templates, approved media rights and actual rate cards. **Exit:** eligible messaging and company publishing work end-to-end where access exists. Blocked connectors remain visibly blocked; manual completion is not reported as an automated integration pass.

### Phase 4 — Production hardening and measured expansion (indicative days 101–160 if needed)

4.1 Load-test expected volume; tune queues, provider quotas, backoff/circuit breakers and database indexes using measured workloads. Test worker loss and recovery, not just successful responses.

4.2 Perform security/privacy review, retention/deletion/export drills, token rotation, backup restore and incident exercises. Document deployment rollback, failed migration recovery, provider outage, compromised credentials, accidental duplicate action and budget overrun procedures.

4.3 Evaluate scoring and contact quality against human-labeled data, improve only against measured errors; add external CRM sync only if needed and define conflict ownership. Expand employees/markets after unit economics and policy readiness are demonstrated.

**Exit:** recovery objectives, capacity and privacy controls pass agreed acceptance; operating owner accepts runbooks; no unresolved critical authorization, suppression, duplication or secret-handling defects. Basic security/backups are prerequisites from earlier phases, not postponed until P4.

## 7. QA and release gates

Test layers: deterministic policy/state tests; PostgreSQL/queue integration tests; provider contract fixtures including malformed/partial responses; browser end-to-end tests; explicitly authorized live account smoke tests; and sales-team UAT. Each provider contract records doc/version date and sanitized fixtures. Mocks prove application logic, not account access.

| Acceptance gate from specification §16 | Required proof |
|---|---|
| Approved ICP; normalized domain dedupe; evidence/score | Unapproved job denied; duplicate candidates collapse; selected version remains fixed; unsupported facts flagged. |
| Separate Apollo search/enrichment; asynchronous phone; missing data | Search yields no invented contacts; callback states and unavailability are honest; no guessed fallback endpoint. |
| Budget blocks | Parallel requests reserve worst-case approved spend; unknown prices block paid execution; usage lag reconciles without releasing pending reservations prematurely. |
| Grounded drafts | Review all 20 pilot drafts against evidence and approved services; any unsupported claim blocks that draft. Include adversarial website/email fixtures. |
| Authorized email and no retry duplicates | Campaign, content and recipient bounds enforced; concurrent workers/crash/timeout tests; ambiguous outcomes pause. |
| Unsubscribe / DNC | Channel/global scope tested; event arrival cancels queued work; suppression is reevaluated immediately before action. |
| No AI calling; manually recorded outcomes | Route/worker/dependency review plus architecture test finds no telephony dispatch; call tasks require human ownership. |
| WhatsApp permission; no LinkedIn DM/scraping | No-consent send denied; missing template/access denied; no prohibited connector/routes/jobs. |
| Approved social publishing | Content/media/account revision locked to approval; scheduler respects time; permission loss and unknown result do not cause duplicates. |
| Calendar availability | Competing app requests serialize; prospect acceptance required; external conflict and provider failures remain pending/conflicted. |
| Secrets, auth and resilience | Role/assignment tests, secret scanning, redaction, expired-token recovery, forged webhook/replay checks, provider outage and unknown response tests. |
| Truthful results | Fixture/live separation; no false sent/booked/published markers; unsupported delivery/engagement metrics show unavailable. |
| Backup restore | Restore encrypted separate backup into an isolated database and validate key relationships/audit records; record measured recovery time. |

Pilot sequence: approved construction/architecture ICP, approximately 20–500 employees and BIM Manager/Project Manager/Director roles as the initial specification example, with geography expanded to USA, UAE, Saudi Arabia, India and Singapore → up to 50 evidence-backed companies total, sampled across the target countries where data permits → selective contacts within cap → 20 reviewed email drafts → small authorized outbound sample → replies/human calls/meeting capture → one draft per social platform, permission-gated publication → usage/failure report. Report yield and cost by country; do not represent a good result in one market as proof of coverage in the other four.

Report researched domains, verified matches, Apollo match rate, valid email yield, available phone yield, usable-contact cost, approved sends, positive replies, human calls, confirmed meetings, publication success and incidents. Define denominators/time windows and exclude demo data. Divide-by-zero yields unavailable, not a fabricated zero cost. Distinguish contact availability from verified accuracy and consent. Delivery rate is unavailable unless supported delivery signals exist. Set quality and unit-economic thresholds before the live pilot; the source specifies targets but no numeric go/no-go thresholds. Data scarcity is reported, never filled with invented companies or contacts.

## 8. Budget, decisions and inputs

Preserve the specification's original indicative MVP allowance of ₹8,000–₹18,000/month and broader rollout allowance of ₹20,000–₹60,000+/month. These are not current quotes or spending authorization. Preserve its vendor baseline: Apollo Basic $49/user/month on annual billing (₹4,685); Brave $5 monthly credits then $5/1,000 requests (₹0–1,000); AI $5–$30 (₹480–2,870); hosting $12–$24 (₹1,150–2,295); self-hosted PostgreSQL/n8n license allowance ₹0 subject to terms; mailbox ₹0–2,000; monitoring/backups ₹500–2,000. Historical conversion was approximately ₹95.60/USD, not a current exchange-rate claim.

The source ranges are rounded allowances and do not establish a complete live bill. Reprice with account entitlements, actual usage, storage/egress, backups and approval lead times. Exclusions remain labor, coding subscription, annual prepayment implications, extra Apollo/phone credits, WhatsApp usage, extra storage, tax, domain setup, design/media subscriptions, premium API plans and onboarding. Voice calling expenditure is excluded. No purchases are required for mock development.

| When needed | Inputs / decision owner |
|---|---|
| Before first meaningful research pilot | Voxel1 product/sales owner: approved service descriptions and claims, first ICP and exclusions, monthly researched-contact/send target, existing CRM/prototype location if any, success thresholds, approvers and pilot budget. |
| Before live P1 adapters | Account/admin owner: Apollo entitlement and tested phone/email coverage; Brave account and storage rights; production AI choice and processing terms; explicit paid enrichment cap. |
| Before live P2 communications | Company IT/sales owner: mailbox/sender/admin authorization, calendar account, scheduling policy and timezone, sender authentication, campaign/batch approvers, authorized test recipients and outbound guidance. |
| Before live P3 channels | Marketing/business owner: WhatsApp account/number/opt-in collection/templates; LinkedIn organization and Instagram professional-account roles; app/API access and approved media. |
| Before deployment | Operations/management: domain/hosting ceiling, support owner, backup retention and recovery objectives, privacy/DND/outreach procedures approved by the relevant advisor, retention/export/deletion policy. |

These cover all 13 setup inputs in specification §19. Exact provider choice and corporate accounts do not block designing interfaces and mocks; they do block claiming a working live integration. Compliance procedures are release inputs, not a legal conclusion established by this architecture review.

## 9. Main risks and next implementation milestone

The critical path is provider access/data quality, followed by reliable approved outbound workflows. Search relevance and missing Apollo data may make the pilot uneconomic even if the software works. Evidence review and selective enrichment measure this early. AI fabrication is addressed through citations, approved claims and human review; API outages through bounded retries and visible recovery; duplicated effects through guarded state transitions and reconciliation; privacy through minimized data, role checks and audited retention; permission delays through honest manual fallback. Volume, account approvals and the lack of any existing code are the main estimate uncertainties.

The first implementation milestone should be P0 foundations followed by the complete ICP → discovery → selective enrichment vertical slice. Completion of this planning task is not completion of P0 or authorization to purchase APIs or run outreach. No application code, provider connection, customer communication, publication or AI voice functionality has been implemented.
