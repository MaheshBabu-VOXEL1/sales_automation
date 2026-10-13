# Deploy the private demo on Render

The Vercel "Other" import screen is not sufficient for this repository. `server.py` is a long-running Python HTTP server; the frontend calls its `/api` routes, and SQLite needs persistent storage. This procedure deploys the **current prototype** as a small password-protected demo, not as a production sales platform.

1. In Render, create a **Web Service** from `MaheshBabu-VOXEL1/sales_automation`, branch `main`, root directory `./`, runtime **Python**. Choose a **paid instance that supports a persistent disk**. Do not choose a free instance for data you need to keep.
2. Set build command to `python -m compileall -q server.py` and start command to `python server.py`.
3. Attach a persistent disk mounted at `/opt/render/project/src/data`. The application stores its database at `/opt/render/project/src/data/voxel1.db` by default. Alternatively, set `VOXEL1_DB` to an absolute path on your disk. Check the mount and database path match before using the app.
4. Set environment variables:

   | Name | Value |
   | --- | --- |
   | `VOXEL1_HOST` | `0.0.0.0` |
   | `VOXEL1_AUTH_USER` | A private username chosen by your team |
   | `VOXEL1_AUTH_PASSWORD` | A strong, unique password generated in your password manager |

   Render provides `PORT` to the app. Do not put the password in GitHub, this document, or a chat message. The app refuses public binding if either credential is missing.
5. Deploy and open Render's HTTPS `onrender.com` URL. Your browser should request the username and password. Confirm that the Training and BIM ICPs load, save a harmless test value, refresh, and confirm it persists. Do one small selected-country search and verify the result appears in the company table. After a redeploy, check that saved ICPs and leads are still there.

This is shared-password protection for a private demo. Give the URL and credentials only to intended team members through a password manager or another secure channel. Before using this as a real multi-user CRM, add individual accounts, access controls, audit logs, backups and a durable database strategy.

Current search uses a public OpenStreetMap Overpass city sample, not full-country coverage. It may return few contacts or fail temporarily. Apollo, Brave and AI integrations are not included.
