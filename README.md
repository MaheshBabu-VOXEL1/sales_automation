# Voxel1 Growth Engine

An internal sales workspace with two service pipelines: **Training** and **BIM Services**. Each has its own targeting profile (ICP), user-triggered company search with monthly request caps, candidate review, lead rooms, a daily task plan, content drafts and an approvals queue. SQLite is the local default; set `DATABASE_URL` to a PostgreSQL URL for persistent hosted storage.

## Growth Engine workspace

The interface follows the Voxel1 Growth Engine design (top bar, service sidebar, KPI cards, Daily rhythm, Leads, Content, Approvals and lead rooms), limited to Training and BIM Services. Every figure comes from saved data; nothing is simulated.

- **Daily rhythm** lists tasks your team planned for today plus drafts waiting for approval. *Add suggested routine* creates that service's standard tasks for today as ordinary tasks owned by you. No scheduler or agent runs them.
- **Edit ICP** sits in every service workspace header, next to *Goal & strategy*, and opens that service's ICP (countries, industries, company size, titles, keywords, exclusions, goal, notes). Saving it never runs a search.
- **Leads** holds *Find companies* (*Edit ICP*, manual *Add company*, budgeted *Search companies*) and the lead list with filters. Rejected and archived leads keep their history.
- **Lead room** sets the sales stage (New → Won, or Lost), owner and a private room outline, and plans linked tasks and message drafts. It also shows why the lead is listed, its source, contacts, interest and review, and its full history. Rooms are internal: no client page is shared and no opens are tracked.
- **Content** plans drafts by channel and purpose. Reach, enquiries and meetings are not measured, because no social, email or analytics account is connected.
- **Approvals** lists pending content and message drafts across both services, with priority, service and type filters. **Approving never sends or posts anything.** Copy or download the approved text, send or post it yourself, then use *Record as sent/posted*. Editing a draft returns it to *Needs approval*.
- **Goal & strategy** sets each service's won-deal goal (it starts at 0). Won deals are counted from lead rooms set to *Won*.
- **Pause workspace / Pause all** blocks new searches, approvals and task completion until resumed. A search already running is not cancelled. Draft editing stays possible.
- **Dark mode** is remembered in this browser only.

Data lives in the `growth_settings`, `growth_items`, `growth_leads` and `growth_events` tables, alongside the existing tables. Edits use a revision number, so a stale browser cannot overwrite newer changes.

## Run

Requires Python 3.10 or newer. From `D:\sale automation`:

```powershell
python server.py
```

For PostgreSQL, first run `python -m pip install -r requirements.txt`, then set `DATABASE_URL` in the environment. Do not put a database URL in source files or screenshots. If `DATABASE_URL` is set but connection fails, startup fails rather than silently switching to SQLite.

Open <http://127.0.0.1:8001>. Data is stored locally in `data/voxel1.db`. To use another port, set `VOXEL1_PORT` before starting the server.

Run the backend tests with `python -m unittest discover -s tests -v`.

If the page says an older Voxel1 server is running, stop the existing `python server.py` process, start it again from this folder, and refresh the browser tab. The current ICP form requires a backend response that includes `countries`; the page disables saving/searching when it detects an older response.

## One-click company search

Set `APOLLO_API_KEY` and `BRAVE_SEARCH_API_KEY` as **server environment variables**. The browser never receives either key. With both configured, clicking **Search companies** runs a bounded pilot: Apollo searches companies across the selected countries (up to 10 per click), Brave checks for a BIM/Revit page on each company website, and Apollo searches relevant decision-maker titles for the qualifying companies. The app saves the company, its Apollo website link, and the first matched person's name/title. Brave results are checked in memory and not retained under its current API terms. Apollo's people-search response does not provide email or phone, so those fields stay blank unless optional enrichment is enabled. This workflow does not send messages or book meetings. A human should still review each match.

Obvious job boards and publications are skipped before Brave lookup or contact enrichment. This is a narrow quality filter, not a guarantee that remaining companies are suitable buyers. Previously saved leads are not removed automatically; review them in the app.

