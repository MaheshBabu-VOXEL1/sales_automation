# Deploy the demo on Render

The Vercel "Other" import screen is not sufficient for this repository. `server.py` is a long-running Python HTTP server; the frontend calls its `/api` routes, and SQLite needs persistent storage. This procedure deploys the **current prototype** as a small password-protected demo, not as a production sales platform.

1. In Render, create a **Web Service** from `MaheshBabu-VOXEL1/sales_automation`, branch `main`, root directory left blank, runtime **Python**. A paid web instance is needed for the SQLite disk option; a separate PostgreSQL database can also provide persistence.
2. Set build command to `pip install -r requirements.txt` and start command to `python server.py`.
3. Choose one storage setup:

   - **Render PostgreSQL:** Create a Render Postgres database in the **same region** as the web service. In the web service's Environment page, set `DATABASE_URL` to that database's **Internal Database URL**. Save and redeploy. This selects PostgreSQL; the old local SQLite file is not imported. Do not share the URL or put it in GitHub. Use a plan with a retention period suitable for your data; Render's free Postgres databases expire after 30 days.
   - **SQLite on a paid persistent disk:** Attach a disk mounted at `/opt/render/project/src/data`. The app stores `voxel1.db` there by default. Do not set `DATABASE_URL` for this option. A Free web service cannot attach a persistent disk.

   The current Render app contains test data only, so no SQLite-to-PostgreSQL import is needed. If real data is added before switching, export and migrate it first.
4. Set `VOXEL1_HOST=0.0.0.0`. Choose one access mode:

   - **Open without login:** set `VOXEL1_PUBLIC_NO_AUTH=1`. This overrides any existing `VOXEL1_AUTH_USER` and `VOXEL1_AUTH_PASSWORD` values. Anyone who reaches the public URL can view contact details, edit ICPs and interest statuses, and start searches. Use only for an intentionally public demo without sensitive data.
   - **Private browser password prompt:** do not set `VOXEL1_PUBLIC_NO_AUTH`; set both `VOXEL1_AUTH_USER` and `VOXEL1_AUTH_PASSWORD` to private, strong values.

   The environment variables are:

   | Name | Value |
   | --- | --- |
   | `VOXEL1_HOST` | `0.0.0.0` |
   | `VOXEL1_PUBLIC_NO_AUTH` | `1` only when intentionally opening the whole app without login |
   | `VOXEL1_AUTH_USER` | Private mode only: a username chosen by your team |
   | `VOXEL1_AUTH_PASSWORD` | Private mode only: a strong, unique password |

   Render provides `PORT` to the app. Do not put passwords in GitHub, this document, or a chat message. The app refuses public binding unless a complete pair of credentials or the explicit public flag is set.
5. Deploy and open Render's HTTPS `onrender.com` URL. In public mode it opens directly; in private mode the browser requests the username and password. Confirm that the Training and BIM ICPs load, save a harmless test value, refresh, and confirm it persists. Do one small selected-country search and verify the result appears in the company table. After a redeploy, check that saved ICPs and leads are still there.

For the Apollo + Brave pilot, add `APOLLO_API_KEY` and `BRAVE_SEARCH_API_KEY` in the Render web service's **Environment** page, then save and redeploy. Keep both values secret and out of the browser. With only one key, search reports the missing one. With neither, it uses the old public-map sample. In open-without-login mode, API search is blocked until `VOXEL1_ALLOW_PUBLIC_SEARCH=1` is also set. That last setting lets any visitor spend the account's Apollo/Brave credits; prefer private access for the pilot. Search is capped at ten Apollo company candidates per click. The app does not yet enforce a monthly credit budget, and Apollo account/API access may still reject the selected endpoint.

The open mode makes all app data and write actions available to visitors; changing the URL name is not access control. For a real CRM, add individual accounts, access controls, audit logs, backups and a durable database strategy.

Without both provider keys, search uses a public OpenStreetMap Overpass city sample, not full-country coverage. It may return few contacts or fail temporarily. The Apollo + Brave mode checks public website evidence but does not use AI, enrich email, send outreach, or book meetings.

If the primary map connection fails, the search switches once to the documented global Private.coffee Overpass instance (`https://overpass.private.coffee/api/interpreter`) and uses that instance for remaining countries in the request. Only public location and industry queries are sent. HTTP rejections, including rate limits, do not trigger this fallback. TLS certificate verification remains enabled. A successful deployment does not confirm outbound access: verify one small search from the deployed app.
