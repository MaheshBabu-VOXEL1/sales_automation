# Pending draft corrections — 16 October 2026

Source: `data/live-workflow-audit.json` (read-only copy of the 23 pending message drafts).
**Applied 16 Oct 2026 ~13:00 IST** (at Mahesh's request) through the app's own
`growth.save_item` edit/reject path, so revisions and history events were recorded:
#2, #3, #4, #7 rejected (rev 1→2); #15, #20, #25, #27, #31 edited and still pending
approval (rev 1→2). Khansaheb (lead 15) archived, reason "wrong_location"; restore it
if UAE is added to the campaign. DAR is kept: the AI already drops the mismatched
contact name and uses a neutral greeting. Original texts are in
`data/live-workflow-audit.json`. Each change was made only after checking the draft was
still pending and unchanged since the audit. Nothing was sent; no Gemini request was made.
After: 29 pending, 4 rejected, 1 sent; 7 active BIM leads. Limits unchanged.

Checked against `knowledge/bim.json`: MEPF/LOD, NDA, clash resolution and CAD-to-BIM
claims are website-published facts (still awaiting owner approval, not invented).

## Cause fixed in code

LinkedIn/WhatsApp/partner prompts received the Sales Goal strategy as "team direction",
and the Clark WhatsApp draft quoted it ("to help win repeat work"). Outbound prompts now
mark goal/strategy text as internal context that must never be quoted
(`ai_draft.INTERNAL_GUIDANCE`; regression test in `tests/test_audit_fixes.py`).
Older email drafts #3 and #4 restated the AI screening note; that was already fixed
before today (the note is excluded from outbound facts).

## Contact problems (fix before approving anything for these leads)

| Lead | Problem | Needed |
|---|---|---|
| DAR ENGINEERING (19) | Contact email is `@afdb.org` (African Development Bank), not DAR | Real DAR contact or neutral greeting only |
| SAPAC (20), Nesma (21), Omrania (24) | No email address recorded, yet email drafts exist | A verified address before any email can be sent |
| Nesma (21) | Contact name masked by provider | Verified name, or keep the neutral greeting |
| Clark Construction (17) | US contractor; recorded contact is the company President | Confirm Clark is a real Saudi Scan-to-BIM prospect |
| Khansaheb (15) | UAE company; campaign targets Saudi Arabia; email domain differs from website | Decide whether UAE is in scope; verify contact |

## Recommended decisions

| Item | Lead | Decision | Reason |
|---|---|---|---|
| #2 Email | DAR | **Reject** | Greets the probably wrong person; duplicate of #5 |
| #3 Email | SAPAC | **Reject** | States the unverified guess "utilizes BIM in-house" as fact; duplicate of #6 |
| #4 Email | Nesma | **Reject** | "We noticed ... ISO 19650 certification" comes from the unverified screening note; duplicate |
| #7 Email | Nesma | **Reject** | Duplicate of #33 |
| #5 Email | DAR | Keep | Neutral and correct; hold until a DAR contact is verified |
| #6 Email | SAPAC | Keep | Good; needs an email address |
| #33 Email | Nesma | Keep | Good; needs an email address |
| #25 Email | Omrania | **Edit** | Repeats the same services twice |
| #15 LinkedIn | Clark | **Edit** | Assumes "current projects in Saudi Arabia" |
| #20 WhatsApp | Clark | **Edit** | Quotes internal strategy "help win repeat work" |
| #27 LinkedIn | SAPAC | **Edit** | Repeats itself; asks about "requirements" not known to exist |
| #31 WhatsApp | Nesma | **Edit** | Opt-out line is garbled |
| #18 WhatsApp | Khansaheb | Hold | UAE outside campaign country — decision needed |
| #14, #16, #17, #19, #21, #28, #29, #30, #32 | various | Keep | Accurate; WhatsApp opt-in still unproven, so no delivery yet |

## Legacy failed jobs — disposition

Source: same audit copy (50 job records). Only three distinct failures exist; the rest are
`needs_input` (Brave rights, partners, clients, social targets) or waiting for review.

| Job | Days failed | Output saved? | Disposition |
|---|---|---|---|
| `message:LinkedIn:15` Khansaheb LinkedIn | 15 and 16 Oct | No (no output event) | Will be attempted once on the next scheduled outreach run |
| `message:WhatsApp:19` DAR WhatsApp | 15 and 16 Oct | No | Same |
| `room:20:…` SAPAC room | 16 Oct | No (SAPAC has no room draft or room event) | Next 07:30 room run will draft it, as no earlier attempt is recorded |

- These records use the older generic error text, have no retry token, and cannot be retried
  with the Retry button — this is intentional; the original cause was not captured.
- No duplicate risk: none of the three saved a draft, so the scheduler simply fills the gap.
  The current code records the specific reason and offers a controlled retry if one fails again.
- Cost: at most 3 Gemini requests on the next run, within the remaining allowance.
- The rhythm has no weekend check, so the next run is Saturday 17 Oct if the laptop is awake.
- Before that run, decide on DAR (wrong contact) and Khansaheb (UAE, outside the Saudi campaign).
  Archiving or rejecting a lead in the app stops further spend on it.
- The running app (started 12:23 IST) does not have the internal-strategy prompt fix. Restart it
  while idle, or the next run's LinkedIn/WhatsApp drafts can still quote the strategy.

## Corrected text

### #25 Email — Omrania
Title: Scan-to-BIM services from Voxel1

    Dear Karim Maghraby,

    Voxel1 is a BIM services company based in India serving the architecture, engineering and construction industry.

    We offer Scan-to-BIM: models produced from laser-scan data, covering architecture, structure and MEPF at the level of development each project requires.

    Would a short call be useful to discuss whether this could support Omrania's projects?

    If you would rather not hear from us, reply and we will not contact you again.

    The Voxel1 team

### #15 LinkedIn — Clark Construction Group

    Hi AJ, I'm reaching out from Voxel1, an India-based BIM services company. We provide Scan-to-BIM: models produced from laser-scan data across architecture, structure and MEPF. Would you be open to a short call with our BIM team to see whether this could support your projects?

### #20 WhatsApp — Clark Construction Group

    Hello AJ, this is Voxel1, a BIM services company based in India. We provide Scan-to-BIM, producing models from laser-scan data covering architecture, structure and MEPF. Would you be open to a short discovery call with our BIM team? If you would prefer no further messages, just let me know and we will stop.

### #27 LinkedIn — SAPAC

    Hello, I'm reaching out from Voxel1, a BIM services company based in India. We provide Scan-to-BIM: models produced from laser-scan data covering architecture, structure and MEPF at the level of development a project requires. Would you be open to a 30-minute call to see whether this could support your projects?

### #31 WhatsApp — Nesma & Partners

    Hello, this is Voxel1, a BIM services company based in India. We provide Scan-to-BIM, producing models from laser-scan data covering architecture, structure and MEPF. Would you be open to a short discovery meeting about BIM delivery support for Nesma & Partners? If you would prefer no further messages, just let me know and we will stop.

## Correction to legacy-job expectations

The next run is not a guaranteed repair: Khansaheb is archived and is excluded
unless deliberately restored and screened. A future day's scheduler may attempt
eligible DAR/SAPAC gaps within current limits, but old uncertain failures are not
cleared or replayed today. A missing saved output is not proof of the historical
provider's internal outcome. Do not claim guaranteed recovery or zero duplicate
risk from the generic legacy error alone.

The latest prompt fix also requires Scan-to-BIM in outbound bodies, rather than
allowing a subject/title-only mention. Training shared prompts now use its offer.