Optional AI buyer screening is enabled by setting `GEMINI_API_KEY` on the server. It uses the Gemini `gemini-2.5-flash-lite` model by default (`GEMINI_MODEL` can override it) to review up to ten Apollo candidates per click using company details and transient Brave page snippets. The prompt asks it to reject service vendors, training providers, directories, and ambiguous cases; a result is saved only if the model explicitly returns `qualified: true`. If Gemini fails, the candidate is skipped and a warning is shown. Gemini requests may incur charges under the account's plan. This is a plausible-buyer screen, not proof of a training need or purchase intent, and it does not revisit already saved leads. The app does not retain Brave response data. For an approved candidate it saves Gemini's short reason (up to 240 characters), the model name and the screening time; rejected candidates' explanations are not saved.

**AI drafts.** With `GEMINI_API_KEY` set, each active lead room has **Write draft with AI**. Gemini (`gemini-2.5-flash` by default; `GEMINI_DRAFT_MODEL` overrides it) writes a first-contact or follow-up email from only the facts the app stores about that lead: company, industry, country, website, contact, why it was listed, the screening note, the room outline, and up to three earlier approved or sent messages. Before saving, the draft is checked in code and thrown away if it offers a free pilot, trial or discount, quotes a price, names a city instead of India, or cites case studies or past work. It is saved as a pending Email draft for a person to edit and approve. Nothing is sent. Each attempt counts as one Gemini request against `VOXEL1_MONTHLY_GEMINI_REQUESTS`, including failed attempts, and drafting is refused while that cap is unset.

The candidate review table shows whether each saved lead has a recorded Gemini approval. Existing leads migrate with screening **not recorded**, since their earlier screening history cannot be verified; only a new Gemini-approved search result marks a lead as screened. The **Gemini-screened** filter shows those marked leads. A repeat search can mark an existing lead screened if Gemini approves it, without changing its interest status. This is still not proof of a buyer's need. The table distinguishes a verified Apollo work email from a company phone and flags provider-obfuscated names. Brave snippets are not retained; use the linked company website to verify fit. Previously saved leads remain in the table.

The Apollo company-search endpoint consumes credits. Brave also meters requests. A public app with `VOXEL1_PUBLIC_NO_AUTH=1` blocks these paid-provider searches unless `VOXEL1_ALLOW_PUBLIC_SEARCH=1` is explicitly set. Enabling that option lets anyone with the app URL trigger searches and spend the account's credits. Use app authentication or a private deployment for normal use. The pilot has a ten-company limit per click and the monthly request caps described below.

Optional location and contact enrichment is **off by default**. Set `APOLLO_ENRICH_DETAILS=1` on the server only after reviewing Apollo credits and privacy: each click then enriches at most the first three matching organizations (up to one credit each) and first three matched people (typically one credit each for email/demographics, with no phone reveal or waterfall). This can fill company city, industry, corporate phone and a verified work email when Apollo has them. The company search itself costs one credit per page. Repeat clicks may spend credits again and count against the monthly caps below. On a public, no-login deployment, anyone can initiate this and view saved contacts. Prefer authenticated access before storing real contact information. See Apollo's [API credit schedule](https://docs.apollo.io/docs/api-pricing).

## Candidate review

Each candidate shows **why it is listed** and **where it came from**:

- New Apollo + Brave results record the search that returned the company (countries and keyword tags) and that Brave found a page on the company's own domain mentioning BIM or Revit. The page URL and text are not stored.
- If Gemini approved it, the row shows Gemini's short reason, the model and the date. This is an AI judgement, not proof of need.
- OpenStreetMap results record the map category and city sample.
- Candidates saved before this version say **No reason recorded**; the app does not invent one.
- The source link is labelled as the Apollo company record's website or the OpenStreetMap record.

**Reject** (not a fit) or **Archive** (not now) moves a candidate out of the active list. A reason is required; **Other** also needs a note. Nothing is deleted: the company, its contacts, interest status and notes stay in the database, and **Rejected / archived** lists them with the reason, date and a **Restore** button. Later paid searches skip rejected and archived Apollo companies before any Brave, Gemini or Apollo people request, and searches never overwrite their saved record. Active-candidate counts and country totals exclude them.

**History** shows each candidate's events: added, found again, interest changes and review decisions with reasons and notes. Events are recorded from this version onward; earlier changes were not logged.

`GET /api/system` reports the storage type (PostgreSQL or SQLite), the PostgreSQL server version or whether the SQLite directory is a separate mount, and row counts. It never returns the database URL.

## Monthly search budget

Paid (Apollo + Brave) searches are **blocked until monthly caps are set** as server environment variables. Only whoever manages the server environment can change them; the shared app login cannot.

