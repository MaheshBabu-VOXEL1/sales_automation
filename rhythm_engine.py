"""Execute offering rhythms through review drafts, never external delivery."""
import json
import os
import re
from contextlib import closing
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

import ai_draft
import draft_outputs
import growth
import provider_search


class MissingInput(ValueError):
    pass


REUSED = "Existing draft still awaiting review; no new draft was prepared."


def init(db, run):
    run(db, """CREATE TABLE IF NOT EXISTS research_snapshots (
        id TEXT PRIMARY KEY, service TEXT NOT NULL, day TEXT NOT NULL,
        kind TEXT NOT NULL, query TEXT NOT NULL, findings TEXT NOT NULL)""")


def save_item(api, service, day, title, body, kind="brief", label="Research", lead_id=None, channel="Internal", model=None):
    with closing(api.connect()) as db, db:
        if growth.is_paused(db, api.run, service):
            raise MissingInput("Paused before saving output; no new draft was stored.")
        if lead_id:
            current = api.run(db, "SELECT review_decision, status FROM leads WHERE id=? AND service=?", (lead_id, service)).fetchone()
            if not current or current["review_decision"] != "active" or current["status"] == "not_interested":
                raise MissingInput("Lead changed during preparation. Output was not saved.")
        if len(body) > 10000:
            body = body[:9800] + "\n[Report shortened. Review the job rows for the complete record.]"
        item = growth.save_item(db, api.run, None, {"service": service, "kind": kind, "lead_id": lead_id,
            "title": title[:200], "body": body, "label": label, "channel": channel, "due": day})
        growth.event(db, api.run, service, item["id"], lead_id, "rhythm_output_created", {"kind": kind, "title": item["title"], "model": model})
        return item


def leads(api, service):
    with closing(api.connect()) as db:
        return [dict(r) for r in api.run(db, """SELECT l.*, r.stage, r.room_notes FROM leads l
            LEFT JOIN growth_leads r ON r.lead_id=l.id WHERE l.service=?
            AND l.review_decision='active' AND l.status<>'not_interested' ORDER BY l.id""", (service,))]


