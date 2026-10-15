"""Persistent internal Growth Engine workspace for the Training and BIM Services pipelines.

Everything here is internal record-keeping. Approving a draft never sends, posts or
schedules anything: no mailbox, social account or calendar is connected.
"""
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urlparse

SERVICES = ("training", "bim")
RHYTHMS = json.loads(Path(__file__).with_name("rhythms.json").read_text(encoding="utf-8"))
IST = timezone(timedelta(hours=5, minutes=30))
STAGES = ("new", "engaged", "meeting", "proposal", "negotiation", "won", "lost")
CHANNELS = ("Internal", "Email", "LinkedIn", "Instagram", "Facebook", "YouTube", "WhatsApp", "Phone", "Website", "Event")
# Tasks carry an activity type; content and outreach drafts carry a purpose.
LABELS = {
    "task": ("Marketing", "BD", "Outreach", "Sales", "Account", "Content"),
    "content": ("Proof", "Authority", "Education", "Lead gen", "Nurture", "Partner"),
    "outreach": ("First contact", "Follow-up", "Proposal", "Partner", "Account"),
    "room": ("Outline",),
    "brief": ("Research", "Mapping", "Daily summary", "Call preparation"),
}
ACTIONS = {"approve": "approved", "reject": "rejected", "complete": "done", "reopen": "pending"}


class Conflict(ValueError):
    """Raised when an item changed since the browser loaded it."""


def stamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def init(db, run, identity):
    run(db, """CREATE TABLE IF NOT EXISTS growth_rhythm_settings (
        service TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0)""")
    run(db, """CREATE TABLE IF NOT EXISTS growth_rhythm_runs (
        service TEXT NOT NULL, day TEXT NOT NULL, slot INTEGER NOT NULL,
        PRIMARY KEY (service, day, slot))""")
    for service in SERVICES:
        run(db, "INSERT INTO growth_rhythm_settings (service) VALUES (?) ON CONFLICT(service) DO NOTHING", (service,))
    run(db, """CREATE TABLE IF NOT EXISTS growth_settings (
        service TEXT PRIMARY KEY, paused INTEGER NOT NULL DEFAULT 0,
        goal INTEGER NOT NULL DEFAULT 0, strategy TEXT NOT NULL DEFAULT '')""")
    for service, strategy in (("bim", "Find project teams that need BIM delivery support, and win repeat work from each client."),
                              ("training", "Find architecture, engineering and construction teams that need their staff trained in BIM."),
                              ("global", "")):
        run(db, "INSERT INTO growth_settings (service, strategy) VALUES (?, ?) ON CONFLICT(service) DO NOTHING", (service, strategy))
    run(db, f"""CREATE TABLE IF NOT EXISTS growth_items (
        id {identity} PRIMARY KEY, service TEXT NOT NULL, kind TEXT NOT NULL,
        lead_id BIGINT, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '',
        owner TEXT NOT NULL DEFAULT '', channel TEXT NOT NULL DEFAULT 'Internal',
        label TEXT NOT NULL DEFAULT '', due TEXT NOT NULL DEFAULT '', due_time TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL DEFAULT 'pending', revision INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    run(db, """CREATE TABLE IF NOT EXISTS growth_leads (
        lead_id BIGINT PRIMARY KEY, service TEXT NOT NULL, stage TEXT NOT NULL DEFAULT 'new',
        owner TEXT NOT NULL DEFAULT '', room_notes TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL)""")
    run(db, f"""CREATE TABLE IF NOT EXISTS growth_events (
        id {identity} PRIMARY KEY, service TEXT NOT NULL, item_id BIGINT,
        lead_id BIGINT, event TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL)""")


def snapshot(db, run):
    import automation
    return {"sales_progress": automation.progress(db, run),
            "campaigns": [{"service": r["service"], **json.loads(r["config"])} for r in run(db, "SELECT * FROM agent_campaigns")],
            "jobs": [dict(r) for r in run(db, "SELECT * FROM agent_jobs ORDER BY day DESC, updated_at DESC LIMIT 250")],
            "rhythm_templates": RHYTHMS,
            "rhythm_settings": [dict(r) for r in run(db, "SELECT * FROM growth_rhythm_settings")],
            "settings": [dict(r) for r in run(db, "SELECT * FROM growth_settings")],
            "items": [dict(r) for r in run(db, "SELECT * FROM growth_items ORDER BY id DESC")],
            "lead_details": [dict(r) for r in run(db, "SELECT * FROM growth_leads")],
            "connections": {"email": False, "social": False, "calendar": False},
            "choices": {"stages": STAGES, "channels": CHANNELS, "labels": LABELS}}


def lead_history(db, run, service, lead_id):
    rows = run(db, "SELECT event, detail, created_at FROM growth_events WHERE service=? AND lead_id=? ORDER BY id DESC", (service, lead_id))
    return [{"event": r["event"], "detail": json.loads(r["detail"]), "created_at": r["created_at"]} for r in rows]


def is_paused(db, run, service):
    return any(r["paused"] for r in run(db, "SELECT paused FROM growth_settings WHERE service IN (?, 'global')", (service,)))


def text(payload, key, limit, required=False):
    value = payload.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f"Enter a valid {key.replace('_', ' ')} (up to {limit} characters).")
    return value.strip()


def event(db, run, service, item_id, lead_id, name, detail):
    run(db, "INSERT INTO growth_events (service, item_id, lead_id, event, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (service, item_id, lead_id, name, json.dumps(detail), stamp()))


def add_company(db, run, payload, log_lead_event):
    service = payload.get("service")
    if service not in SERVICES:
        raise ValueError("Choose Training or BIM Services.")
    company = text(payload, "company", 200, True)
    website = text(payload, "website", 500)
    if website and (urlparse(website).scheme not in ("http", "https") or not urlparse(website).hostname):
        raise ValueError("Website must start with http:// or https://.")
    email = text(payload, "email", 254)
    if email and ("@" not in email or any(c.isspace() for c in email)):
        raise ValueError("Enter a valid business email.")
    values = (service, "manual/" + uuid.uuid4().hex, company, text(payload, "category", 100) or "business",
              text(payload, "city", 100), text(payload, "country", 100), email or None,
              text(payload, "phone", 100) or None, website or None, website,
              text(payload, "contact_name", 200), text(payload, "contact_title", 200),
              "Added manually by your team; not checked by a search provider.", stamp(), stamp())
    row = run(db, """INSERT INTO leads (service, source_id, company, category, city, country, email, phone,
        website, source_url, contact_name, contact_title, match_reason, discovered_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""", values).fetchone()
    log_lead_event(db, row["id"], service, "discovered", {"source": "Manually entered", "match_reason": values[12]})
    return dict(run(db, "SELECT * FROM leads WHERE id=?", (row["id"],)).fetchone())


def save_settings(db, run, service, payload):
    if service not in SERVICES + ("global",):
        raise ValueError("Unknown workspace.")
    row = dict(run(db, "SELECT * FROM growth_settings WHERE service=?", (service,)).fetchone())
    if "paused" in payload:
        if type(payload["paused"]) is not bool:
            raise ValueError("Paused must be true or false.")
        row["paused"] = int(payload["paused"])
    if "goal" in payload:
        if type(payload["goal"]) is not int or not 0 <= payload["goal"] <= 10000:
            raise ValueError("The sales goal must be a whole number from 0 to 10000.")
        row["goal"] = payload["goal"]
    if "strategy" in payload:
        row["strategy"] = text(payload, "strategy", 1000)
    run(db, "UPDATE growth_settings SET paused=?, goal=?, strategy=? WHERE service=?",
        (row["paused"], row["goal"], row["strategy"], service))
    event(db, run, service, None, None, "settings_updated", {key: row[key] for key in ("paused", "goal", "strategy")})
    return row


def save_lead(db, run, lead_id, payload):
    service = payload.get("service")
    lead = run(db, "SELECT id FROM leads WHERE id=? AND service=?", (lead_id, service)).fetchone()
    if not lead:
        raise ValueError("Lead not found in this service.")
    stage = payload.get("stage")
    if stage not in STAGES:
        raise ValueError("Choose a valid sales stage.")
    owner, notes = text(payload, "owner", 120), text(payload, "room_notes", 10000)
    before = run(db, "SELECT stage, owner FROM growth_leads WHERE lead_id=?", (lead_id,)).fetchone()
    run(db, """INSERT INTO growth_leads (lead_id, service, stage, owner, room_notes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(lead_id) DO UPDATE SET
        stage=excluded.stage, owner=excluded.owner, room_notes=excluded.room_notes, updated_at=excluded.updated_at""",
        (lead_id, service, stage, owner, notes, datetime.now(timezone.utc).isoformat(timespec="microseconds")))
    event(db, run, service, None, lead_id, "lead_room_updated",
          {"from_stage": before["stage"] if before else "new", "stage": stage, "owner": owner})
    return dict(run(db, "SELECT * FROM growth_leads WHERE lead_id=?", (lead_id,)).fetchone())


def item_fields(db, run, service, kind, payload):
    title, body, owner = text(payload, "title", 200, True), text(payload, "body", 10000), text(payload, "owner", 120)
    channel = payload.get("channel") or "Internal"
    if channel not in CHANNELS:
        raise ValueError("Choose a listed channel.")
    label = payload.get("label") or ""
    if label and label not in LABELS[kind]:
        raise ValueError("Choose a listed type.")
    due, due_time = text(payload, "due", 10), text(payload, "due_time", 5)
    if due:
        try:
            datetime.strptime(due, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Use a valid date.") from None
    if due_time:
        try:
            datetime.strptime(due_time, "%H:%M")
        except ValueError:
            raise ValueError("Use a valid time (HH:MM).") from None
    lead_id = payload.get("lead_id") or None
    if lead_id is not None:
        if type(lead_id) is not int or not run(db, "SELECT id FROM leads WHERE id=? AND service=?", (lead_id, service)).fetchone():
            raise ValueError("Choose a lead belonging to this service.")
    return {"title": title, "body": body, "owner": owner, "channel": channel, "label": label,
            "due": due, "due_time": due_time, "lead_id": lead_id}


def save_item(db, run, item_id, payload):
    """Create (item_id None), edit or act on a task / content draft / outreach draft."""
    current = None
    if item_id is not None:
        current = run(db, "SELECT * FROM growth_items WHERE id=?", (item_id,)).fetchone()
        if not current:
            raise ValueError("Item not found.")
        current = dict(current)
        if type(payload.get("revision")) is not int or payload["revision"] != current["revision"]:
            raise Conflict("This item changed since you opened it. It has been reloaded; check it and try again.")
    service = current["service"] if current else payload.get("service")
    if service not in SERVICES:
        raise ValueError("Choose Training or BIM Services.")
    if current and "action" in payload:
        action = payload["action"]
        if action not in ACTIONS:
            raise ValueError("Unknown action.")
        kind, state = current["kind"], current["state"]
        if kind == "room" and action == "complete":
            raise ValueError("Use Apply to room to apply an approved room draft.")
        if action == "approve" and (kind == "task" or not current["body"].strip()):
            raise ValueError("Only a content or outreach draft with text can be approved.")
        if action == "complete" and kind != "task" and state != "approved":
            raise ValueError("Approve the draft before recording it as posted or sent.")
        if action in ("approve", "complete") and is_paused(db, run, service):
            raise ValueError("This workspace is paused. Resume it before approving or completing work.")
        if action == "reopen" and state == "pending":
            raise ValueError("This item is already open.")
        if action in ("approve", "reject") and state != "pending":
            raise ValueError("Reopen the item before changing its decision.")
        if action == "complete" and state not in ("pending", "approved"):
            raise ValueError("Reopen the item first.")
        changed = run(db, "UPDATE growth_items SET state=?, revision=revision+1, updated_at=? WHERE id=? AND revision=?",
                      (ACTIONS[action], stamp(), current["id"], current["revision"]))
        if changed.rowcount != 1:
            raise Conflict("This item changed since you opened it. Reload and try again.")
        event(db, run, service, current["id"], current["lead_id"], action, {"title": current["title"], "kind": kind})
        return dict(run(db, "SELECT * FROM growth_items WHERE id=?", (current["id"],)).fetchone())
    kind = current["kind"] if current else payload.get("kind")
    if kind not in LABELS:
        raise ValueError("Choose a task, content draft or outreach draft.")
    fields = item_fields(db, run, service, kind, payload)
    if kind == "room" and (not fields["lead_id"] or fields["channel"] != "Internal"):
        raise ValueError("Room drafts must be internal and linked to a lead.")
    if kind == "brief" and fields["channel"] != "Internal":
        raise ValueError("Internal review briefs cannot be assigned to an external channel.")
    if current is None:
        row = run(db, """INSERT INTO growth_items (service, kind, lead_id, title, body, owner, channel, label, due, due_time, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id""",
            (service, kind, fields["lead_id"], fields["title"], fields["body"], fields["owner"], fields["channel"],
             fields["label"], fields["due"], fields["due_time"], stamp(), stamp())).fetchone()
        item_id = row["id"]
    else:
        # Any edit returns the item to pending, so an earlier approval never covers changed text.
        changed = run(db, """UPDATE growth_items SET title=?, body=?, owner=?, channel=?, label=?, due=?, due_time=?, lead_id=?,
            state='pending', revision=revision+1, updated_at=? WHERE id=? AND revision=?""",
            (fields["title"], fields["body"], fields["owner"], fields["channel"], fields["label"], fields["due"],
             fields["due_time"], fields["lead_id"], stamp(), item_id, current["revision"]))
        if changed.rowcount != 1:
            raise Conflict("This item changed since you opened it. Reload and try again.")
    event(db, run, service, item_id, fields["lead_id"], "created" if current is None else "edited", {"title": fields["title"], "kind": kind})
    return dict(run(db, "SELECT * FROM growth_items WHERE id=?", (item_id,)).fetchone())


def generate_rhythm(db, run, service, instant=None):
    """Claim each template slot transactionally; never execute its business activity."""
    if service not in SERVICES:
        raise ValueError("Unknown service.")
    if is_paused(db, run, service):
        return {"created": 0}
    day = (instant or datetime.now(timezone.utc)).astimezone(IST).date().isoformat()
    created = 0
    for slot, (time, label, title, purpose) in enumerate(RHYTHMS[service]):
        claim = run(db, """INSERT INTO growth_rhythm_runs (service, day, slot)
            VALUES (?, ?, ?) ON CONFLICT(service, day, slot) DO NOTHING RETURNING slot""", (service, day, slot)).fetchone()
        if not claim:
            continue
        # Reuse tasks added through the earlier manual routine UI.
        if run(db, "SELECT id FROM growth_items WHERE service=? AND kind='task' AND due=? AND title=?", (service, day, title)).fetchone():
            continue
        save_item(db, run, None, {"service": service, "kind": "task", "title": title,
            "label": label, "due": day, "due_time": time, "owner": "You", "channel": "Internal",
            "body": f"{purpose}\n\nReference schedule: {time} IST (Asia/Kolkata). Execute manually; outbound drafts require approval."})
        created += 1
    return {"created": created}


def tick_rhythms(db, run, instant=None):
    instant = instant or datetime.now(timezone.utc)
    local = instant.astimezone(IST)
    if local.weekday() >= 5 or local.hour < 6:
        return
    for row in run(db, "SELECT service FROM growth_rhythm_settings WHERE enabled=1").fetchall():
        generate_rhythm(db, run, row["service"], instant)


def mutate(db, run, method, parts, payload, log_lead_event):
    """Writes below /api/growth; callers enforce session and same-origin checks."""
    if len(parts) == 2 and parts[0] == "rhythm" and parts[1] in SERVICES:
        if method == "POST":
            return generate_rhythm(db, run, parts[1])
        if method == "PUT":
            if type(payload.get("enabled")) is not bool:
                raise ValueError("Enabled must be true or false.")
            run(db, "UPDATE growth_rhythm_settings SET enabled=? WHERE service=?", (int(payload["enabled"]), parts[1]))
            event(db, run, parts[1], None, None, "daily_planning_changed", {"enabled": payload["enabled"]})
            tick_rhythms(db, run)
            return {"enabled": payload["enabled"]}
    if parts == ["companies"] and method == "POST":
        return add_company(db, run, payload, log_lead_event)
    if len(parts) == 2 and parts[0] == "settings" and method == "PUT":
        return save_settings(db, run, parts[1], payload)
    if len(parts) == 2 and parts[0] == "leads" and method == "PUT" and parts[1].isdigit():
        return save_lead(db, run, int(parts[1]), payload)
    if parts == ["items"] and method == "POST":
        return save_item(db, run, None, payload)
    if len(parts) == 2 and parts[0] == "items" and method == "PATCH" and parts[1].isdigit():
        return save_item(db, run, int(parts[1]), payload)
    raise LookupError("Unknown workspace action.")
