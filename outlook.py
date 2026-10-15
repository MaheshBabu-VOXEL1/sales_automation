"""Delegated Microsoft Graph connection and explicit, revision-bound delivery queue."""
import base64
import hashlib
import json
import os
import re
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import closing
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import growth

SENDER = "maheshbabu.d@voxel1.com"
SCOPES = "offline_access User.Read Mail.Send"
LOCK = threading.RLock()
REQUIRED = ("OUTLOOK_CLIENT_ID", "OUTLOOK_CLIENT_SECRET", "OUTLOOK_TENANT_ID", "OUTLOOK_REDIRECT_URI", "OUTLOOK_TOKEN_KEY")


def init(db, run):
    run(db, """CREATE TABLE IF NOT EXISTS outlook_account (
        id INTEGER PRIMARY KEY, email TEXT NOT NULL, tokens TEXT NOT NULL, tested INTEGER NOT NULL DEFAULT 0)""")
    run(db, """CREATE TABLE IF NOT EXISTS outlook_states (
        state TEXT PRIMARY KEY, browser TEXT NOT NULL, verifier TEXT NOT NULL, expires BIGINT NOT NULL)""")
    run(db, """CREATE TABLE IF NOT EXISTS outlook_queue (
        id TEXT PRIMARY KEY, item_id BIGINT UNIQUE, revision INTEGER, service TEXT NOT NULL,
        recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL,
        timezone TEXT NOT NULL, state TEXT NOT NULL, result TEXT NOT NULL DEFAULT '',
        attempted_at TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL)""")


def cipher():
    from cryptography.fernet import Fernet
    try:
        return Fernet(os.environ.get("OUTLOOK_TOKEN_KEY", ""))
    except (ValueError, TypeError):
        raise ValueError("OUTLOOK_TOKEN_KEY must be a valid Fernet encryption key.") from None


def require_private(api):
    if api.PUBLIC_NO_AUTH or not (api.AUTH_USER and api.AUTH_PASSWORD):
        raise ValueError("Enable private app sign-in before connecting Outlook or sending email.")


def settings():
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        raise ValueError("Configure on the server: " + ", ".join(missing))
    tenant = os.environ["OUTLOOK_TENANT_ID"]
    if not re.fullmatch(r"[A-Za-z0-9.-]+", tenant):
        raise ValueError("Invalid Microsoft tenant ID.")
    redirect = os.environ["OUTLOOK_REDIRECT_URI"]
    parsed = urllib.parse.urlparse(redirect)
    if parsed.path != "/api/outlook/callback" or (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1"))):
        raise ValueError("Use an HTTPS Outlook callback URL (HTTP is allowed only on localhost).")
    cipher()
    return f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"


def http(url, *, form=None, token=None, data=None):
    headers = {}
    raw = None
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        raw = urllib.parse.urlencode(form).encode()
    if data is not None:
        headers["Content-Type"] = "application/json"
        raw = json.dumps(data).encode()
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=raw, headers=headers), timeout=25) as response:
            content = response.read()
            return response.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as exc:
        # Never expose provider responses containing credentials, codes, or messages.
        raise ValueError(f"Microsoft request failed (HTTP {exc.code}). Check account permissions and reconnect if needed.") from None
    except (OSError, ValueError):
        raise RuntimeError("Microsoft response was unavailable. Check Sent Items before retrying a send.") from None


def begin(api):
    require_private(api)
    authority = settings()
    state, browser, verifier = (secrets.token_urlsafe(40) for _ in range(3))
    with closing(api.connect()) as db, db:
        api.run(db, "DELETE FROM outlook_states WHERE expires<?", (int(time.time()),))
        api.run(db, "INSERT INTO outlook_states (state, browser, verifier, expires) VALUES (?, ?, ?, ?)",
                (state, hashlib.sha256(browser.encode()).hexdigest(), verifier, int(time.time()) + 600))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    params = {"client_id": os.environ["OUTLOOK_CLIENT_ID"], "response_type": "code", "response_mode": "query",
              "redirect_uri": os.environ["OUTLOOK_REDIRECT_URI"], "scope": SCOPES, "state": state,
              "code_challenge": challenge, "code_challenge_method": "S256", "login_hint": SENDER, "prompt": "select_account"}
    return authority + "/authorize?" + urllib.parse.urlencode(params), browser


