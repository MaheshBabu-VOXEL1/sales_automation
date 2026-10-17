"""Explicit, audited recovery of failed generation, never of an uncertain saved output."""
import json
import re
from contextlib import closing
from datetime import datetime, timezone

import growth
import provider_search
import draft_outputs


def init(db, run):
    run(db, """CREATE TABLE IF NOT EXISTS agent_retry_attempts (
        service TEXT NOT NULL, day TEXT NOT NULL, job TEXT NOT NULL, attempt INTEGER NOT NULL,
        started_at TEXT NOT NULL, finished_at TEXT NOT NULL DEFAULT '', state TEXT NOT NULL,
        previous_result TEXT NOT NULL, result TEXT NOT NULL DEFAULT '',
        PRIMARY KEY(service, day, job, attempt))""")


def specification(job):
    if not isinstance(job, str):
        raise ValueError("Choose a failed draft job.")
    match = re.fullmatch(r"room:(\d+):[a-f0-9]{12}", job)
    if match:
        return "room", int(match[1]), "Internal", "room:%"
    match = re.fullmatch(r"draft:(\d+)", job)
    if match:
        return "email", int(match[1]), "Email", "draft:%"
    match = re.fullmatch(r"message:(LinkedIn|WhatsApp):(\d+)", job)
    if match:
        return "message", int(match[2]), match[1], "message:" + match[1] + ":%"
    raise ValueError("Only individual room, email, LinkedIn or WhatsApp draft failures can be retried here. Review other activities separately.")


def existing_output(api, db, service, lead_id, kind, channel):
    if kind != "room":
        # Do not send another first contact when an earlier one is saved, even if
        # approved, sent or rejected. Return the saved record for review instead.
        return api.run(db, "SELECT * FROM growth_items WHERE service=? AND lead_id=? AND kind='outreach' AND channel=? AND label='First contact' ORDER BY id DESC LIMIT 1", (service, lead_id, channel)).fetchone()
    row = api.run(db, "SELECT * FROM growth_items WHERE service=? AND lead_id=? AND kind='room' AND state IN ('pending','approved') ORDER BY id DESC LIMIT 1", (service, lead_id)).fetchone()
    if row:
        return row
    lead = api.run(db, "SELECT * FROM leads WHERE id=? AND service=?", (lead_id, service)).fetchone()
    _, digest, _, _ = draft_outputs.room_context(api, db, lead, service, datetime.now(timezone.utc).astimezone(growth.IST).date().isoformat())
    for event in api.run(db, "SELECT item_id, detail FROM growth_events WHERE service=? AND lead_id=? AND event='ai_output_drafted' ORDER BY id DESC", (service, lead_id)):
        detail = json.loads(event["detail"])
        if detail.get("kind") == "room" and detail.get("context_digest") == digest:
            return api.run(db, "SELECT * FROM growth_items WHERE id=?", (event["item_id"],)).fetchone()
    return None


