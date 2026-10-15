# Growth Engine — automated work through draft creation

This release implements the BIM and Training rhythms through saved, reviewable
drafts. It does not publish content, contact leads, send reports to anyone, or
activate Outlook delivery. Platform integration is a separate responsibility.

## Activate once

1. Open a service's **Sales Goal**.
2. Set **Complete draft rhythm → Automate all rhythm activities up to review drafts**.
3. Supply the business objective, targeting, dates and real named accounts.
4. Set desired LinkedIn, Instagram and Facebook posts per day. Zero disables that
   channel's daily posts. Instagram/Facebook outputs include an editable SVG card.
5. Add actual partner/client names matching saved leads, known introduction paths,
   and approved proof/story facts if available. Confirm permission only for facts
   that may be used publicly.
6. Save, and clear applicable global/service pauses.

The worker checks every 30 seconds, every day, while the hosting process runs.
Due activities run once per service/IST day. Restarting does not duplicate saved
claims. Sleeping/free hosting or a stopped server cannot execute work. Past days
are not backfilled.

Existing campaigns are not silently switched to this broader paid workflow.
Saving resolved inputs makes today's input/budget-blocked slots eligible again;
completed work and uncertain provider attempts remain claimed. Room, content and
message attempts all count toward the same Gemini monthly limit.

## BIM outputs

| Time IST | Activity | Reviewable output or explicit prerequisite |
|---|---|---|
| 06:00 | Tender/bid scan | Source-linked search-signal research briefs; original source verification required |
| 06:30 | Project/award scan | Source-linked research, with actual account/query coverage |
| 07:00 | Decision-maker mapping | Saved contact roles/sources and team-supplied introductions; unknown bid ownership stays unknown |
| 07:30 | Lead rooms | Up to five initial/updated AI room drafts; real stage, team-note or matching research changes can trigger a revision after prior drafts are applied; reviewer approval still required |
| 09:00 | Outreach | Existing email drafts plus LinkedIn/WhatsApp message drafts for up to five screened leads; nothing sent |
| 10:00 | Partner touch | One discussion/update draft for a real saved partner |
| 11:00 | Proposal/scope follow-up | Follow-up drafts for recorded sent email older than three days; otherwise scope-call preparation for real active opportunities |
| 14:00 | Existing-client check | Draft next-project or training enquiry for a Won or explicitly recorded customer |
| 16:00 | Content/proof piece | Social captions and Instagram/Facebook graphic cards; consented proof is required for proof-based copy |
| 18:00 | Evening scan/summary | Another research brief and an internal summary of actual saved jobs, drafts and blockers |

## Training outputs

| Time IST | Activity | Reviewable output or explicit prerequisite |
|---|---|---|
| 06:00 | Hiring scan | Source-linked hiring signals, not proof of a confirmed training requirement |
| 09:00 | Academic partnership | Discussion draft for a saved college/university lead |
| 10:00 | L&D outreach | Email, LinkedIn and WhatsApp message drafts for screened contacts |
| 11:00 | Batch follow-ups | Drafts based on recorded sent messages or saved opportunity notes; no invented batches/dates |
| 14:00 | Existing-client training | Draft for actual customer records; VITALS/XIM customers must be supplied because those pipelines are not connected here |
| 16:00 | Trainee story/content | Use supplied consented story facts, or prepare educational alternatives and flag the missing proof |
| 18:00 | Daily summary | Internal factual report; not emailed or WhatsApped automatically |

## Research requirements and limits

The existing provider keys and monthly request caps remain required. Company
discovery keeps priority over signal research when jobs are due together.

Retaining Brave search results requires a plan granting storage rights, according
to [Brave's official API guidance](https://brave.com/search/api/). Confirm that
your account has those rights before setting **`BRAVE_SEARCH_STORAGE_ALLOWED=1`**
in the hosting environment. Without this setting the research activities show
**needs input**, make no research calls, and store no research results. Other
draft workflows can still run from existing records.

Each research activity reserves one search-run slot and up to twelve Brave
requests before making calls. Named accounts are searched in batches of up to
five, ordinarily covering sixty named accounts within twelve requests. Long
names can require smaller batches. At most the first five configured countries
are included in each activity; narrow campaigns by market for accurate coverage.
Coverage is reported explicitly. This is bounded search research, not an
exhaustive market scan or a direct procurement-portal integration.

Queries respect the [Brave query limits](https://api-dashboard.search.brave.com/api-reference/web/search/get).
Results use the past-month freshness filter. Public search titles/excerpts do not
confirm an active tender, award, bid owner, deadline or a buyer's need. Original
publisher links are supplied for checking. Research is kept internally and is not
automatically republished as marketing content.

The initial pilot caps (for example five searches per month) are much smaller than
a daily multi-service rhythm needs. The app reports **needs budget** instead of
raising limits or spending beyond them. Account managers decide appropriate caps.

## What review means

- **needs review:** real outputs are saved and waiting for human review.
- **needs input:** a required source, partner, customer or other fact is missing.
- **needs budget:** the next request was blocked by the configured cap.
- **needs you:** a provider failed or a partially completed activity needs attention.
- **no action:** no legitimate follow-up/activity is due from the recorded facts.
- **Reviewed:** the linked outputs have been approved/reviewed/applied.

The Daily Rhythm table links directly to outputs. Internal briefs have **Mark
reviewed**, not a sent/published action. Messages and posts remain pending until
reviewed. Room drafts do not overwrite existing notes without **Apply to room**.

Known contact titles are mapped deterministically; daily counts/reports are
assembled from saved records. AI is used for writing drafts, not for inventing
contacts, results or relationship evidence. Room context can include matching
licensed research signals, explicitly labelled unverified. Public posts receive
the offering, campaign direction and any explicitly consented proof notes, not
the private lead list or contact history.

## Graphic cards

Instagram/Facebook drafts include original navy/white typography cards generated
from the draft's headline and opening paragraph. Download them as editable
1080×1080 SVG files or export PNG directly from the content draft. They update when draft text changes.
These are graphic layouts, not generated photographs or claimed client images.
The full caption remains visible separately even when a layout shortens text.

## Practical limits still requiring people or integrations

- The current product has two offering pipelines, not all five in the specification.
- Real bid ownership, warm introductions and customer relationships need source
  records; the software cannot infer them from a job title.
- Confirmed meetings, replies, opt-outs, delivery results and sales depend on
  accurate recorded facts or later integrations. The AI does not infer them.
- Consented proof and trainee stories need real source material. Educational
  alternatives are labelled and never presented as proof.
- Generated wording still needs review. Automated rule checks cannot establish
  that every factual statement or marketing angle is correct.
- Raster/photo generation, direct tender-portal ingestion, reply ingestion and
  adaptive sales strategy allocation are outside this release.

Tests use simulated provider responses; they establish execution, accounting,
pause, idempotency and data-boundary behavior. Live draft quality must be verified
against real examples on the hosted application before declaring the full
business requirement accepted.
