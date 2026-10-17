# Business inputs needed to activate the remaining workflow

Keep these fields empty until an owner supplies real information. Do not enter
fixture companies from automated tests into the live app.

| Input | What the owner supplies | Where it is used | Current status |
|---|---|---|---|
| Sales target | Actual quarterly number and quarter | Sales Goal | Goal is 0 |
| Named target accounts | Legal company name, website, country, desired service | Sales Goal and saved lead | No approved account list supplied |
| PMC/consultant partners | Actual company and nature of relationship; save matching lead | Sales Goal → Partner accounts | Missing |
| Existing clients | Actual client name, matching saved lead, relevant approved history | Sales Goal → Existing clients | Missing |
| Warm introductions | Who can introduce whom, relationship, permission | Sales Goal relationship notes | Missing |
| Public proof | Approved factual project/training example, source, permitted wording, consent | Approved proof and proof consent | Missing |
| Capabilities | Owner confirms usable website facts and any limitations | knowledge/bim.json | Website-derived; owner approval pending |
| Contacts | Current employer, work email, role, source, confirmation date | Lead review | Mismatches and missing contacts remain |
| Social targets | Desired drafts/day by channel | Sales Goal → Content targets | All 0; no live content expected |
| Brave storage rights | Account plan explicitly permitting retained search results | Server setting after confirmation | Unconfirmed; research blocked |
| Provider allowance | Owner-approved monthly app caps and provider subscriptions | Server configuration | Search 5/5; caps unchanged |
| Training campaign | Buyer type, offer, countries, actual accounts and approved training facts | Training Sales Goal | No live campaign activated |

Copyable record for each partner/client:

- Company:
- Website/country:
- Partner or existing client:
- Matching lead:
- Actual relationship/history:
- Approved facts and source:
- Introduction/contact permission:
- Owner and confirmation date:

Copyable proof record:

- Approved example and factual wording:
- Evidence/source:
- People/companies that may be named:
- Consent to use publicly:
- Owner approval and date:

Domain matching or an Apollo verified-email label does not prove employment,
interest or contact permission. Company switchboards are not direct phone lines.
Do not approve DAR or Khansaheb recipient identity from the current email alone.

Owner decision, 16 October: BIM partner activity is disabled and partner names
are not a required input. Existing-client information is still separate.

## Partner requirement restored — latest owner decision, 16 October

The owner requested undoing the no-partner preference after confirming sir's
original scope. BIM partner_enabled is now true. Today's original needs_input
outcome was restored from the disable audit event. All other campaign fields
were preserved; no draft generation, cap change or sending was performed.
Partner details are once again required for this activity to produce a draft.
This supersedes the earlier owner decision to disable partners. The optional
setting remains available in the product, but is currently enabled for BIM.
