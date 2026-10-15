"""Persistent, bounded discovery-to-draft jobs. No external delivery."""
import json
from contextlib import closing
from datetime import datetime, timezone

import growth
import provider_search


def init(db, run):
    run(db, """CREATE TABLE IF NOT EXISTS agent_campaigns (
        service TEXT PRIMARY KEY, config TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    run(db, """CREATE TABLE IF NOT EXISTS agent_jobs (
        service TEXT NOT NULL, day TEXT NOT NULL, job TEXT NOT NULL,
        state TEXT NOT NULL, result TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL, PRIMARY KEY(service, day, job))""")


def save(api, db, service, payload):
    if service not in growth.SERVICES:
        raise ValueError("Unknown service.")
    profile = api.validate_icp(payload.get("targeting", {}))
    objective = growth.text(payload, "objective", 500, True)
    start, end = growth.text(payload, "start", 10, True), growth.text(payload, "end", 10)
    for date in (start, end):
        if date:
            datetime.strptime(date, "%Y-%m-%d")
    if end and end < start:
        raise ValueError("End date must be on or after the start date.")
    for field in ("search_time", "draft_time"):
        value = growth.text(payload, field, 5, True)
        if datetime.strptime(value, "%H:%M").strftime("%H:%M") != value:
            raise ValueError("Use a time in HH:MM format.")
    if payload["draft_time"] < payload["search_time"]:
        raise ValueError("Draft time must be after discovery time.")
    if payload.get("accept_budget") is not True:
        raise ValueError("Confirm that scheduled provider requests use the configured monthly budget.")
    config = {"objective": objective, "start": start, "end": end,
              "search_time": payload["search_time"], "draft_time": payload["draft_time"],
              "targeting": profile}
    api.run(db, """INSERT INTO agent_campaigns (service, config, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(service) DO UPDATE SET config=excluded.config, updated_at=excluded.updated_at""",
        (service, json.dumps(config), api.now()))
    growth.event(db, api.run, service, None, None, "campaign_saved", config)
    return config


def active(api, service):
    with closing(api.connect()) as db:
        if growth.is_paused(db, api.run, service):
            raise ValueError("Paused. No further provider requests will start.")


def claim(api, service, day, job):
    with closing(api.connect()) as db, db:
        if growth.is_paused(db, api.run, service):
            return False
        return bool(api.run(db, """INSERT INTO agent_jobs (service, day, job, state, updated_at)
            VALUES (?, ?, ?, 'running', ?) ON CONFLICT(service, day, job) DO NOTHING RETURNING job""",
            (service, day, job, api.now())).fetchone())


def finish(api, service, day, job, state, result):
    with closing(api.connect()) as db, db:
        api.run(db, "UPDATE agent_jobs SET state=?, result=?, updated_at=? WHERE service=? AND day=? AND job=?",
                (state, json.dumps(result), api.now(), service, day, job))


def recover(api):
    """A crashed paid request has an unknown outcome; never replay it blindly."""
    with closing(api.connect()) as db, db:
        api.run(db, "UPDATE agent_jobs SET state='interrupted', result=? WHERE state='running'",
                (json.dumps({"message": "Server restarted during this job. Review results; it was not repeated to avoid duplicate charges or drafts."}),))


def discovery(api, service, config):
    import os
    if not all(os.environ.get(k) for k in ("APOLLO_API_KEY", "BRAVE_SEARCH_API_KEY", "GEMINI_API_KEY")):
        raise ValueError("Scheduled discovery requires Apollo, Brave, and Gemini keys for buyer screening.")
    if api.PUBLIC_NO_AUTH:
        raise ValueError("Scheduled paid workflows require private access; disable public demo mode.")
    if not api.search_lock.acquire(blocking=False):
        raise ValueError("Another search is running. This scheduled attempt did not use provider credits.")
    try:
        active(api, service)
        run_id, allowance = api.reserve_search(service)

        class GuardedMeter(provider_search.Meter):
            def charge(self, provider, operation):
                active(api, service)
                super().charge(provider, operation)

        meter = GuardedMeter(allowance)
        try:
            with closing(api.connect()) as db:
                skip = {r["source_id"].split("/", 1)[1] for r in api.run(db,
                    "SELECT source_id FROM leads WHERE service=? AND review_decision<>'active'", (service,))
                    if r["source_id"].startswith("apollo/")}
            result = provider_search.discover(config["targeting"], service, meter, skip)
            saved = api.persist_discovery(service, result)
        except Exception:
            api.finish_search(run_id, meter, "Scheduled discovery stopped or failed. Review the job status.")
            raise
        api.finish_search(run_id, meter)
        return saved
    finally:
        api.search_lock.release()


def tick(api, instant=None):
    local = (instant or datetime.now(timezone.utc)).astimezone(growth.IST)
    day, clock = local.date().isoformat(), local.strftime("%H:%M")
    with closing(api.connect()) as db:
        campaigns = [dict(r) for r in api.run(db, "SELECT * FROM agent_campaigns")]
    for row in campaigns:
        service, config = row["service"], json.loads(row["config"])
        if day < config["start"] or (config["end"] and day > config["end"]):
            continue
        if clock >= config["search_time"] and claim(api, service, day, "discovery"):
            try:
                finish(api, service, day, "discovery", "done", discovery(api, service, config))
            except Exception as exc:
                finish(api, service, day, "discovery", "needs_you", {"message": safe_error(api, exc)})
        if clock < config["draft_time"]:
            continue
        with closing(api.connect()) as db:
            search = api.run(db, "SELECT * FROM agent_jobs WHERE service=? AND day=? AND job='discovery'", (service, day)).fetchone()
        if not search or search["state"] != "done":
            continue
        ids = json.loads(search["result"]).get("lead_ids", [])
        with closing(api.connect()) as db:
            eligible = []
            for lead_id in ids:
                lead = api.run(db, "SELECT id FROM leads WHERE id=? AND service=? AND ai_screened=1 AND review_decision='active' AND status<>'not_interested'", (lead_id, service)).fetchone()
                prior = api.run(db, "SELECT id FROM growth_items WHERE lead_id=? AND kind='outreach'", (lead_id,)).fetchone()
                if lead and not prior:
                    eligible.append(lead_id)
        # All attempted drafts count toward the daily limit, including failures.
        with closing(api.connect()) as db:
            attempted = api.run(db, "SELECT COUNT(*) AS n FROM agent_jobs WHERE service=? AND day=? AND job LIKE 'draft:%'", (service, day)).fetchone()["n"]
        for lead_id in eligible[:max(0, 5 - attempted)]:
            job = f"draft:{lead_id}"
            if not claim(api, service, day, job):
                continue
            try:
                active(api, service)
                item = api.ai_draft_lead(service, lead_id, {"purpose": "First contact", "guidance": config["objective"]})
                finish(api, service, day, job, "needs_approval", {"item_id": item["id"], "message": "Draft prepared. Review it in Approvals; nothing was sent."})
            except Exception as exc:
                finish(api, service, day, job, "needs_you", {"message": safe_error(api, exc)})


def safe_error(api, exc):
    if isinstance(exc, (ValueError, api.BudgetBlocked)):
        return str(exc)[:500]
    return "Provider or storage operation failed. No automatic retry today; inspect provider status and saved results."
