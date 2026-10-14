# Voxel1 Prospect Desk — first working slice

A small prototype with two separate service pipelines: **Training** and **BIM Services**. Each product has its own editable ICP, a user-triggered company search, public contact fields where available, and manually recorded interest status. SQLite is the local default; set `DATABASE_URL` to a PostgreSQL URL for persistent hosted storage.

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

Set `APOLLO_API_KEY` and `BRAVE_SEARCH_API_KEY` as **server environment variables**. The browser never receives either key. With both configured, clicking **Search companies** runs a bounded pilot: Apollo searches companies across the selected countries (up to 10 per click), Brave checks for a BIM/Revit page on each company website, and Apollo searches relevant decision-maker titles for the qualifying companies. The app saves the company, its Apollo website link, and the first matched person's name/title. Brave results are checked in memory and not retained under its current API terms. Apollo's people-search response does not provide email or phone, so those fields stay blank. This workflow does not send messages or book meetings. It does not call Gemini; relevance currently means a matching public page, and a human should still review each match.

The Apollo company-search endpoint consumes credits. Brave also meters requests. A public app with `VOXEL1_PUBLIC_NO_AUTH=1` blocks these paid-provider searches unless `VOXEL1_ALLOW_PUBLIC_SEARCH=1` is explicitly set. Enabling that option lets anyone with the app URL trigger searches and spend the account's credits. Use app authentication or a private deployment for normal use. The pilot has a ten-company limit per click but no monthly account-level credit budget.

If neither provider key is configured, the previous OpenStreetMap city-sample mode remains available. If only one key is configured, the button explains which other key is missing. Provider failures are shown in the UI; results without a matching website page are omitted.

## Legacy map search

The ICP form lets the team select countries of focus **independently for Training and BIM Services**. The five initial countries are USA, UAE, Saudi Arabia, India and Singapore; other country names can also be saved. The form records industries, employee range, decision-maker titles, positive/exclusion keywords, goal and notes. Apollo mode applies countries, employee range, titles, keywords and industry selections as keyword tags. Goal and notes are saved but are not provider filters.

Clicking **Search selected countries** uses a public OpenStreetMap Overpass instance for supported countries only. Each has one bounded 12 km city sample: New York, Dubai, Riyadh, Mumbai or Singapore. Each query is capped at 40 map records and runs sequentially. Other countries remain in the ICP but have no connected discovery provider yet; the app reports that rather than implying they were searched. This is **not complete country-wide coverage**. Repeat searches do not duplicate the same map record within a service. Partial country failures are reported instead of being presented as zero leads.

Email and phone fields are displayed only if the public map record contains them. These are **company-level, unverified public fields**, not Apollo decision-maker records. Blank fields stay blank. The interface links each result to its source record. Data coverage can be sparse; a search result is a candidate, not verified ICP fit.

The **Interested / Not interested** dropdown is set by a human after an actual interaction. Discovery never infers interest. The optional note can record evidence of the response.

## Limits before real deployment

This runs on localhost without a password by default. Public binding requires either a shared HTTP Basic Auth username and password or an explicit `VOXEL1_PUBLIC_NO_AUTH=1` opt-in. In open mode, anyone with the URL can see stored data and change it. It is not a production multi-user CRM: there are no individual accounts, access audit logs, password reset, rate limits or database backups managed by the app. It does not send email, contact leads, call anyone, connect to Claude, verify contact details, or automate voice calls. A production build needs authenticated users, approved ICP versions, privacy controls and audited outreach before outbound work.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the current Render deployment procedure. The current Python server and SQLite database cannot be deployed unchanged as a working Vercel project.

The public Overpass service is volunteer-operated and unsuitable for bulk prospecting. Search is bounded and user-triggered here. For full country-wide discovery or significant volume, choose a contracted data source and verify its five-country coverage, or operate an appropriate OpenStreetMap extract. See the [OpenStreetMap Overpass guidance](https://wiki.openstreetmap.org/wiki/Overpass_API). This prototype makes no Nominatim calls.
