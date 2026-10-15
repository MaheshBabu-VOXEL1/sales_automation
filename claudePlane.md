# Claude Plan — Voxel1 Growth Engine Build Specification

Source: [Voxel1 Growth Engine — Build Spec](https://claude.ai/artifact/RYs5R2rDJpSsa9jQFiMEMv#26c7d406-2e2f)  
Source document date: 14 October 2026  
Read and documented: 15 October 2026

This is a structured summary of the Claude artifact, read through its rendered document. It is not a verbatim export. Sections 1–12 describe the source specification; sections 13–15 provide comparison and implementation interpretation. The source is a proposed build specification, not evidence that features already work. Its instructions are documented as requirements, not treated as authorization to send messages, publish content, buy services, or change infrastructure.

## 1. Purpose and scope

Build a Growth Engine that runs Voxel1's marketing, business development, and sales through five offering agents. Each agent has a quarterly sales goal and a daily operating rhythm. People approve outward-facing work; agents prepare and execute the approved workflows.

The artifact proposes a roughly ten-week v1 delivery plan tied to a frozen demonstration UI. This is a source estimate, not a delivery commitment made in this chat.

| Agent | Source strategy |
|---|---|
| BIM Services | Become the named BIM team inside other firms' bids, then convert clients into rate contracts |
| Design Services | Reach promoters before designers are appointed; serve as a production partner to Gulf consultants |
| VITALS | Sell verifiable progress to developers and through lenders |
| XIM Platform | Enter when firms set BIM direction; demonstrate XIM using their own building |
| Training | Train people who hire and buy, while building Voxel1's talent bench |

### Included in v1

- Daily scanning, mapping, drafting, follow-ups, and reporting per agent.
- Leads and private, project-specific lead rooms.
- Content planning, publishing, and channel results.
- A shared approvals queue with priority, service, and type filters.
- Individual-agent and global pause controls.

### Excluded from v1

- Sending without approval.
- Paid ad buying; only proposed budgets are drafted for review.
- Autonomous proposal pricing; prices come from approved rate cards.
- Delivery and billing, which remain in the separate Voxel1 workspace app.

## 2. Screens and interactions

The source calls for two main screens, a single column up to 880 px wide, a service pill selector, a phone bottom bar, and a laptop top bar. It requires support down to 390 px without horizontal page scrolling.

### Services screen

| Area | Information | Actions |
|---|---|---|
| Header | Agent name/status, strategy, won sales versus goal, likely sales, lead count, completed activities, items needing the owner, current activity | Pause/resume |
| Today | Chronological activities with time, type, title, result, and status | Open the associated lead from a Needs You activity |
| Leads | Name, location, pipeline stage, heat, next step, and owner | Open lead room |
| Content | Channel totals, enquiries, meetings, effort share, weekly pieces, status, results | Approve/edit drafts |
| Lead room | Stage, next steps, ownership and due dates, client-facing material, engagement, history | Approve/edit steps needing input |

Activity statuses in the source are Done, Running, Needs You, and Later.

### Approvals screen

- One list across all offerings.
- Filters: High/Medium/Low priority, offering, and type (lead, content, ad budget).
- Actions: View draft, Open lead, Approve.
- Approved records remain visible and marked.
- High priority: proposal-stage deal or hot lead.
- Medium priority: new lead or ad budget.
- Low priority: scheduled post.
- Counts update across the application after approval.

## 3. Sales goals and agent configuration

**The artifact explicitly defines a numeric sales goal per quarter.** Its BIM example is four sales. That target is one part of a broader agent configuration, not the entire configuration.

| Configuration | BIM example or source expectation |
|---|---|
| Quarterly sales goal | 4 sales; example, not a confirmed live target |
| Strategy | Become the named BIM team in other firms' bids |
| Target accounts | Approximately 60 named developers, EPCs, metro/Gulf consultants, and PMCs |
| Plays and starting effort | Named seat in bids 40%; existing-client expansion 30%; PMC partners 20%; Gulf production 10% |
| Signals | Tenders requiring a BIM lead, project awards, RERA registrations, BIM hiring |
| Rhythm | Timed activities with type, frequency, and expected output |
| Channels | LinkedIn company/K profiles, website, email, events, AI answers |
| Rules | Message caps, approvals, price bands, tone |

The source identifies K as the configuration owner. Agents must not change goals, target lists, price bands, or rules themselves.

### Agent operating loop

1. Scan signals and score them against target accounts.
2. Select three to five worthwhile opportunities and identify the warmest introduction path.
3. Build/update lead rooms and prepare messages, proposals, and posts.
4. Queue external outputs for approval, then send approved outputs.
5. Follow up, record results, and report the day.

### Weekly strategy changes

- Compare plays using replies, meetings, proposals, and sales per hour of effort.
- Shift at most 15 percentage points of effort per week.
- Keep every play at or above 5%.
- Record each change and its reason; show it to K and allow reversal.

These rules require reliable measurement and a precise interpretation of the 15-point limit before implementation.

## 4. Proposed data model

The source proposes PostgreSQL with ten core tables, plus strategy-shift and audit records. It broadly requests service ownership and creation/update timestamps on records.

| Entity | Main fields and purpose |
|---|---|
| service | Name, code, strategy, sales goal, won/likely counts, status, plays and effort allocation |
| account | Name, organization type, country/city, tier, warm introduction path |
| contact | Account, name, role, email, phone, LinkedIn, contact permission/source/date |
| signal | Offering/account, signal type, source URL, discovery time, score, selection state |
| lead | Offering/account, stage, heat, value, next step |
| step | Lead, title, due date, owner, status, linked draft |
| room | Lead, private slug, sections, draft/live status, engagement counters |
| draft | Kind, body, channel, priority, status, approving person and time |
| activity | Offering, scheduled time, type, title, frequency, result, status, execution time |
| content | Offering, day, channel, title, purpose, status, reach, enquiries, meetings |
| strategy_shift | Offering, allocation before/after, reason, timestamp |
| audit_log | Sends, approvals, pauses, and other accountable actions |

Pipeline: New → Engaged → Meeting → Proposal → Negotiation → Won, with Lost as an outcome. Heat labels: New, Hot, Warm, Cold.

The source describes accounts as shared across services while also broadly requiring service IDs. The actual schema needs an explicit relationship for accounts used by multiple offerings.

## 5. Jobs and schedules

The source specifies working-day schedules in IST, supplemented by event triggers. Each execution writes an activity record.

| Job | Schedule or trigger | Output |
|---|---|---|
| Scan signals | 06:00 and 18:00 | Scored signal records |
| Pick and map | 07:00 and high-scoring signal arrival | Three to five opportunities, decision-makers, introduction paths |
| Build/update rooms | 07:30 and lead-stage change | Room drafts for approval |
| Draft outreach | 09:00; maximum five per agent | Approval-queue drafts |
| Partner touch | 10:00; one per agent | Partner update draft |
| Follow-ups | 11:00 and three days after no response to a sent item | Follow-up drafts |
| Publish content | 12:00 | Scheduled, approved content published |
| Client check | 14:00 | Cross-sell and next-project opportunities |
| Day summary | 18:00 | WhatsApp/email summary to K |
| Next week's content | Friday 16:00 | Draft calendar |
| Strategy review | Monday 06:00 | Logged effort-allocation changes |

### Event triggers

- Reply: classify as interested, question, not now, or opt out; draft an answer and suggest a meeting slot.
- Room opened/forwarded: update engagement and heat; map an additional contact if identifiable.
- Room unopened for five days: draft a different angle or introduction path.
- Approval: source requests sending within five minutes, recording the action, and scheduling follow-up.

Viewer/device activity alone cannot reliably identify a new person or prove a forward; the implementation must distinguish measured events from inferences.

## 6. Approval and pause behavior

1. Create a prioritized draft linked to a lead or content item.
2. Display it in Approvals and the relevant contextual view.
3. K approves, edits, or leaves it pending. Time passing must never substitute for approval.
4. Approval releases the send job; successful execution completes the associated step/content item.
5. The artifact says pause immediately stops sends and publishing, while scans continue.

This last rule differs from the meeting, which describes pausing all automated work for an offering. See section 13 before choosing final behavior.

## 7. Sources and integrations proposed by the artifact

| Need | Proposed source/provider | Notes in source |
|---|---|---|
| Tenders | CPPP, GeM, state procurement, Dubai/Abu Dhabi portals, Saudi Etimad | Feeds/scraping subject to portal terms |
| RERA | Telangana, Karnataka, Maharashtra first | Registrations and quarterly filings; Progress Index input |
| Awards/land/launches | News search and company announcements | Web-search API |
| Hiring | Public postings | Job API or alerts |
| Contacts | Manual LinkedIn/Sales Navigator, company sites, selected B2B provider | Business contacts with source and permission records |
| Email | Google Workspace or Microsoft 365, to confirm | Separate warmed sending subdomain and daily caps |
| WhatsApp | Business API provider, to choose | Opted-in contacts |
| LinkedIn | Company-page API; personal-profile drafts | K posts personal content manually |
| Instagram/Facebook/YouTube | Meta Graph API and YouTube Data API | Publishing and metrics |
| Advertising | Proposed ChatGPT/Google AI/Meta ad budgets | Budget drafts only; no buying in v1 |
| Calendar | Google or Outlook | Meeting availability and booking |
| AI | Claude API | Larger models for drafting/strategy, smaller for classification |

These are proposed integrations, not verified claims of current API support, account access, licensing, or availability. The existing local implementation uses different providers for some operations.

## 8. Lead rooms

A room is a private account-specific web page that develops with the opportunity.

| Stage/content level | Typical material |
|---|---|
| Insight | Project observation, bid requirement, filing status, or site study; proposed Voxel1 contribution |
| Their model | Their building/tower in XIM or VITALS with derived drawings/progress |
| Proposal | Scope, team, schedule, and the source's “two-number price” on a Voxel1 template |
| Delivery | Weekly progress and relevant next offering |

The meaning of “two-number price” needs clarification; it is not defined further in the artifact.

Room requirements:

- Draft from actual lead documents/public records; obtain approval before sharing.
- Use Voxel1 navy/white branding and India rather than a city in public copy.
- No invented references; client consent for delivered-work examples.
- Host on a Voxel1 subdomain with non-indexed random links.
- Optional email-verified access for proposals and revocable links.
- Show a notice that views are recorded.
- Track supported engagement events, including opens and section activity.
- Source heat rules: opened within 24 hours = hot; within seven days = warm; unopened for five days = cold.

The warm/cold windows overlap and need precedence rules. Identity and forwarding metrics must reflect what is actually measurable.

## 9. Architecture

| Layer | Source proposal |
|---|---|
| Frontend | Next.js/React, mobile-first, matching the frozen demo |
| API/jobs | Node.js or Python with a job queue such as BullMQ or Celery |
| Database | Managed PostgreSQL and audit records |
| AI | Claude API with versioned prompts and validation before saving |
| Rooms | Rendered pages on a Voxel1 subdomain with tracking |
| Hosting | One cloud provider, India region |
| Monitoring | Job/send failure alerts to the BD lead and daily API cost reports |

The architecture separates drafting from delivery: agents write drafts, and approval releases eligible work to senders.

## 10. Source guardrails and security requirements

- Approval for every external message, room, post, proposal, and ad budget.
- At most five new conversations and one partner touch per agent per day.
- No free pilots, trial offers, or unapproved concessions.
- No invented projects, references, case studies, or numbers.
- Client consent for examples of delivered work.
- Public copy uses India, professional language, and approved pricing only.
- Immediate opt-out handling across agents.
- Contact-source and lawful-basis records; deletion-request handling.
- Opt-in requirements for WhatsApp/bulk email and email unsubscribe support.
- Portal access only under permitted terms.
- Team Google/Microsoft sign-in with Director, BD lead, Delivery head, and Training head roles.
- Managed secret storage; no credentials committed to code.
- Append-only audit history for sends, approvals, pauses, and strategy shifts.
- Encrypted client documents; source proposes deletion 90 days after losing a lead.

The artifact references Indian, Saudi, and UAE privacy laws and Gulf production-arrangement legal checks. These are recorded as source requirements, not independently verified legal guidance. No legal or platform-compliance assessment was performed for this summary.

## 11. Proposed build phases

| Phase | Source schedule | Completion criterion |
|---|---|---|
| Foundation | Weeks 1–2 | Real data, sign-in, screens, approvals, pause, audit; a manually entered draft sends from Voxel1 after approval |
| VITALS and BIM | Weeks 3–5 | Scans, mapping, rooms, outreach, follow-ups, summaries; both run a full day with every send awaiting approval |
| Content | Weeks 6–7 | Channel connections, calendar, publishing, metrics; one week's approved content per live agent |
| Design, XIM, Training and strategy | Weeks 8–10 | Remaining agents, reviews, room engagement; all five operate for a week with reasoned strategy shifts |

Proposed team: one full-stack lead, one backend/integrations engineer, one part-time room designer, and K's BD lead for content and account lists.

## 12. Source decisions still open

- Actual quarterly sales targets for every offering.
- Named target accounts: approximately 60 for BIM and 40 for the others as starting suggestions.
- Contact-data and WhatsApp providers.
- Google Workspace versus Microsoft 365 email.
- Approved rate cards and price bands.
- Which client projects have permission to be used as proof.
- Extend the Voxel1 workspace application or build separately.

## 13. Differences from the meeting and supplied HTML

| Topic | Claude artifact | Meeting / other supplied reference | Resolution needed |
|---|---|---|---|
| Sales goal | Numeric quarterly sales target plus wider configuration | Goal-setting also includes country, services, audience, campaign duration, and content cadence | Support both outcome targets and campaign instructions |
| Product name | XIM Platform | English meeting transcript says XAM | Confirm official name; do not silently rename |
| Pause | Stop sends/publishing; continue scans | Meeting says stop other agents' automated work | Decide pause semantics explicitly |
| Delivery timing | Send within five minutes of approval | Meeting says wait for the recipient's suitable local time | Prefer recipient windows when implementing the meeting request; clarify the five-minute expectation |
| Content timing | Generic publish job at 12:00 | Supplied BIM/Training HTML has content-related activity at 16:00 | Retain offering-specific rhythms until a revised schedule is agreed |
| Rollout | BIM and VITALS first; XIM later | Meeting names BIM, XAM, and Vitals as urgent | Align priorities before making delivery commitments |
| Layout | 880 px single-column frozen demo | Supplied HTML uses a sidebar/workspace layout | Confirm which reference governs the final UI |

The more specific supplied BIM and Training rhythms should not be silently replaced by the artifact's shared job timetable.

## 14. Relationship to the current local application

Based on the work inspected and changed in this chat:

- The application supports BIM and Training, rather than all five offerings.
- It has saved goals/strategy, ICP targeting, leads, internal rooms, drafts, approvals, and pause controls.
- The current numeric sales goal is a won-deal target without full quarter-based goal tracking. A numeric goal is valid according to this artifact, but insufficient by itself for the meeting's broader goal-setting workflow.
- The reference's ten BIM and six Training activities are now stored in a shared rhythm definition.
- Optional daily planning creates task records on weekdays from 06:00 IST while the server runs. It does not perform the business activities.
- Searches and AI drafting are user-triggered; approved drafts are not sent automatically.
- Rooms are currently internal records, not the private client-facing tracked pages proposed here.
- The local stack is Python with a plain JavaScript frontend, SQLite by default, and PostgreSQL support; it is not the proposed Next.js stack.
- Existing provider use includes Apollo/Brave and optional Gemini, rather than the artifact's proposed Claude-centered setup.

These points summarize known differences, not a new exhaustive code audit. Local edits have not been committed or pushed in this conversation.

## 15. Recommended next implementation work

1. Expand goal configuration to combine quarterly sales targets with campaign direction: geography, services, audiences/accounts, duration, content cadence, plays, and operational rules.
2. Connect that configuration to actual job inputs rather than merely displaying it beside a fixed template.
3. Complete a bounded BIM workflow: discover relevant signals, map prospects, prepare a useful draft, and queue it for review.
4. Add a version-specific approval and delivery queue after selecting the sending account/provider. Respect recipient time windows, pause, opt-outs, and daily limits.
5. Record outcomes and failures accurately; distinguish planned tasks, executed jobs, approved drafts, and confirmed delivery.
6. Extend to the other priority offerings with their own strategies and integrations.

The immediate product requirement is **a goal-driven operating workflow**, with a quarterly sales outcome and configurable campaign instructions guiding execution.
