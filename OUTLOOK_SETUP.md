# Connect Outlook for Voxel1 Growth Engine

Sending mailbox: **maheshbabu.d@voxel1.com**

The app now supports Microsoft sign-in, an email self-test, and an explicit queue
for approved outreach. A Microsoft application registration must be configured
once before the Connect Outlook button can work. An email address alone does not
grant mailbox access. Do not put your Microsoft password or client secret in chat,
source files, screenshots, or campaign fields.

## One-time Microsoft administrator setup

1. Open the [Microsoft Entra admin center](https://entra.microsoft.com/).
2. Under App registrations, create an application named **Voxel1 Growth Engine**.
   Use the organization's single tenant for this company mailbox.
3. Add a **Web** redirect URI exactly matching:
   `https://sales-automation-u8lk.onrender.com/api/outlook/callback`
4. Record the Application (client) ID and Directory (tenant) ID.
5. Add Microsoft Graph **delegated** permissions `User.Read` and `Mail.Send`.
   The sign-in flow also requests `offline_access` for background token renewal.
   Follow the organization's administrator-consent policy. Do not grant broad
   application-level mail access for this implementation.
6. Create a client secret and save its **value** directly into Render environment
   settings. Track its expiry so it can be rotated before it stops working.

Reference: [Register a Microsoft application](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).
The implementation uses [authorization code flow with PKCE](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow).

## Render settings

Open the existing Render web service's Environment page and add:

| Environment name | Value |
|---|---|
| `OUTLOOK_CLIENT_ID` | Application (client) ID from Entra |
| `OUTLOOK_CLIENT_SECRET` | Client secret **value**, not the secret ID |
| `OUTLOOK_TENANT_ID` | Directory (tenant) ID from Entra |
| `OUTLOOK_REDIRECT_URI` | `https://sales-automation-u8lk.onrender.com/api/outlook/callback` |
| `OUTLOOK_TOKEN_KEY` | A generated Fernet encryption key; retain it across redeploys |

Generate the encryption key privately on an administrator's computer:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the generated value directly into Render. Do not commit it. Changing or losing
this key prevents decryption of the saved Outlook connection and requires
reconnection. Keep it in the team's secret store.

Keep `VOXEL1_PUBLIC_NO_AUTH=0`, with `VOXEL1_AUTH_USER` and `VOXEL1_AUTH_PASSWORD`
set. Mail connection/sending are blocked in public or unauthenticated mode.
Use the existing durable database and run a single application process. The build
installs `requirements.txt`; start with `python server.py`.

Save the environment settings and redeploy.

## Connect and test

1. Sign in to Growth Engine and click **Outlook** in the top bar.
2. Click **Connect Outlook**. Sign in to Microsoft as
   **maheshbabu.d@voxel1.com** and grant the requested permissions.
3. Microsoft returns you to the app. If the app login appears again, sign back in;
   the Outlook connection is saved separately.
4. Clear the global pause for the self-test. Individual service pauses can remain.
5. Open **Outlook → Send test email to myself** and confirm.
6. Check the sender's Inbox and Sent Items. The app displays Microsoft acceptance,
   which is not proof of delivery. There are at most three test attempts per UTC day.

No live self-test has been sent as part of implementing this feature. It requires
the real Microsoft registration, account authorization, and the owner's test action.

## Send one approved lead email

1. Open an approved Email outreach draft and review its text and recipient.
2. Click **Send with Outlook**.
3. Confirm the exact business email address, permission to contact it, and its
   IANA timezone (for example `Asia/Riyadh` or `America/New_York`).
4. Click **Queue approved email**.
5. Review its status under **Outlook**. The worker submits during 09:00–17:00
   Monday–Friday in that timezone, up to five attempts per service per UTC day.

Connecting Outlook does not release previous approvals. Each message needs this
explicit queue action. The queue is bound to the approved draft revision. Editing,
reopening, rejecting, changing the recipient, or marking the lead inactive before
execution cancels that queued version. Reapprove and queue again if appropriate.

Pause blocks new submissions; an in-flight request cannot be recalled. Queued mail
can be cancelled from Outlook. Disconnect removes saved credentials and cancels
queued mail, while preserving submission records. Token revocation can also be
managed through Microsoft's connected-app permissions.

`Record as sent` remains the manual logging option. Use it only after sending
outside the app. Do not use it for a message already queued in Outlook.

## Delivery states and limitations

- **queued:** waiting for a working-hour window, capacity, or resume.
- **sending:** submission has started.
- **accepted:** Microsoft returned HTTP 202; check Sent Items and monitor delivery.
- **uncertain:** request failed or the process restarted mid-send. Inspect Sent Items;
  it is not retried automatically because that could duplicate an email.
- **cancelled:** cancelled by the owner, a changed draft/lead, or disconnection.

The [Microsoft Graph sendMail API](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0)
accepts submissions asynchronously. This release does not track delivery receipts,
bounces, replies, or automatic unsubscribe processing. Owners must record opt-outs
promptly as Not interested; the queue rechecks that status before sending.

Refresh-token credentials are encrypted in the database; OAuth state is one-time,
browser-bound, and expires after ten minutes. Authorization codes are omitted from
application access logs. Ensure upstream proxy logs also redact OAuth query strings.
This prototype uses the existing shared app login rather than individual user roles;
everyone with that login can operate the connected mailbox through the app.

For a local authorization test, register the exact localhost Web callback URI and
set `OUTLOOK_REDIRECT_URI` accordingly. HTTP callbacks are allowed only for
`localhost`/`127.0.0.1`. Production callbacks require HTTPS.
