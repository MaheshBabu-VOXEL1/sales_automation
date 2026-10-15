"""Company knowledge packs: sourced Voxel1 facts that AI drafts may use, plus the facts still missing.

A pack lives in knowledge/<service>.json. Only facts whose status is website_published or
owner_approved, and whose "use" list includes the draft's purpose, are ever sent to Gemini.
Held facts (portfolio, testimonials, cities) and withdrawn facts are never sent.
"""
import json
import re
from pathlib import Path

DIR = Path(__file__).with_name("knowledge")
USABLE = ("website_published", "owner_approved")
LIMIT = 9
_cache = {}


def load(service):
    if service not in _cache:
        path = DIR / f"{service}.json"
        _cache[service] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    return _cache[service]


def _norm(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def facts_for(service, use, focus=""):
    """Fact sentences for one draft: core facts first, then facts tagged with the campaign focus."""
    pack = load(service)
    if not pack:
        return []
    usable = [f for f in pack["facts"] if f["status"] in USABLE and use in f.get("use", [])]
    wanted = {_norm(v) for v in (focus or "").split(",") if _norm(v)}
    matched = [f for f in usable if wanted & {_norm(t) for t in f.get("tags", [])}]
    core = [f for f in usable if "core" in f.get("tags", [])]
    chosen = list({f["id"]: f for f in matched + core}.values())
    # Matched facts lead so a Scan-to-BIM draft sees Scan-to-BIM capabilities first.
    return [f["text"] for f in chosen[:LIMIT]]


def version(service):
    pack = load(service)
    return pack["version"] if pack else ""


def summary(service):
    """Counts and open questions for the UI; never includes held fact text."""
    pack = load(service)
    if not pack:
        return {"version": "", "usable": 0, "awaiting_approval": 0, "held": 0, "missing": []}
    facts = pack["facts"]
    return {
        "version": pack["version"],
        "source": pack.get("captured_from", ""),
        "usable": sum(1 for f in facts if f["status"] in USABLE and f.get("use")),
        "awaiting_approval": sum(1 for f in facts if f["status"] == "website_published" and f.get("use")),
        "held": sum(1 for f in facts if not f.get("use") or f["status"] not in USABLE),
        "missing": [{"priority": m["priority"], "question": m["question"]} for m in pack.get("missing", [])],
    }


INSTRUCTION = (
    "voxel1_company_facts are the only statements you may make about Voxel1's services, process or capabilities. "
    "Use at most two that fit the recipient, in your own words; never add capabilities, clients, projects, locations, "
    "numbers, certifications or turnaround times that are not listed there. ")
