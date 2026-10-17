"""Persistent, bounded discovery-to-draft jobs. No external delivery."""
import json
import logging
import re
import sys
import secrets
from contextlib import closing
from datetime import datetime, timezone

import growth
import provider_search
import draft_outputs


def init(db, run):
    run(db, """CREATE TABLE IF NOT EXISTS agent_campaigns (
        service TEXT PRIMARY KEY, config TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    run(db, """CREATE TABLE IF NOT EXISTS agent_jobs (
        service TEXT NOT NULL, day TEXT NOT NULL, job TEXT NOT NULL,
        state TEXT NOT NULL, result TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL, PRIMARY KEY(service, day, job))""")
    import job_recovery
    job_recovery.init(db, run)


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
    # Legacy campaign requests remain valid and preserve unified settings.
    current = api.run(db, "SELECT config FROM agent_campaigns WHERE service=?", (service,)).fetchone()
    previous = json.loads(current["config"]) if current else {}
    for key in ("quarter", "content_targets", "strategy", "auto_rooms", "auto_linkedin", "full_rhythm", "target_accounts", "partner_accounts", "partner_enabled", "existing_clients", "warm_paths", "approved_proof", "proof_consent", "service_focus"):
        if key in previous:
            config[key] = previous[key]
    for key in ("auto_rooms", "auto_linkedin", "full_rhythm", "proof_consent", "partner_enabled"):
        if key in payload:
            if type(payload[key]) is not bool:
                raise ValueError("Draft automation settings must be true or false.")
            config[key] = payload[key]
    for key in ("target_accounts", "partner_accounts", "existing_clients", "warm_paths", "approved_proof"):
        if key in payload:
            config[key] = growth.text(payload, key, 3000)
    if "service_focus" in payload:
        # Required wording for outbound drafts; separate from optional search keywords.
        config["service_focus"] = " ".join(growth.text(payload, "service_focus", 200).split())
    if config.get("full_rhythm"):
        config.update(auto_rooms=True, auto_linkedin=True)
    if "goal" in payload:
        if type(payload["goal"]) is not int or not 0 <= payload["goal"] <= 10000:
            raise ValueError("Sales target must be a whole number from 0 to 10000.")
        quarter = growth.text(payload, "quarter", 7, True)
        if not re.fullmatch(r"[0-9]{4}-Q[1-4]", quarter):
            raise ValueError("Use a quarter such as 2026-Q4.")
        strategy = growth.text(payload, "strategy", 1000)
        targets = payload.get("content_targets", {})
        if not isinstance(targets, dict) or any(k not in ("LinkedIn", "Instagram", "Facebook") for k in targets):
            raise ValueError("Choose LinkedIn, Instagram or Facebook content targets.")
        if any(type(v) is not int or not 0 <= v <= 10 for v in targets.values()):
            raise ValueError("Content targets must be whole numbers from 0 to 10 posts per day.")
        config.update(quarter=quarter, content_targets=targets, strategy=strategy)
        growth.save_settings(db, api.run, service, {"goal": payload["goal"], "strategy": strategy})
        # Manual searches and scheduled searches use the same saved targeting.
        api.run(db, """UPDATE icps SET name=?, country=?, city=?, categories=?, notes=?, profile_json=?, updated_at=? WHERE service=?""",
                (profile["name"], profile["country"], profile["city"], json.dumps(profile["categories"]), profile["notes"],
                 json.dumps({k: profile[k] for k in ("countries", "employee_min", "employee_max", "titles", "keywords", "exclusions", "goal")}), api.now(), service))
    api.run(db, """INSERT INTO agent_campaigns (service, config, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(service) DO UPDATE SET config=excluded.config, updated_at=excluded.updated_at""",
        (service, json.dumps(config), api.now()))
    # Changed inputs can release blocked work today, while successful or unknown
    # paid attempts remain claimed and are never replayed by a settings save.
    day = datetime.now(timezone.utc).astimezone(growth.IST).date().isoformat()
    # A job that already saved outputs (e.g. social drafts or a daily summary that
    # still flags missing proof/research input) is not re-run: that would duplicate them.
    for job in api.run(db, "SELECT job, state, result FROM agent_jobs WHERE service=? AND day=?", (service, day)).fetchall():
        result = json.loads(job["result"] or "{}")
        if result.get("item_ids"):
            continue
        if job["state"] in ("needs_input", "needs_budget") or result.get("budget_blocked"):
            api.run(db, "UPDATE agent_jobs SET state='retry_ready' WHERE service=? AND day=? AND job=?", (service, day, job["job"]))
    growth.event(db, api.run, service, None, None, "campaign_saved", config)
    return config


def progress(db, run):
    """Quarter wins require a recorded transition; editing a room is not a win."""
    result = {}
    for row in run(db, "SELECT service, config FROM agent_campaigns").fetchall():
        service, config = row["service"], json.loads(row["config"])
        quarter = config.get("quarter")
        wins = set()
        if quarter:
            for e in run(db, "SELECT lead_id, detail, created_at FROM growth_events WHERE service=? AND event='lead_room_updated'", (service,)):
                detail = json.loads(e["detail"])
                at = datetime.fromisoformat(e["created_at"]).astimezone(growth.IST)
                if detail.get("stage") == "won" and detail.get("from_stage") != "won" and f"{at.year}-Q{(at.month - 1) // 3 + 1}" == quarter:
                    wins.add(e["lead_id"])
            still_won = {r["lead_id"] for r in run(db, "SELECT lead_id FROM growth_leads WHERE service=? AND stage='won'", (service,))}
            wins &= still_won
        result[service] = {"quarter": quarter, "quarter_won": len(wins)}
    return result


def active(api, service):
    with closing(api.connect()) as db:
        if growth.is_paused(db, api.run, service):
            raise ValueError("Paused. No further provider requests will start.")


def claim(api, service, day, job):
    with closing(api.connect()) as db, db:
        import job_recovery
        try:
            _, _, _, pattern = job_recovery.specification(job)
        except ValueError:
            pattern = None
        if pattern:
            if api.DATABASE_URL:
                api.run(db, f"SELECT pg_advisory_xact_lock({api.BUDGET_LOCK_ID})")
            else:
                db.execute("BEGIN IMMEDIATE")
            original = api.run(db, "SELECT COUNT(*) AS n FROM agent_jobs WHERE service=? AND day=? AND job LIKE ? AND state<>'retry_ready'", (service, day, pattern)).fetchone()["n"]
            retried = api.run(db, "SELECT COUNT(*) AS n FROM agent_retry_attempts WHERE service=? AND day=? AND job LIKE ?", (service, day, pattern)).fetchone()["n"]
            if original + retried >= 5:
                return False
        if growth.is_paused(db, api.run, service):
            return False
        return bool(api.run(db, """INSERT INTO agent_jobs (service, day, job, state, updated_at)
            VALUES (?, ?, ?, 'running', ?) ON CONFLICT(service, day, job) DO UPDATE
            SET state='running', result='', updated_at=excluded.updated_at WHERE agent_jobs.state='retry_ready' RETURNING job""",
            (service, day, job, api.now())).fetchone())


def finish(api, service, day, job, state, result):
    failure = sys.exc_info()[1]
    if failure is not None and state in ("needs_you", "needs_budget"):
        result = dict(result)
        if isinstance(failure, provider_search.DraftGenerationError):
            result.update(message=str(failure), retry_safe=True, failure_code="draft_generation", failure_token=secrets.token_hex(16))
        elif isinstance(failure, api.BudgetBlocked):
            result.update(message=str(failure), budget_blocked=True)
        else:
            result.update(retry_safe=False, failure_code="unconfirmed_outcome")
    if state == "needs_you" and failure is not None:
        # Called from an except block: keep the traceback that the stored message hides.
        logging.error("Job %s for %s on %s failed: %s", job, service, day, result.get("message", ""), exc_info=failure)
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


def _discover_due(api, instant=None):
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
                finish(api, service, day, "discovery", "needs_you", {"message": safe_error(api, exc), "budget_blocked": isinstance(exc, api.BudgetBlocked)})


def _tick_core(api, instant=None):
    local = (instant or datetime.now(timezone.utc)).astimezone(growth.IST)
    day, clock = local.date().isoformat(), local.strftime("%H:%M")
    with closing(api.connect()) as db:
        campaigns = [dict(r) for r in api.run(db, "SELECT * FROM agent_campaigns")]
    for row in campaigns:
        service, config = row["service"], json.loads(row["config"])
        if day < config["start"] or (config["end"] and day > config["end"]):
            continue
        if clock >= "06:00":
            with closing(api.connect()) as db, db:
                if not growth.is_paused(db, api.run, service):
                    for channel, count in config.get("content_targets", {}).items():
                        if config.get("full_rhythm"):
                            continue
                        if channel == "LinkedIn" and config.get("auto_linkedin"):
                            continue
                        for index in range(count):
                            job = f"content:{channel}:{index + 1}"
                            claimed = api.run(db, """INSERT INTO agent_jobs (service, day, job, state, updated_at)
                                VALUES (?, ?, ?, 'planned', ?) ON CONFLICT(service, day, job) DO NOTHING RETURNING job""",
                                (service, day, job, api.now())).fetchone()
                            if claimed:
                                item = growth.save_item(db, api.run, None, {"service": service, "kind": "task",
                                    "title": f"Prepare {channel} post {index + 1} for review", "label": "Content",
                                    "due": day, "due_time": "16:00", "channel": channel, "owner": "You",
                                    "body": f"Goal: {config['objective']}\nStrategy: {config.get('strategy', '')}\nCreate a content draft for approval. Publication is not connected."})
                                api.run(db, "UPDATE agent_jobs SET result=? WHERE service=? AND day=? AND job=?",
                                        (json.dumps({"message": "Content preparation task created; draft and publish manually.", "task_id": item["id"]}), service, day, job))
        # Public post drafts do not depend on finding a new lead today.
        if config.get("auto_linkedin") and not config.get("full_rhythm") and clock >= "12:00":
            for slot in range(1, config.get("content_targets", {}).get("LinkedIn", 0) + 1):
                job = f"linkedin:{slot}"
                if claim(api, service, day, job):
                    try:
                        item = draft_outputs.create(api, service, "linkedin", slot=slot, day=day)
                        finish(api, service, day, job, "needs_approval", {"item_id": item["id"], "message": "LinkedIn text drafted. Review in Content or Approvals; not published."})
                    except Exception as exc:
                        finish(api, service, day, job, "needs_you", {"message": safe_error(api, exc), "budget_blocked": isinstance(exc, api.BudgetBlocked)})
        if config.get("auto_rooms") and clock >= "07:30":
            candidates = draft_outputs.room_candidates(api, service, day)
            with closing(api.connect()) as db:
                attempts = api.run(db, "SELECT COUNT(*) AS n FROM agent_jobs WHERE service=? AND day=? AND job LIKE ? AND state<>'retry_ready'", (service, day, "room:%")).fetchone()["n"]
            for lead in candidates[:max(0, 5 - attempts)]:
                job = f"room:{lead['id']}:{lead['context_digest'][:12]}"
                if claim(api, service, day, job):
                    try:
                        item = draft_outputs.create(api, service, "room", lead_id=lead["id"], day=day)
                        finish(api, service, day, job, "needs_approval", {"item_id": item["id"], "message": "Internal room draft prepared. Review and approve before applying; existing outline unchanged."})
                    except Exception as exc:
                        finish(api, service, day, job, "needs_you", {"message": safe_error(api, exc), "budget_blocked": isinstance(exc, api.BudgetBlocked)})
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
                prior = api.run(db, "SELECT id FROM growth_items WHERE lead_id=? AND kind='outreach' AND channel='Email' AND label='First contact'", (lead_id,)).fetchone()
                if lead and not prior:
                    eligible.append(lead_id)
        # All attempted drafts count toward the daily limit, including failures.
        with closing(api.connect()) as db:
            attempted = api.run(db, "SELECT COUNT(*) AS n FROM agent_jobs WHERE service=? AND day=? AND job LIKE ? AND state<>'retry_ready'", (service, day, "draft:%")).fetchone()["n"]
        for lead_id in eligible[:max(0, 5 - attempted)]:
            job = f"draft:{lead_id}"
            if not claim(api, service, day, job):
                continue
            try:
                active(api, service)
                guidance = (config["objective"] + "\nStrategy: " + config.get("strategy", ""))[:500]
                item = api.ai_draft_lead(service, lead_id, {"purpose": "First contact", "guidance": guidance})
                finish(api, service, day, job, "needs_approval", {"item_id": item["id"], "message": "Draft prepared. Review it in Approvals; nothing was sent."})
            except Exception as exc:
                finish(api, service, day, job, "needs_you", {"message": safe_error(api, exc), "budget_blocked": isinstance(exc, api.BudgetBlocked)})


def safe_error(api, exc):
    if isinstance(exc, (ValueError, api.BudgetBlocked, provider_search.DraftGenerationError)):
        return str(exc)[:500]
    return "Provider or storage operation failed. No automatic retry today; inspect provider status and saved results."


def tick(api, instant=None):
    import rhythm_engine
    # Preserve the original lead-discovery budget priority; research then enriches
    # the context available to room and message preparation.
    _discover_due(api, instant)
    rhythm_engine.tick(api, instant, phase="research")
    try:
        _tick_core(api, instant)
    finally:
        rhythm_engine.tick(api, instant, phase="drafts")