def retry(api, payload):
    """One human-confirmed attempt. No automatic retries; counts against existing caps."""
    if api.PUBLIC_NO_AUTH:
        raise ValueError("Draft retries require private app access.")
    service, day, job = payload.get("service"), payload.get("day"), payload.get("job")
    if service not in growth.SERVICES or payload.get("confirmed") is not True:
        raise ValueError("Confirm one additional draft attempt for a valid service.")
    today = datetime.now(timezone.utc).astimezone(growth.IST).date().isoformat()
    if day != today:
        raise ValueError("Only today's failed jobs can be retried. Review older records without replaying them.")
    kind, lead_id, channel, pattern = specification(job)
    with provider_search.DRAFT_LOCK:
        with closing(api.connect()) as db, db:
            # Serialize preflight/daily counters across processes as well as the
            # row-level compare-and-swap. This lock is released before generation.
            if api.DATABASE_URL:
                api.run(db, f"SELECT pg_advisory_xact_lock({api.BUDGET_LOCK_ID})")
            else:
                db.execute("BEGIN IMMEDIATE")
            if growth.is_paused(db, api.run, service):
                raise ValueError("Resume the workspace before retrying a draft.")
            row = api.run(db, "SELECT * FROM agent_jobs WHERE service=? AND day=? AND job=?", (service, day, job)).fetchone()
            if not row:
                raise ValueError("Job not found in this service.")
            previous = json.loads(row["result"] or "{}")
            token = payload.get("failure_token")
            if row["state"] != "needs_you" or not previous.get("retry_safe") or not token or token != previous.get("failure_token"):
                raise ValueError("This failure is changed, running, completed or has an uncertain outcome. Refresh and review it; no retry was started.")
            if previous.get("item_id") or previous.get("item_ids"):
                raise ValueError("This job already has saved outputs. Review those instead of repeating it.")
            campaign = api.run(db, "SELECT config FROM agent_campaigns WHERE service=?", (service,)).fetchone()
            if not campaign:
                raise ValueError("Configure a Sales Goal before retrying.")
            config = json.loads(campaign["config"])
            if today < config["start"] or (config["end"] and today > config["end"]):
                raise ValueError("The campaign is outside its active dates.")
            if (kind == "room" and not config.get("auto_rooms")) or (kind == "message" and not config.get("full_rhythm")):
                raise ValueError("This draft workflow is disabled in Sales Goal.")
            lead = api.run(db, "SELECT * FROM leads WHERE service=? AND id=? AND review_decision='active' AND status<>'not_interested' AND ai_screened=1", (service, lead_id)).fetchone()
            if not lead:
                raise ValueError("The lead is no longer an active screened candidate.")
            existing = existing_output(api, db, service, lead_id, kind, channel)
            if existing:
                result = {"item_id": existing["id"], "message": "A saved draft already exists. No Gemini request was made; review the existing record."}
                state = "needs_approval" if existing["state"] in ("pending", "approved") else "done"
                api.run(db, "UPDATE agent_jobs SET state=?, result=?, updated_at=? WHERE service=? AND day=? AND job=? AND state='needs_you' AND result=?", (state, json.dumps(result), api.now(), service, day, job, row["result"]))
                growth.event(db, api.run, service, existing["id"], lead_id, "draft_retry_reused", {"job": job, "day": day})
                return result
            status = api.budget_status(db)
            if status["used"]["gemini"] + status["held"]["gemini"] + 1 > status["limits"]["gemini"]:
                raise api.BudgetBlocked("No Gemini allowance remains. No retry was started.")
            # Preserve the original maximum five attempts per draft/channel/day.
            attempts = api.run(db, "SELECT COUNT(*) AS n FROM agent_jobs WHERE service=? AND day=? AND job LIKE ? AND state<>'retry_ready'", (service, day, pattern)).fetchone()["n"]
            retries = api.run(db, "SELECT COUNT(*) AS n FROM agent_retry_attempts WHERE service=? AND day=? AND job LIKE ?", (service, day, pattern)).fetchone()["n"]
            if attempts + retries >= 5:
                raise api.BudgetBlocked("The five daily attempts for this draft type/channel are used. No retry was started.")
            attempt = api.run(db, "SELECT COUNT(*) AS n FROM agent_retry_attempts WHERE service=? AND day=? AND job=?", (service, day, job)).fetchone()["n"] + 1
            if attempt > 2:
                raise ValueError("This job has already had two explicit retries today. Inspect the error before more attempts.")
            changed = api.run(db, "UPDATE agent_jobs SET state='running', updated_at=? WHERE service=? AND day=? AND job=? AND state='needs_you' AND result=?", (api.now(), service, day, job, row["result"]))
            if changed.rowcount != 1:
                raise ValueError("Another request already claimed this retry. Refresh results.")
            api.run(db, "INSERT INTO agent_retry_attempts (service, day, job, attempt, started_at, state, previous_result) VALUES (?, ?, ?, ?, ?, 'running', ?)", (service, day, job, attempt, api.now(), row["result"]))
            growth.event(db, api.run, service, None, lead_id, "draft_retry_requested", {"job": job, "day": day, "attempt": attempt})
        import automation
        try:
            automation.active(api, service)
            if kind == "room":
                item = draft_outputs.create(api, service, "room", lead_id=lead_id, day=day)
            elif kind == "email":
                item = api.ai_draft_lead(service, lead_id, {"purpose": "First contact", "guidance": config["objective"]})
            else:
                import rhythm_engine
                current = next((v for v in rhythm_engine.leads(api, service) if v["id"] == lead_id), None)
                if not current:
                    raise ValueError("Lead changed before retry execution.")
                item = rhythm_engine.message(api, service, config, day, current,
                    "linkedin_message" if channel == "LinkedIn" else "whatsapp_message", channel, "First contact")
            result = {"item_id": item["id"], "message": "Retry prepared a draft for review. Nothing was sent."}
            automation.finish(api, service, day, job, "needs_approval", result)
        except Exception as exc:
            result = {"message": automation.safe_error(api, exc), "budget_blocked": isinstance(exc, api.BudgetBlocked)}
            automation.finish(api, service, day, job, "needs_you", result)
        with closing(api.connect()) as db, db:
            current = api.run(db, "SELECT state, result FROM agent_jobs WHERE service=? AND day=? AND job=?", (service, day, job)).fetchone()
            api.run(db, "UPDATE agent_retry_attempts SET state=?, result=?, finished_at=? WHERE service=? AND day=? AND job=? AND attempt=?", (current["state"], current["result"], api.now(), service, day, job, attempt))
            growth.event(db, api.run, service, None, lead_id, "draft_retry_finished", {"job": job, "day": day, "attempt": attempt, "state": current["state"]})
            if kind == "message":
                parent_job = "rhythm:4" if service == "bim" else "rhythm:2"
                parent = api.run(db, "SELECT result FROM agent_jobs WHERE service=? AND day=? AND job=? AND state IN ('needs_you','needs_review')", (service, day, parent_job)).fetchone()
                if parent:
                    parent_result = json.loads(parent["result"] or "{}")
                    failed = [json.loads(v["result"] or "{}").get("message", "Review failed channel job.") for v in api.run(db, "SELECT result FROM agent_jobs WHERE service=? AND day=? AND job LIKE ? AND state='needs_you'", (service, day, "message:%"))]
                    ids = [v["id"] for v in api.run(db, "SELECT id FROM growth_items WHERE service=? AND kind='outreach' AND state IN ('pending','approved')", (service,))]
                    parent_result.update(item_ids=ids, issues=failed, partial=bool(failed), message=f"Outreach review: {len(ids)} saved drafts; {len(failed)} channel jobs need attention.")
                    api.run(db, "UPDATE agent_jobs SET state=?, result=?, updated_at=? WHERE service=? AND day=? AND job=? AND state<>'running'", ("needs_you" if failed else "needs_review", json.dumps(parent_result), api.now(), service, day, parent_job))
            return {**json.loads(current["result"]), "state": current["state"]}