def callback(api, query, browser):
    require_private(api)
    authority = settings()
    state, code = query.get("state", [""])[0], query.get("code", [""])[0]
    with closing(api.connect()) as db, db:
        row = api.run(db, "DELETE FROM outlook_states WHERE state=? RETURNING *", (state,)).fetchone()
    if not row or row["expires"] < time.time() or not browser or not secrets.compare_digest(row["browser"], hashlib.sha256(browser.encode()).hexdigest()):
        raise ValueError("Outlook sign-in expired or the browser changed. Start Connect Outlook again.")
    if not code or "error" in query:
        raise ValueError("Microsoft sign-in was cancelled or permission was not granted.")
    _, tokens = http(authority + "/token", form={"client_id": os.environ["OUTLOOK_CLIENT_ID"],
        "client_secret": os.environ["OUTLOOK_CLIENT_SECRET"], "grant_type": "authorization_code", "code": code,
        "code_verifier": row["verifier"], "redirect_uri": os.environ["OUTLOOK_REDIRECT_URI"], "scope": SCOPES})
    _, user = http("https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName", token=tokens["access_token"])
    if SENDER not in {str(user.get(k, "")).lower() for k in ("mail", "userPrincipalName")}:
        raise ValueError("Connect the requested mailbox: " + SENDER)
    if not tokens.get("refresh_token"):
        raise ValueError("Microsoft did not grant offline access. Reconnect and grant the requested permissions.")
    tokens["expires_at"] = time.time() + int(tokens.get("expires_in", 3600))
    encrypted = cipher().encrypt(json.dumps(tokens).encode()).decode()
    with LOCK, closing(api.connect()) as db, db:
        api.run(db, """INSERT INTO outlook_account (id, email, tokens, tested) VALUES (1, ?, ?, 0)
            ON CONFLICT(id) DO UPDATE SET email=excluded.email, tokens=excluded.tokens, tested=0""", (SENDER, encrypted))
        growth.event(db, api.run, "global", None, None, "outlook_connected", {"sender": SENDER})


def access_token(api):
    settings()
    with LOCK:
        with closing(api.connect()) as db:
            row = api.run(db, "SELECT * FROM outlook_account WHERE id=1").fetchone()
        if not row:
            raise ValueError("Connect Outlook first.")
        try:
            tokens = json.loads(cipher().decrypt(row["tokens"].encode()))
        except Exception:
            raise ValueError("Stored Outlook connection cannot be decrypted. Restore its encryption key or reconnect.") from None
        if tokens.get("expires_at", 0) < time.time() + 90:
            _, fresh = http(settings() + "/token", form={"client_id": os.environ["OUTLOOK_CLIENT_ID"],
                "client_secret": os.environ["OUTLOOK_CLIENT_SECRET"], "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"], "scope": SCOPES})
            tokens.update(fresh)
            tokens["expires_at"] = time.time() + int(fresh.get("expires_in", 3600))
            with closing(api.connect()) as db, db:
                api.run(db, "UPDATE outlook_account SET tokens=? WHERE id=1", (cipher().encrypt(json.dumps(tokens).encode()).decode(),))
        return tokens["access_token"]


def status(db, run):
    row = run(db, "SELECT email, tested FROM outlook_account WHERE id=1").fetchone()
    return {"sender": SENDER, "connected": bool(row), "tested": bool(row and row["tested"]),
            "missing": [k for k in REQUIRED if not os.environ.get(k)],
            "queue": [dict(r) for r in run(db, "SELECT id, item_id, service, recipient, timezone, state, result, created_at FROM outlook_queue ORDER BY created_at DESC LIMIT 50")]}