| Variable | Caps, per calendar month (UTC) |
| --- | --- |
| `VOXEL1_MONTHLY_SEARCH_LIMIT` | Search clicks that reached the providers, including failed ones |
| `VOXEL1_MONTHLY_APOLLO_REQUESTS` | Apollo requests (company search, people search, optional enrichment) |
| `VOXEL1_MONTHLY_BRAVE_REQUESTS` | Brave web-search requests |
| `VOXEL1_MONTHLY_GEMINI_REQUESTS` | Gemini requests (search screening plus AI drafts); needed only when `GEMINI_API_KEY` is set |

Unset or invalid values count as 0. Before each click the app shows the worst-case requests for the current settings: Apollo 11 (17 with `APOLLO_ENRICH_DETAILS=1`), Brave 10, Gemini 10 when enabled. The person must confirm that estimate. The server then checks every cap and reserves the full estimate in one database transaction, so concurrent clicks cannot overshoot. A search that does not fit makes no provider request. During the search each request is counted before it is sent, and the search stops before exceeding its reservation.

When a search finishes, the app records the requests it actually sent in the `provider_usage` ledger and in `search_runs`. Failed requests count too, because providers may still meter them. A search interrupted by a crash or restart keeps holding its full estimate, because its real count is unknown. These are **request counts, not credits or money**: an Apollo request can cost zero, one or several credits depending on the endpoint and plan. Compare with each provider's usage dashboard. The budget panel and `GET /api/budget` show this month's caps, measured use, held reservations and the ten most recent searches. The free OpenStreetMap mode is not budgeted.

If neither provider key is configured, the previous OpenStreetMap city-sample mode remains available. If only one key is configured, the button explains which other key is missing. Provider failures are shown in the UI; results without a matching website page are omitted.

## Legacy map search

The ICP form lets the team select countries of focus **independently for Training and BIM Services**. The five initial countries are USA, UAE, Saudi Arabia, India and Singapore; other country names can also be saved. The form records industries, employee range, decision-maker titles, positive/exclusion keywords, goal and notes. Apollo mode applies countries, employee range, titles, keywords and industry selections as keyword tags. Goal and notes are saved but are not provider filters.

Clicking **Search selected countries** uses a public OpenStreetMap Overpass instance for supported countries only. Each has one bounded 12 km city sample: New York, Dubai, Riyadh, Mumbai or Singapore. Each query is capped at 40 map records and runs sequentially. Other countries remain in the ICP but have no connected discovery provider yet; the app reports that rather than implying they were searched. This is **not complete country-wide coverage**. Repeat searches do not duplicate the same map record within a service. Partial country failures are reported instead of being presented as zero leads.

Email and phone fields are displayed only if the public map record contains them. These are **company-level, unverified public fields**, not Apollo decision-maker records. Blank fields stay blank. The interface links each result to its source record. Data coverage can be sparse; a search result is a candidate, not verified ICP fit.

The **Interested / Not interested** dropdown is set by a human after an actual interaction. Discovery never infers interest. The optional note can record evidence of the response.

## Limits before real deployment

This runs on localhost without a password by default. Public binding requires a shared username and password (`VOXEL1_AUTH_USER` and `VOXEL1_AUTH_PASSWORD`) or an explicit `VOXEL1_PUBLIC_NO_AUTH=1` opt-in. Private mode presents a normal `/login` page and uses a short-lived, HttpOnly session cookie, which works in browsers that do not support HTTP Basic Auth prompts. Existing HTTP Basic Auth still works for API clients. Five failed logins from the same address within a minute trigger a temporary limit. In open mode, anyone with the URL can see stored data and change it. It is not a production multi-user CRM: there are no individual accounts, access audit logs, password reset, or database backups managed by the app. It does not send email, contact leads, call anyone, connect to Claude, verify contact details, or automate voice calls. A production build needs authenticated users, approved ICP versions, privacy controls and audited outreach before outbound work.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the current Render deployment procedure. The current Python server and SQLite database cannot be deployed unchanged as a working Vercel project.

The public Overpass service is volunteer-operated and unsuitable for bulk prospecting. Search is bounded and user-triggered here. For full country-wide discovery or significant volume, choose a contracted data source and verify its five-country coverage, or operate an appropriate OpenStreetMap extract. See the [OpenStreetMap Overpass guidance](https://wiki.openstreetmap.org/wiki/Overpass_API). This prototype makes no Nominatim calls.