def research(api, service, config, day, slot):
    # Brave requires a plan with storage rights to retain even partial results.
    if os.environ.get("BRAVE_SEARCH_STORAGE_ALLOWED") != "1":
        raise MissingInput("Research needs a Brave plan granting result-storage rights. Confirm the plan, then set BRAVE_SEARCH_STORAGE_ALLOWED=1 on the server. No research query was made.")
    if not os.environ.get("BRAVE_SEARCH_API_KEY"):
        raise MissingInput("Configure BRAVE_SEARCH_API_KEY on the server for signal research.")
    if api.PUBLIC_NO_AUTH:
        raise MissingInput("Use private app access before scheduled paid research.")
    terms = {"tenders": 'BIM tender bid "BIM lead"', "awards": "construction project award contractor BIM",
             "hiring": "contractor hiring BIM modeller Revit", "evening": "BIM construction project tender award"}
    targets = [v.strip() for v in config.get("target_accounts", "").splitlines() if v.strip()]
    # At most twelve queries per activity; sixty ordinary named accounts fit in
    # five-account batches. Explicit coverage avoids claiming a full-market scan.
    chosen = []
    if targets:
        offset = datetime.fromisoformat(day).toordinal() % len(targets)
        chosen = [targets[(offset + n) % len(targets)] for n in range(min(60, len(targets)))]
    geo = " OR ".join(config["targeting"]["countries"][:5])
    base = terms[slot] + " (" + geo + ") " + config["targeting"].get("keywords", "")[:100]
    if len(base) > 350:
        raise MissingInput("Country names make the signal query too long. Narrow this campaign's geographic focus.")
    batches = [chosen[n:n + 5] for n in range(0, len(chosen), 5)] or [[]]
    queries, covered = [], []
    while batches and len(queries) < 12:
        batch = batches.pop(0)
        query = base + (" (" + " OR ".join('"' + n.replace('"', '') + '"' for n in batch) + ")" if batch else "")
        if len(query) > 600 or len(query.split()) > 75:
            if len(batch) <= 1:
                raise MissingInput("A target account name makes the signal query too long. Use a shorter company name.")
            middle = len(batch) // 2
            batches = [batch[:middle], batch[middle:]] + batches
            continue
        queries.append(query)
        covered.extend(batch)
    run_id, allowance = api.reserve_search(service, {"apollo": 0, "brave": len(queries), "gemini": 0})
    meter = provider_search.Meter(allowance)
    try:
        import automation
        found = []
        for query in queries:
            automation.active(api, service)
            meter.charge("brave", "rhythm_" + slot)
            data = provider_search.request_json(provider_search.BRAVE, "X-Subscription-Token", os.environ["BRAVE_SEARCH_API_KEY"], {"q": query, "count": 5, "freshness": "pm"})
            for hit in (data.get("web") or {}).get("results", [])[:5]:
                url = str(hit.get("url") or "")
                if len(url) > 1500 or urlparse(url).scheme not in ("http", "https") or not urlparse(url).hostname or any(v["url"] == url for v in found):
                    continue
                clean = lambda value, size: re.sub(r"<[^>]*>", "", str(value or ""))[:size]
                found.append({"url": url, "title": clean(hit.get("title"), 180), "excerpt": clean(hit.get("description"), 300)})
        with closing(api.connect()) as db, db:
            api.run(db, "INSERT INTO research_snapshots (id, service, day, kind, query, findings) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO NOTHING",
                    (f"{service}:{day}:{slot}", service, day, slot, "\n".join(queries), json.dumps(found)))
        ids = []
        for page in range(max(1, (len(found) + 4) // 5)):
            lines = [f"Research: {slot}", "Search matches only; tender status, deadlines, awards and buyer need are NOT verified.",
                     f"Coverage: {len(queries)} queries; named accounts: {len(covered)} of {len(targets)}. Countries: first {min(5, len(config['targeting']['countries']))} of {len(config['targeting']['countries'])}.",
                     "A search mentioning an account does not establish a verified opportunity."]
            for n, hit in enumerate(found[page * 5:page * 5 + 5], page * 5 + 1):
                lines += [f"\n{n}. {hit['title']}", "Publisher URL: " + hit["url"], "Short search excerpt: " + " ".join(hit["excerpt"].split()[:20])[:120], "Next: verify the original publisher and current status before acting."]
            if not found:
                lines.append("No matches returned. This is not proof that no opportunities exist.")
            ids.append(save_item(api, service, day, f"{slot.title()} research {page + 1} — {day}", "\n".join(lines))["id"])
    except Exception:
        api.finish_search(run_id, meter, "Rhythm research stopped or failed; inspect the rhythm result.")
        raise
    api.finish_search(run_id, meter)
    return {"item_ids": ids, "message": f"{len(found)} unique search matches; {len(covered)} of {len(targets)} named accounts queried. Not verified opportunities.", "partial": bool(batches)}


def mapping(api, service, config, day):
    candidates = leads(api, service)[:10]
    if not candidates:
        raise MissingInput("No active leads are saved for decision-maker mapping. Discovery must produce candidates first.")
    lines = ["Decision-maker and introduction map", "Only saved contact data is listed. Contact seniority does not prove bid ownership or a warm relationship."]
    for lead in candidates:
        name = lead.get("contact_name") or "Name not recorded"
        if "*" in name:
            name = "Provider-obfuscated name; verify before addressing"
        if ai_draft.contact_domain_mismatch(lead):
            name += " (email domain differs from the company website; verify employment before addressing)"
        lines += ["\nCompany: " + lead["company"], "Recorded contact: " + name,
                  "Role: " + (lead.get("contact_title") or "Not recorded"),
                  "Source: " + (lead.get("source_url") or "Not recorded"),
                  "Bid holder / project authority: not verified. Warm introduction: confirm with the team."]
    lines += ["\nTeam-supplied relationship notes:", config.get("warm_paths") or "None recorded. Do not claim a mutual introduction."]
    item = save_item(api, service, day, "Decision-maker and introduction map", "\n".join(lines), label="Mapping")
    return {"item_ids": [item["id"]], "message": "Recorded contacts mapped; unknown relationships explicitly flagged."}


def message(api, service, config, day, lead, kind, channel, label):
    with closing(api.connect()) as db:
        existing = api.run(db, "SELECT * FROM growth_items WHERE service=? AND lead_id=? AND kind='outreach' AND channel=? AND label=? AND state IN ('pending','approved') ORDER BY id DESC", (service, lead["id"], channel, label)).fetchone()
        if existing:
            return {**dict(existing), "reused": True}
        sent = [dict(r) for r in api.run(db, "SELECT title, body, updated_at, channel FROM growth_items WHERE lead_id=? AND kind='outreach' AND channel='Email' AND state='done' ORDER BY updated_at DESC LIMIT 2", (lead["id"],))]
    facts = ai_draft.lead_facts(lead, service, lead.get("room_notes") or "", [], ai_draft.campaign_focus(config))
    if kind == "followup":
        facts["recorded_sent_messages"] = sent
        facts["reply_tracking"] = "No automatic reply tracking; do not claim no reply unless recorded by the team."
    if kind == "cross_sell":
        facts["customer_basis"] = "Recorded Won stage or explicitly listed by the team as an existing customer."
    import automation
    automation.active(api, service)
    api.reserve_ai_draft(operation="rhythm_" + kind)
    output = draft_outputs.generate(kind, service, facts, config["objective"] + "\n" + config.get("strategy", ""))
    return save_item(api, service, day, output["title"], output["body"], kind="outreach", label=label, lead_id=lead["id"], channel=channel, model=output["model"])


def outreach(api, service, config, day):
    all_candidates = [l for l in leads(api, service) if l["ai_screened"]]
    if not all_candidates:
        raise MissingInput("No screened active leads are available for outreach drafting.")
    with closing(api.connect()) as db:
        existing_channels = {(r["lead_id"], r["channel"]) for r in api.run(db, "SELECT lead_id, channel FROM growth_items WHERE service=? AND kind='outreach' AND label='First contact'", (service,))}
    candidates = [l for l in all_candidates if any((l["id"], channel) not in existing_channels for channel in ("LinkedIn", "WhatsApp"))][:5]
    from automation import claim, finish
    outputs = []
    with closing(api.connect()) as db:
        outputs += [r["id"] for r in api.run(db, "SELECT id FROM growth_items WHERE service=? AND kind='outreach' AND channel='Email' AND state IN ('pending','approved')", (service,))]
    for channel, kind in (("LinkedIn", "linkedin_message"), ("WhatsApp", "whatsapp_message")):
        for lead in candidates:
            if (lead["id"], channel) in existing_channels:
                continue
            job = f"message:{channel}:{lead['id']}"
            if claim(api, service, day, job):
                try:
                    item = message(api, service, config, day, lead, kind, channel, "First contact")
                    outputs.append(item["id"])
                    finish(api, service, day, job, "needs_approval", {"item_id": item["id"], "message": REUSED if item.get("reused") else f"{channel} message drafted; not sent. Contact permission must be checked before any delivery."})
                except Exception as exc:
                    finish(api, service, day, job, "needs_you", {"message": error(api, exc)})
    with closing(api.connect()) as db:
        pending = [r["id"] for r in api.run(db, "SELECT id FROM growth_items WHERE service=? AND kind='outreach' AND state IN ('pending','approved')", (service,))]
        failed = [r["result"] for r in api.run(db, "SELECT result FROM agent_jobs WHERE service=? AND day=? AND state='needs_you' AND job LIKE ?", (service, day, "message:%"))]
    return {"item_ids": list(dict.fromkeys(outputs + pending)), "message": f"Outreach preparation finished: {len(pending)} service-wide drafts awaiting review; {len(failed)} channel jobs need attention.", "issues": [json.loads(v).get("message", "") for v in failed], "partial": bool(failed)}


def partner(api, service, config, day, academic=False):
    names = [v.strip().casefold() for v in config.get("partner_accounts", "").splitlines() if v.strip()]
    matches = [l for l in leads(api, service) if ((l["category"] == "education" or re.search(r"\b(university|college|institute)\b", l["company"], re.I)) if academic else any(n == l["company"].casefold() for n in names))]
    if not matches:
        raise MissingInput("Add a saved college/university lead for academic partnership drafting." if academic else "List an actual PMC/consultant in Sales Goal → Partner accounts and save that company's lead. No partner relationship will be invented.")
    item = message(api, service, config, day, matches[0], "academic" if academic else "partner", "Email", "Partner")
    return {"item_ids": [item["id"]], "message": REUSED if item.get("reused") else "Partnership discussion drafted from recorded facts; no agreement or prior relationship assumed."}


def followups(api, service, config, day):
    cutoff = datetime.fromisoformat(day).replace(tzinfo=growth.IST) - timedelta(days=3)
    eligible = []
    with closing(api.connect()) as db:
        for lead in leads(api, service):
            sent = api.run(db, "SELECT updated_at FROM growth_items WHERE lead_id=? AND kind='outreach' AND channel='Email' AND state='done' ORDER BY updated_at DESC LIMIT 1", (lead["id"],)).fetchone()
            if sent:
                try:
                    if datetime.fromisoformat(sent["updated_at"]) <= cutoff:
                        eligible.append(lead)
                except (TypeError, ValueError):
                    pass
    prepared = [message(api, service, config, day, l, "followup", "Email", "Follow-up") for l in eligible[:3]]
    ids = [item["id"] for item in prepared]
    if not ids:
        # Preparing call questions is useful even before a follow-up can be justified.
        opportunities = [l for l in leads(api, service) if l.get("stage") in ("meeting", "proposal", "negotiation")]
        if not opportunities:
            return {"message": "No recorded sent email older than three days or active proposal/scope call. No follow-up was invented.", "no_action": True}
        lead = opportunities[0]
        api.reserve_ai_draft(operation="scope_preparation")
        output = draft_outputs.generate("proposal", service, ai_draft.lead_facts(lead, service, lead.get("room_notes") or "", [], ai_draft.campaign_focus(config)), config["objective"])
        ids = [save_item(api, service, day, output["title"], output["body"], label="Call preparation", lead_id=lead["id"], model=output["model"])["id"]]
    if prepared and all(item.get("reused") for item in prepared):
        return {"item_ids": ids, "message": REUSED}
    return {"item_ids": ids, "message": "Follow-up or scope-call preparation ready for review. No automatic reply or meeting confirmation assumed."}


def clients(api, service, config, day):
    names = [v.strip().casefold() for v in config.get("existing_clients", "").splitlines() if v.strip()]
    pool = [l for l in leads(api, service) if l.get("stage") == "won" or l["company"].casefold() in names]
    if not pool:
        raise MissingInput("No recorded existing clients are available. Add actual customer names in Sales Goal → Existing clients and save their leads (Training: VITALS/XIM clients), or record a real Won opportunity.")
    item = message(api, service, config, day, pool[0], "cross_sell", "Email", "Account")
    return {"item_ids": [item["id"]], "message": REUSED if item.get("reused") else "Next-project or team-training enquiry drafted for a recorded existing customer."}


def social(api, service, config, day):
    from automation import claim, finish
    targets = config.get("content_targets", {})
    if not sum(targets.values()):
        raise MissingInput("Set at least one social post per day in Sales Goal.")
    outputs, issues = [], []
    for channel, kind in (("LinkedIn", "linkedin"), ("Instagram", "instagram"), ("Facebook", "facebook")):
        for slot in range(1, targets.get(channel, 0) + 1):
            job = f"{kind}:{slot}"
            if claim(api, service, day, job):
                try:
                    item = draft_outputs.create(api, service, kind, slot=slot, day=day)
                    outputs.append(item["id"])
                    finish(api, service, day, job, "needs_approval", {"item_id": item["id"], "message": f"{channel} text draft ready; graphic-card download available for Instagram/Facebook. Nothing published."})
                except Exception as exc:
                    issues.append(error(api, exc))
                    finish(api, service, day, job, "needs_you", {"message": error(api, exc)})
    with closing(api.connect()) as db:
        outputs += [r["id"] for r in api.run(db, "SELECT id FROM growth_items WHERE service=? AND due=? AND kind='content' AND state IN ('pending','approved')", (service, day))]
    proof_missing = not (config.get("approved_proof") and config.get("proof_consent"))
    notice = f"{len(set(outputs))} social drafts available for review; Instagram/Facebook include editable graphic cards."
    if proof_missing:
        # Missing team input, not a provider failure: reported as needs_input.
        issues.append("No consented proof/trainee-story source is saved. Educational alternatives are reviewable; they are not client proof or a trainee story.")
        notice += " Consented proof/story input is still needed for this rhythm activity."
    return {"item_ids": list(dict.fromkeys(outputs)), "message": notice, "issues": issues, "partial": len(issues) > int(proof_missing), "input_needed": proof_missing}


def summary(api, service, day, research_issue=None):
    with closing(api.connect()) as db:
        jobs = [dict(r) for r in api.run(db, "SELECT job, state, result FROM agent_jobs WHERE service=? AND day=? ORDER BY job", (service, day))]
        counts = [dict(r) for r in api.run(db, "SELECT kind, state, COUNT(*) AS total FROM growth_items WHERE service=? GROUP BY kind, state", (service,))]
    lines = [f"{service.upper()} daily summary — {day} (IST)", "Job outcomes for today:"]
    for job in jobs:
        data = json.loads(job["result"] or "{}")
        lines.append(f"- {job['job']}: {job['state']} — {data.get('message') or ('Found: ' + str(data.get('found', 'not recorded')))}")
    if research_issue:
        lines.append("Evening research: " + research_issue)
    lines += ["\nSaved draft inventory (service-wide, not today's conversion counts):"]
    lines += [f"- {r['kind']} / {r['state']}: {r['total']}" for r in counts]
    lines.append("No message delivery, replies, meetings or sales are inferred by this report. Review evidence and pending drafts in the app.")
    item = save_item(api, service, day, "Daily summary — " + day, "\n".join(lines), label="Daily summary")
    return {"item_ids": [item["id"]], "message": "Daily summary prepared from saved job and draft records."}


def error(api, exc):
    if isinstance(exc, (MissingInput, ValueError, api.BudgetBlocked)):
        return str(exc)[:650]
    return "Provider or storage operation failed. No automatic retry today; inspect provider status and saved results."


def tick(api, instant=None, phase="drafts"):
    from automation import claim, finish
    local = (instant or datetime.now(timezone.utc)).astimezone(growth.IST)
    day, clock = local.date().isoformat(), local.strftime("%H:%M")
    with closing(api.connect()) as db:
        campaigns = [dict(r) for r in api.run(db, "SELECT * FROM agent_campaigns")]
    for row in campaigns:
        service, config = row["service"], json.loads(row["config"])
        if not config.get("full_rhythm") or day < config["start"] or (config["end"] and day > config["end"]):
            continue
        for slot, (scheduled, _, _, _) in enumerate(growth.RHYTHMS[service]):
            research_slot = slot in ((0, 1) if service == "bim" else (0,))
            if research_slot != (phase == "research") or clock < scheduled:
                continue
            job = f"rhythm:{slot}"
            if not claim(api, service, day, job):
                continue
            try:
                if research_slot:
                    result = research(api, service, config, day, "hiring" if service == "training" else "tenders" if slot == 0 else "awards")
                elif service == "bim" and slot == 2:
                    result = mapping(api, service, config, day)
                elif service == "bim" and slot == 3:
                    with closing(api.connect()) as db:
                        ids = [r["id"] for r in api.run(db, "SELECT id FROM growth_items WHERE service=? AND kind='room' AND state IN ('pending','approved','done')", (service,))]
                    if not ids:
                        raise MissingInput("No room draft is ready. Inspect the room-generation jobs or discovery results.")
                    result = {"item_ids": ids, "message": "Company room drafts available for review; applying remains a separate approval step."}
                elif (service == "bim" and slot == 4) or (service == "training" and slot == 2):
                    result = outreach(api, service, config, day)
                elif (service == "bim" and slot == 5) or (service == "training" and slot == 1):
                    result = partner(api, service, config, day, academic=service == "training")
                elif (service == "bim" and slot == 6) or (service == "training" and slot == 3):
                    result = followups(api, service, config, day)
                elif (service == "bim" and slot == 7) or (service == "training" and slot == 4):
                    result = clients(api, service, config, day)
                elif (service == "bim" and slot == 8) or (service == "training" and slot == 5):
                    result = social(api, service, config, day)
                else:
                    try:
                        research(api, service, config, day, "evening")
                        issue, missing = None, False
                    except Exception as exc:
                        issue, missing = error(api, exc), isinstance(exc, MissingInput)
                    result = summary(api, service, day, issue)
                    if issue:
                        result.update(issues=[issue], **({"input_needed": True} if missing else {"partial": True}))
                # needs_you is reserved for provider/storage failures; missing team input is needs_input.
                state = ("needs_you" if result.get("partial") else "needs_input" if result.get("input_needed")
                         else "no_action" if result.get("no_action") else "needs_review")
                finish(api, service, day, job, state, result)
            except Exception as exc:
                state = "needs_budget" if isinstance(exc, api.BudgetBlocked) else "needs_input" if isinstance(exc, MissingInput) else "needs_you"
                finish(api, service, day, job, state, {"message": error(api, exc)})
        if service == "training" and phase == "drafts" and clock >= "18:00" and claim(api, service, day, "summary"):
            try:
                finish(api, service, day, "summary", "needs_review", summary(api, service, day))
            except Exception as exc:
                finish(api, service, day, "summary", "needs_you", {"message": error(api, exc)})
