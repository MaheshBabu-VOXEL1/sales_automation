# Voxel1 Prospect Desk — first working slice

A local, dependency-free prototype with two separate service pipelines: **Training** and **BIM Services**. Each product has its own editable ICP, a user-triggered company search, public contact fields where available, and manually recorded interest status.

## Run

Requires Python 3.10 or newer. From `D:\sale automation`:

```powershell
python server.py
```

Open <http://127.0.0.1:8001>. Data is stored locally in `data/voxel1.db`. To use another port, set `VOXEL1_PORT` before starting the server.

Run the backend tests with `python -m unittest discover -s tests -v`.

If the page says an older Voxel1 server is running, stop the existing `python server.py` process, start it again from this folder, and refresh the browser tab. The current ICP form requires a backend response that includes `countries`; the page disables saving/searching when it detects an older response.

## What search does

The ICP form lets the team select countries of focus **independently for Training and BIM Services**. The five initial countries are USA, UAE, Saudi Arabia, India and Singapore; other country names can also be saved. The form records industries, employee range, decision-maker titles, positive/exclusion keywords, goal and notes. The current free discovery adapter uses only selected countries and industry tags; the other fields are saved for future qualification/enrichment and are **not yet applied as search filters**.

Clicking **Search selected countries** uses a public OpenStreetMap Overpass instance for supported countries only. Each has one bounded 12 km city sample: New York, Dubai, Riyadh, Mumbai or Singapore. Each query is capped at 40 map records and runs sequentially. Other countries remain in the ICP but have no connected discovery provider yet; the app reports that rather than implying they were searched. This is **not complete country-wide coverage**. Repeat searches do not duplicate the same map record within a service. Partial country failures are reported instead of being presented as zero leads.

Email and phone fields are displayed only if the public map record contains them. These are **company-level, unverified public fields**, not Apollo decision-maker records. Blank fields stay blank. The interface links each result to its source record. Data coverage can be sparse; a search result is a candidate, not verified ICP fit.

The **Interested / Not interested** dropdown is set by a human after an actual interaction. Discovery never infers interest. The optional note can record evidence of the response.

## Limits before real deployment

This runs on localhost with no login or multi-user access control. Do not expose the server to a network or use it as a production CRM. It does not send email, contact leads, call anyone, connect to Claude or Apollo, verify contact details, or automate voice calls. A production build needs authenticated users, approved ICP versions, richer discovery/enrichment providers, qualification review, provider licensing checks, privacy controls and audited outreach before outbound work.

The public Overpass service is volunteer-operated and unsuitable for bulk prospecting. Search is bounded and user-triggered here. For full country-wide discovery or significant volume, choose a contracted data source and verify its five-country coverage, or operate an appropriate OpenStreetMap extract. See the [OpenStreetMap Overpass guidance](https://wiki.openstreetmap.org/wiki/Overpass_API). This prototype makes no Nominatim calls.