def queue(api, payload):
    require_private(api)
    with LOCK, closing(api.connect()) as db, db:
        row = api.run(db, "SELECT tested FROM outlook_account WHERE id=1").fetchone()
        if not row or not row["tested"]:
            raise ValueError("Connect Outlook and send the self-test before queuing lead outreach.")
        item = api.run(db, "SELECT * FROM growth_items WHERE id=?", (payload.get("item_id"),)).fetchone()
        if not item or item["kind"] != "outreach" or item["channel"] != "Email" or item["state"] != "approved" or type(payload.get("revision")) is not int or item["revision"] != payload["revision"]:
            raise ValueError("Review and approve the current email draft before sending.")
        if growth.is_paused(db, api.run, item["service"]):
            raise ValueError("Resume this workspace before queuing email.")
        lead = api.run(db, "SELECT * FROM leads WHERE id=? AND service=?", (item["lead_id"], item["service"])).fetchone()
        if not lead or lead["review_decision"] != "active" or lead["status"] == "not_interested":
            raise ValueError("This lead is inactive or not interested.")
        recipient = str(lead["email"] or "").strip()
        if not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", recipient) or payload.get("recipient") != recipient:
            raise ValueError("Confirm the lead's current business email address.")
        if payload.get("permission_confirmed") is not True:
            raise ValueError("Confirm permission to contact this recipient.")
        zone = payload.get("timezone", "")
        try:
            ZoneInfo(zone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            raise ValueError("Enter a valid recipient timezone, such as Asia/Riyadh.") from None
        api.run(db, "DELETE FROM outlook_queue WHERE item_id=? AND state='cancelled'", (item["id"],))
        if api.run(db, "SELECT id FROM outlook_queue WHERE item_id=?", (item["id"],)).fetchone():
            raise ValueError("This draft already has a delivery record. Do not queue it twice.")
        job_id = secrets.token_urlsafe(18)
        api.run(db, """INSERT INTO outlook_queue (id, item_id, revision, service, recipient, subject, body, timezone, state, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?)""", (job_id, item["id"], item["revision"], item["service"], recipient, item["title"], item["body"], zone, api.now()))
        growth.event(db, api.run, item["service"], item["id"], item["lead_id"], "email_queued", {"recipient": recipient, "timezone": zone, "revision": item["revision"], "permission_confirmed": True})
    return {"message": "Queued for 09:00–17:00 weekdays in the recipient's timezone. Pause controls apply."}


def send(token, recipient, subject, body):
    code, _ = http("https://graph.microsoft.com/v1.0/me/sendMail", token=token, data={"message": {
        "subject": subject, "body": {"contentType": "Text", "content": body},
        "toRecipients": [{"emailAddress": {"address": recipient}}]}, "saveToSentItems": True})
    if code != 202:
        raise RuntimeError("Microsoft did not acknowledge the send. Check Sent Items before retrying.")


def test_email(api):
    require_private(api)
    token = access_token(api)
    job_id = secrets.token_urlsafe(18)
    with LOCK, closing(api.connect()) as db, db:
        if growth.is_paused(db, api.run, "global"):
            raise ValueError("Clear the global pause before sending the self-test.")
        count = api.run(db, "SELECT COUNT(*) AS n FROM outlook_queue WHERE service='test' AND attempted_at>=?", (datetime.now(timezone.utc).date().isoformat(),)).fetchone()["n"]
        if count >= 3:
            raise ValueError("Three test attempts have been used today. Check your mailbox before trying tomorrow.")
        api.run(db, "INSERT INTO outlook_queue (id, service, recipient, subject, body, timezone, state, attempted_at, created_at) VALUES (?, 'test', ?, 'Outlook connection test', '', 'UTC', 'sending', ?, ?)",
                (job_id, SENDER, api.now(), api.now()))
    try:
        send(token, SENDER, "Voxel1 Growth Engine — Outlook connection test", "This test confirms that Growth Engine can submit email through your connected Outlook mailbox. No lead outreach has been sent by this test.")
    except Exception:
        with closing(api.connect()) as db, db:
            api.run(db, "UPDATE outlook_queue SET state='uncertain', result='Self-test outcome unknown. Check Inbox and Sent Items.' WHERE id=?", (job_id,))
        raise ValueError("Self-test outcome unknown. Check Inbox and Sent Items before trying again.") from None
    with closing(api.connect()) as db, db:
        api.run(db, "UPDATE outlook_account SET tested=1 WHERE id=1")
        api.run(db, "UPDATE outlook_queue SET state='accepted', result='Microsoft accepted self-test; check Inbox and Sent Items.' WHERE id=?", (job_id,))
    return {"message": "Microsoft accepted the test email to " + SENDER + ". Check Inbox and Sent Items; acceptance is not proof of delivery."}


def recover(api):
    with closing(api.connect()) as db, db:
        api.run(db, "UPDATE outlook_queue SET state='uncertain', result='Server restarted during submission. Check Sent Items; this email will not be retried automatically.' WHERE state='sending'")


def tick(api, instant=None):
    require_private(api)
    instant = instant or datetime.now(timezone.utc)
    with closing(api.connect()) as db:
        account = api.run(db, "SELECT tested FROM outlook_account WHERE id=1").fetchone()
        if not account or not account["tested"]:
            return
        jobs = [dict(r) for r in api.run(db, "SELECT * FROM outlook_queue WHERE state='queued' ORDER BY created_at")]
    for job in jobs:
        local = instant.astimezone(ZoneInfo(job["timezone"]))
        if local.weekday() >= 5 or not 9 <= local.hour < 17:
            continue
        try:
            token = access_token(api)
        except (ValueError, RuntimeError):
            with closing(api.connect()) as db, db:
                api.run(db, "UPDATE outlook_queue SET result='Outlook authorization needs attention. Reconnect and test the mailbox.' WHERE state='queued'")
            return
        with LOCK, closing(api.connect()) as db, db:
            if growth.is_paused(db, api.run, job["service"]):
                continue
            item = api.run(db, "SELECT * FROM growth_items WHERE id=?", (job["item_id"],)).fetchone()
            lead = api.run(db, "SELECT * FROM leads WHERE id=?", (item["lead_id"] if item else -1,)).fetchone()
            if not item or item["state"] != "approved" or item["revision"] != job["revision"] or not lead or lead["email"] != job["recipient"] or lead["review_decision"] != "active" or lead["status"] == "not_interested":
                api.run(db, "UPDATE outlook_queue SET state='cancelled', result='Draft or lead changed; review and queue again.' WHERE id=? AND state='queued'", (job["id"],))
                continue
            # UTC-day cap includes uncertain attempts; never reset on a restart.
            day = instant.astimezone(timezone.utc).date().isoformat()
            count = api.run(db, "SELECT COUNT(*) AS n FROM outlook_queue WHERE service=? AND attempted_at>=?", (job["service"], day)).fetchone()["n"]
            if count >= 5:
                continue
            claimed = api.run(db, "UPDATE outlook_queue SET state='sending', attempted_at=? WHERE id=? AND state='queued' RETURNING id", (instant.isoformat(), job["id"])).fetchone()
            if not claimed:
                continue
        try:
            send(token, job["recipient"], job["subject"], job["body"])
        except Exception:
            with closing(api.connect()) as db, db:
                api.run(db, "UPDATE outlook_queue SET state='uncertain', result='Submission failed or outcome unknown. Check Sent Items; no automatic retry.' WHERE id=?", (job["id"],))
            continue
        with closing(api.connect()) as db, db:
            api.run(db, "UPDATE outlook_queue SET state='accepted', result='Microsoft accepted submission; delivery is not confirmed.' WHERE id=?", (job["id"],))
            api.run(db, "UPDATE growth_items SET state='done', revision=revision+1, updated_at=? WHERE id=? AND revision=?", (api.now(), job["item_id"], job["revision"]))
            growth.event(db, api.run, job["service"], job["item_id"], item["lead_id"], "outlook_accepted", {"recipient": job["recipient"], "revision": job["revision"]})
