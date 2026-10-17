# Voxel1 Growth Engine — project status

**Date:** 14 October 2026
**Live app:** <https://sales-automation-u8lk.onrender.com/>
**Code:** `MaheshBabu-VOXEL1/sales_automation`, branch `main`

This report covers three things: what Sir wants, what has been built so far, and what we need to do next.

---

## 1. What Sir wants

One Voxel1-owned, AI-assisted B2B sales system that runs the whole path in one place:

> **Find genuine companies → check they fit → find the decision-maker → get business contact details → draft a message → a person approves it → send it (email, later WhatsApp) → track replies → book meetings → report results and cost.**

**Agreed scope for now**

- Two services only: **Training** and **BIM Services**.
- Five target markets: **USA, UAE, Saudi Arabia, India, Singapore**.
- Volume: **under 500 companies a month**, starting with free or low-cost access to test quality.
- **One click** should do the research. Nobody should research companies by hand.
- The look should follow the *Voxel1 Growth Engine* design.

**Rules Sir set (non-negotiable)**

- A person approves every message or post before it goes out.
- Phone calls are made by employees only. No AI caller or auto-dialer.
- No WhatsApp message without the person's opt-in. A phone number is not permission.
- No LinkedIn bots or unauthorised scraping.
- The AI may suggest and draft, but must not invent facts, interest, contacts or results.

**Later phases**

- Appointment booking.
- LinkedIn and Instagram company posting.
- Reports on results and cost.

---

## 2. What has been done so far

### Built and live on Render

| Feature | What it does |
|---|---|
| Two service pipelines | Training and BIM Services each have their own ICP, leads and history. |
| ICP form | Countries, industries, company size, decision-maker titles, keywords, exclusions, goal and notes. Saving does not run a search. |
| One-click company search | Apollo finds up to 10 companies per click. Brave checks each company's website for BIM/Revit work. Gemini (optional) screens out unlikely buyers. Apollo then finds a decision-maker. |
| Monthly budget protection | Paid searches are **blocked until monthly limits are set** on the server. Before each search the app shows the worst-case number of requests and asks for confirmation. Every request is recorded, and two searches at once cannot overspend. |
| Private sign-in | A password-protected login page with one shared account. |
| Storage | PostgreSQL or SQLite. The **11 India companies** saved earlier are kept. |

### Pushed to `main`, live version not yet confirmed

These were pushed in commits `e15e4dd` and `b38d83c`. Render redeployed, but nobody has signed in to confirm the new version is the one running.

| Feature | What it does |
|---|---|
| Candidate review | **Reject** (not a fit) or **Archive** (not now) with a reason. Nothing is deleted, history is kept, and **Restore** brings a company back. Later searches skip rejected companies, which saves credits. |
| "Why listed" and source | Each lead shows why it was found and where the data came from. Older leads honestly say "No reason recorded". |
| **Growth Engine redesign** | New layout with sidebar, KPI cards, **Daily rhythm** (task plan), **Leads**, **Content**, **Approvals** queue and **lead rooms** (stage, owner, outline, next steps and history). |
| Goals, pause and dark mode | Sales goal per service, pause per workspace or for both, and a dark mode switch. |

### Done on this computer, not pushed yet

| Commit | Change |
|---|---|
| `4a348e3` | **Edit ICP** button in every service workspace header. |
| `4e4c18a` | Fixed the oversized ICP checkboxes; selected countries and industries now show in green. |

### Quality checks

- **57 automated tests** pass. They use simulated providers, so no credits are spent.
- Every button was clicked in a browser on test data, at desktop and phone width, in light and dark mode.
- **No paid search has been run.** No message has been sent and nothing has been posted.

---

## 3. What does NOT work yet

| Sir's step | Status |
|---|---|
| Search companies automatically (e.g. every day) | ❌ Manual button only. There is no scheduler. |
| Collect email and phone | ⚠️ Partial. Needs Apollo contact enrichment turned on, which costs credits. Phone is the company line only. |
| Write the message automatically | ❌ The team types drafts by hand. |
| Approve before sending | ✅ Built. |
| **Send email** | ❌ Not built. Approved text is copied and sent manually. |
| **Send WhatsApp** | ❌ Not built. Needs Meta's WhatsApp Business API and opt-in. |
| Track replies, book meetings | ❌ Not built. |
| LinkedIn and Instagram posting | ❌ Not built. |
| Per-person logins and roles | ❌ One shared login only. |

**Current blocker for searching:** no monthly limits are set on Render, so all paid searches are refused. This is on purpose until Voxel1 decides a budget.

---

## 4. What we need to do next

### Step 1 — Finish and confirm what is built *(no credits needed)*

1. Push `4a348e3` and `4e4c18a` to `main`.
2. Wait for Render to show the deploy as **Live**, then sign in and confirm:
   - the new layout loads;
   - the 11 companies are still there;
   - the database update worked;
   - searches are still blocked.
3. Check in the Render dashboard which database is used, whether it expires (free Render PostgreSQL expires after 30 days) and whether backups are on.

### Step 2 — AI message drafting *(no paid search needed)*

- Add a **"Write draft"** button on each lead. The AI writes a first email from that lead's real details only.
- A person edits it, then approves it.

### Step 3 — Email sending

- Connect Voxel1's sales mailbox (Google Workspace or Microsoft 365).
- **Approve & send** actually sends the email, with:
  - a daily send limit;
  - an unsubscribe line;
  - a do-not-contact list;
  - duplicate protection;
  - reply tracking.

### Step 4 — Small paid pilot *(only after Sir approves a budget)*

1. Set the monthly limits on Render.
2. Run a few searches per service.
3. Check the Apollo, Brave and Gemini dashboards for real cost.
4. Measure how many companies were relevant and how many usable contacts came back, per country.

### Step 5 — Automatic daily search

- A scheduled search per service, within the monthly limits.
- New leads arrive in the review queue every morning.

### Step 6 — Later channels

- **WhatsApp:** only for people who opted in (e.g. replied or filled a form), using approved templates.
- Then meeting booking.
- Then LinkedIn and Instagram company posting.
- Then per-person logins.
- Then backups and monitoring.

---

## 5. Decisions needed from Sir / Voxel1

1. **Monthly budget:** the money or credits per month, and how many searches.
2. **Who counts as a buyer** for Training and for BIM Services, and who to exclude. For example, a BIM services firm may be a competitor for one offer but a partner for another.
3. **Sales mailbox:** Google Workspace or Microsoft 365, plus the sender name and address.
4. **Who approves messages** before they are sent.
5. **Provider accounts:** what the Apollo plan includes, the Brave plan, and Gemini billing.
6. **The 11 older companies:** keep them, review them, or archive them.
7. **WhatsApp:** whether to set up a Meta WhatsApp Business account, and how opt-in will be collected.
