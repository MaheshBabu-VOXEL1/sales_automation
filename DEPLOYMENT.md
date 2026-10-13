# Deploy the demo on Render

The Vercel "Other" import screen is not sufficient for this repository. `server.py` is a long-running Python HTTP server; the frontend calls its `/api` routes, and SQLite needs persistent storage. This procedure deploys the **current prototype** as a small password-protected demo, not as a production sales platform.

1. In Render, create a **Web Service** from `MaheshBabu-VOXEL1/sales_automation`, branch `main`, root directory `./`, runtime **Python**. Choose a **paid instance that supports a persistent disk**. Do not choose a free instance for data you need to keep.
2. Set build command to `python -m compileall -q server.py` and start command to `python server.py`.
3. Attach a persistent disk mounted at `/opt/render/project/src/data`. The application stores its database at `/opt/render/project/src/data/voxel1.db` by default. Alternatively, set `VOXEL1_DB` to an absolute path on your disk. Check the mount and database path match before using the app.
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

The open mode makes all app data and write actions available to visitors; changing the URL name is not access control. For a real CRM, add individual accounts, access controls, audit logs, backups and a durable database strategy.

Current search uses a public OpenStreetMap Overpass city sample, not full-country coverage. It may return few contacts or fail temporarily. Apollo, Brave and AI integrations are not included.
