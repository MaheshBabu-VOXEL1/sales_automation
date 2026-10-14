"""Small Voxel1 prospecting prototype.

Run with: python server.py
Public OpenStreetMap data is used only after a user starts a search.
SQLite is the local default; DATABASE_URL selects PostgreSQL.
"""

from __future__ import annotations

import json
import os
import base64
import binascii
import hmac
import secrets
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from http.cookies import SimpleCookie
import provider_search
import growth
import ai_draft


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("VOXEL1_DB", str(ROOT / "data" / "voxel1.db")))
DATABASE_URL = os.environ.get("DATABASE_URL", "")
HOST = os.environ.get("VOXEL1_HOST", "127.0.0.1")
PORT = int(os.environ.get("VOXEL1_PORT", os.environ.get("PORT", "8001")))
AUTH_USER = os.environ.get("VOXEL1_AUTH_USER", "")
AUTH_PASSWORD = os.environ.get("VOXEL1_AUTH_PASSWORD", "")
PUBLIC_NO_AUTH = os.environ.get("VOXEL1_PUBLIC_NO_AUTH", "") == "1"
SESSION_SECONDS = 8 * 60 * 60
sessions: dict[str, float] = {}
failed_logins: dict[str, list[float]] = {}
session_lock = threading.Lock()
USER_AGENT = "Voxel1ProspectingPrototype/0.1 (local internal research)"
OVERPASS = "https://overpass-api.de/api/interpreter"
OVERPASS_BACKUP = "https://overpass.private.coffee/api/interpreter"
COUNTRIES = {"US": "USA", "AE": "UAE", "SA": "Saudi Arabia", "IN": "India", "SG": "Singapore"}
# A bounded five-country sample for the free public-map adapter. This is not
# country-wide coverage; a licensed discovery provider is needed for that.
TARGET_LOCATIONS = (
    ("US", "New York", 40.7128, -74.0060),
    ("AE", "Dubai", 25.2048, 55.2708),
    ("SA", "Riyadh", 24.7136, 46.6753),
    ("IN", "Mumbai", 19.0760, 72.8777),
    ("SG", "Singapore", 1.3521, 103.8198),
)
SERVICES = {"training": "Training", "bim": "BIM Services"}
CATEGORIES = {
    "architecture": [("office", "architect"), ("craft", "architect")],
    "construction": [("office", "construction_company"), ("craft", "construction")],
    "engineering": [("office", "engineer"), ("office", "engineering")],
    "real_estate": [("office", "estate_agent"), ("office", "property_management")],
    "education": [("amenity", "college"), ("amenity", "training")],
}
DEFAULTS = {
    "training": {"name": "BIM Training ICP", "categories": ["architecture", "construction", "engineering"], "notes": "Firms that may need BIM training."},
    "bim": {"name": "BIM Services ICP", "categories": ["architecture", "construction", "engineering"], "notes": "Firms that may need BIM delivery support."},
}
COUNTRY_ALIASES = {
    "us": "USA", "usa": "USA", "united states": "USA", "united states of america": "USA",
    "ae": "UAE", "uae": "UAE", "united arab emirates": "UAE",
    "sa": "Saudi Arabia", "saudi arabia": "Saudi Arabia",
    "in": "India", "india": "India",
    "sg": "Singapore", "singapore": "Singapore",
}
LOCATION_BY_COUNTRY = {COUNTRIES[code]: (code, city, lat, lon) for code, city, lat, lon in TARGET_LOCATIONS}
search_lock = threading.Lock()
# Monthly request caps for paid providers. Only someone with access to the server
# environment can change them. Unset or invalid values mean 0, so paid searches
# stay blocked until a cap is deliberately configured.
BUDGET_ENV = {
    "searches": "VOXEL1_MONTHLY_SEARCH_LIMIT",
    "apollo": "VOXEL1_MONTHLY_APOLLO_REQUESTS",
    "brave": "VOXEL1_MONTHLY_BRAVE_REQUESTS",
    "gemini": "VOXEL1_MONTHLY_GEMINI_REQUESTS",
}
PROVIDERS = ("apollo", "brave", "gemini")
# Rejecting or archiving hides a candidate from the active list and from later
# paid follow-up checks; the row and its history are kept.
REVIEW_DECISIONS = ("active", "rejected", "archived")
REVIEW_REASONS = {
    "not_target_industry": "Not in a target industry",
    "vendor_or_competitor": "BIM/training vendor or competitor",
    "job_board_or_publication": "Job board, directory or publication",
    "wrong_location": "Outside the target countries",
    "wrong_size": "Outside the target company size",
    "duplicate": "Duplicate of another company",
    "no_current_need": "No current need; revisit later",
    "other": "Other (see note)",
}
BUDGET_LOCK_ID = 4207001  # PostgreSQL advisory lock serializing reservations.


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    if DATABASE_URL:
        if not DATABASE_URL.startswith(("postgresql://", "postgres://")):
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL.")
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL driver missing. Install requirements.txt.") from exc
        return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=10)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def run(db, statement: str, values: tuple = ()):
    # The fixed application queries use '?' placeholders on SQLite.
    # Psycopg uses '%s'; no user-supplied SQL is passed to this helper.
    if DATABASE_URL:
        statement = statement.replace("?", "%s")
    return db.execute(statement, values)


def init_db() -> None:
    with connect() as db:
        run(db, """CREATE TABLE IF NOT EXISTS icps (
            service TEXT PRIMARY KEY, name TEXT NOT NULL, country TEXT NOT NULL,
            city TEXT NOT NULL, categories TEXT NOT NULL, notes TEXT NOT NULL,
            updated_at TEXT NOT NULL, profile_json TEXT NOT NULL DEFAULT '{}'
        )""")
        identity = "BIGINT GENERATED BY DEFAULT AS IDENTITY" if DATABASE_URL else "INTEGER"
        growth.init(db, run, identity)
        run(db, f"""CREATE TABLE IF NOT EXISTS leads (
            id {identity} PRIMARY KEY,
            service TEXT NOT NULL, source_id TEXT NOT NULL,
            company TEXT NOT NULL, category TEXT NOT NULL,
            city TEXT NOT NULL, country TEXT NOT NULL,
            email TEXT, phone TEXT, website TEXT, source_url TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new', notes TEXT NOT NULL DEFAULT '',
            ai_screened INTEGER NOT NULL DEFAULT 0,
            discovered_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            UNIQUE(service, source_id)
        )""")
        for column in ("contact_name", "contact_title", "evidence_url", "match_reason", "ai_reason", "ai_model", "screened_at",
                       "review_reason", "review_note", "reviewed_at"):
            if DATABASE_URL:
                run(db, f"ALTER TABLE leads ADD COLUMN IF NOT EXISTS {column} TEXT NOT NULL DEFAULT ''")
            elif column not in {row["name"] for row in run(db, "PRAGMA table_info(leads)")}:
                run(db, f"ALTER TABLE leads ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        if DATABASE_URL:
            run(db, "ALTER TABLE leads ADD COLUMN IF NOT EXISTS ai_screened INTEGER NOT NULL DEFAULT 0")
        elif "ai_screened" not in {row["name"] for row in run(db, "PRAGMA table_info(leads)")}:
            run(db, "ALTER TABLE leads ADD COLUMN ai_screened INTEGER NOT NULL DEFAULT 0")
        if DATABASE_URL:
            run(db, "ALTER TABLE leads ADD COLUMN IF NOT EXISTS review_decision TEXT NOT NULL DEFAULT 'active'")
        elif "review_decision" not in {row["name"] for row in run(db, "PRAGMA table_info(leads)")}:
            run(db, "ALTER TABLE leads ADD COLUMN review_decision TEXT NOT NULL DEFAULT 'active'")
        run(db, f"""CREATE TABLE IF NOT EXISTS lead_events (
            id {identity} PRIMARY KEY,
            lead_id INTEGER NOT NULL, service TEXT NOT NULL, event TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{{}}', created_at TEXT NOT NULL
        )""")
        run(db, f"""CREATE TABLE IF NOT EXISTS search_runs (
            id {identity} PRIMARY KEY,
            service TEXT NOT NULL, month TEXT NOT NULL, status TEXT NOT NULL,
            estimate_json TEXT NOT NULL, actual_json TEXT NOT NULL DEFAULT '{{}}',
            error TEXT NOT NULL DEFAULT '', started_at TEXT NOT NULL, finished_at TEXT NOT NULL DEFAULT ''
        )""")
        run(db, f"""CREATE TABLE IF NOT EXISTS provider_usage (
            id {identity} PRIMARY KEY,
            run_id INTEGER NOT NULL, month TEXT NOT NULL,
            provider TEXT NOT NULL, operation TEXT NOT NULL, created_at TEXT NOT NULL
        )""")
        # A reservation left open by a crash or restart keeps counting at its
        # full estimate, because the requests it actually made are unknown.
        run(db, "UPDATE search_runs SET status='interrupted', finished_at=? WHERE status='reserved'", (now(),))
        if DATABASE_URL:
            run(db, "ALTER TABLE icps ADD COLUMN IF NOT EXISTS profile_json TEXT NOT NULL DEFAULT '{}'")
        else:
            columns = {row["name"] for row in run(db, "PRAGMA table_info(icps)")}
            if "profile_json" not in columns:
                run(db, "ALTER TABLE icps ADD COLUMN profile_json TEXT NOT NULL DEFAULT '{}'")
        for service, item in DEFAULTS.items():
            profile = {"countries": list(COUNTRIES.values()), "employee_min": "", "employee_max": "", "titles": "", "keywords": "", "exclusions": "", "goal": ""}
            run(db,
                "INSERT INTO icps (service, name, country, city, categories, notes, updated_at, profile_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(service) DO NOTHING",
                (service, item["name"], "ALL", "Configured focus", json.dumps(item["categories"]), item["notes"], now(), json.dumps(profile)),
            )


class MapConnectionError(RuntimeError):
    """Transport failure; distinct from HTTP rejection or rate limiting."""


def public_get(url: str, params: dict | None = None, data: bytes | None = None) -> object:
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        explanations = {
            400: "the map service rejected the search query",
            429: "the public map service is rate limiting requests",
            502: "the public map service is temporarily unavailable",
            503: "the public map service is temporarily unavailable",
            504: "the public map search timed out",
        }
        explanation = explanations.get(exc.code, "the public map service rejected the request")
        raise RuntimeError(f"HTTP {exc.code}: {explanation}.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise MapConnectionError(f"Could not connect to the public map service: {exc.reason if isinstance(exc, urllib.error.URLError) else exc}.") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("The public map service returned an invalid response.") from exc


def validate_icp(payload: dict) -> dict:
    name = str(payload.get("name", "")).strip()[:100]
    categories = payload.get("categories", [])
    notes = str(payload.get("notes", "")).strip()[:500]
    if not name:
        raise ValueError("Enter an ICP name.")
    if not isinstance(categories, list) or not categories or any(c not in CATEGORIES for c in categories):
        raise ValueError("Choose at least one supported industry.")
    raw_countries = payload.get("countries", [])
    if not isinstance(raw_countries, list) or not 1 <= len(raw_countries) <= 30:
        raise ValueError("Choose one or more countries of focus (up to 30).")
    countries = []
    seen = set()
    for raw in raw_countries:
        if not isinstance(raw, str):
            raise ValueError("Country names must be text.")
        country = raw.strip()
        if not 2 <= len(country) <= 80 or any(character in country for character in "<>/\\"):
            raise ValueError("Enter valid country names of 2–80 characters.")
        country = COUNTRY_ALIASES.get(country.casefold(), country)
        if country.casefold() not in seen:
            countries.append(country)
            seen.add(country.casefold())
    if not countries:
        raise ValueError("Choose at least one country of focus.")
    sizes = {}
    for key in ("employee_min", "employee_max"):
        value = payload.get(key, "")
        if value in ("", None):
            sizes[key] = ""
        elif isinstance(value, bool) or not str(value).isdigit() or not 1 <= int(value) <= 1000000:
            raise ValueError("Employee counts must be positive whole numbers.")
        else:
            sizes[key] = str(int(value))
    if sizes["employee_min"] and sizes["employee_max"] and int(sizes["employee_min"]) > int(sizes["employee_max"]):
        raise ValueError("Minimum employee count cannot exceed maximum.")
    profile = {"countries": countries, **sizes}
    for key in ("titles", "keywords", "exclusions", "goal"):
        profile[key] = str(payload.get(key, "")).strip()[:500]
    return {"name": name, "city": "Configured focus", "country": "CUSTOM", "categories": list(dict.fromkeys(categories)), "notes": notes, **profile}


class BudgetBlocked(Exception):
    """A paid search was refused before any provider request."""


def month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def budget_limits() -> dict:
    limits = {}
    for key, name in BUDGET_ENV.items():
        value = os.environ.get(name, "").strip()
        limits[key] = int(value) if value.isdigit() else 0
    return limits


def budget_status(db) -> dict:
    """Usage this month. Finished runs count measured requests; open or interrupted runs hold their full estimate."""
    month = month_key()
    limits = budget_limits()
    used = {provider: 0 for provider in PROVIDERS}
    held = {provider: 0 for provider in PROVIDERS}
    runs = run(db, "SELECT * FROM search_runs WHERE month=? ORDER BY id DESC", (month,)).fetchall()
    for row in runs:
        if row["status"] in ("completed", "failed"):
            for provider, count in json.loads(row["actual_json"] or "{}").items():
                used[provider] = used.get(provider, 0) + int(count)
        else:
            for provider, count in json.loads(row["estimate_json"]).items():
                held[provider] = held.get(provider, 0) + int(count)
    used["gemini"] += ai_draft_count(db, month)
    estimate = provider_search.estimate_requests()
    reasons = []
    if len(runs) + 1 > limits["searches"]:
        reasons.append(f"Monthly search limit reached ({len(runs)} of {limits['searches']} used). Set {BUDGET_ENV['searches']} on the server to allow more." if limits["searches"]
                       else f"No monthly search limit is set. Set {BUDGET_ENV['searches']} on the server before running paid searches.")
    for provider in PROVIDERS:
        need = estimate[provider]
        if need and used[provider] + held[provider] + need > limits[provider]:
            label = provider.capitalize()
            remaining = max(limits[provider] - used[provider] - held[provider], 0)
            reasons.append(f"{label}: this search may need up to {need} requests but only {remaining} remain this month. Raise {BUDGET_ENV[provider]} on the server to allow it." if limits[provider]
                           else f"{label}: no monthly request limit is set. Set {BUDGET_ENV[provider]} on the server.")
    recent = [{"id": row["id"], "service": row["service"], "status": row["status"], "estimate": json.loads(row["estimate_json"]),
               "actual": json.loads(row["actual_json"] or "{}"), "error": row["error"], "started_at": row["started_at"]} for row in runs[:10]]
    return {"month": month, "limits": limits, "used": used, "held": held, "searches_used": len(runs),
            "estimate": estimate, "allowed": not reasons, "blocked_reasons": reasons, "recent": recent}


def reserve_search(service: str) -> tuple[int, dict]:
    """Atomically check the monthly caps and record a reservation; raises BudgetBlocked otherwise."""
    with connect() as db:
        if DATABASE_URL:
            run(db, f"SELECT pg_advisory_xact_lock({BUDGET_LOCK_ID})")
        else:
            db.execute("BEGIN IMMEDIATE")
        status = budget_status(db)
        if not status["allowed"]:
            raise BudgetBlocked(" ".join(status["blocked_reasons"]))
        values = (service, status["month"], "reserved", json.dumps(status["estimate"]), now())
        sql = "INSERT INTO search_runs (service, month, status, estimate_json, started_at) VALUES (?, ?, ?, ?, ?)"
        if DATABASE_URL:
            run_id = run(db, sql + " RETURNING id", values).fetchone()["id"]
        else:
            run_id = run(db, sql, values).lastrowid
        return run_id, status["estimate"]


def ai_draft_count(db, month: str) -> int:
    # AI drafts are not search runs; each attempt is a provider_usage row with run_id 0.
    return run(db, "SELECT COUNT(*) AS n FROM provider_usage WHERE run_id=0 AND month=? AND provider='gemini' AND operation='outreach_draft'",
               (month,)).fetchone()["n"]


def reserve_ai_draft() -> None:
    """Count one Gemini request against the monthly cap before it is sent; raises BudgetBlocked otherwise."""
    with connect() as db:
        if DATABASE_URL:
            run(db, f"SELECT pg_advisory_xact_lock({BUDGET_LOCK_ID})")
        else:
            db.execute("BEGIN IMMEDIATE")
        status = budget_status(db)
        limit = status["limits"]["gemini"]
        if not limit:
            raise BudgetBlocked(f"Gemini: no monthly request limit is set. Set {BUDGET_ENV['gemini']} on the server.")
        if status["used"]["gemini"] + status["held"]["gemini"] + 1 > limit:
            raise BudgetBlocked(f"Gemini: the monthly limit of {limit} requests is used up. Raise {BUDGET_ENV['gemini']} on the server to allow more.")
        run(db, "INSERT INTO provider_usage (run_id, month, provider, operation, created_at) VALUES (0, ?, 'gemini', 'outreach_draft', ?)",
            (status["month"], now()))


def ai_draft_lead(service: str, lead_id: int, payload: dict) -> dict:
    purpose = payload.get("purpose")
    if purpose not in ai_draft.PURPOSES:
        raise ValueError("Choose First contact or Follow-up.")
    guidance = payload.get("guidance") or ""
    if not isinstance(guidance, str) or len(guidance) > 500:
        raise ValueError("Keep the guidance under 500 characters.")
    if not os.environ.get("GEMINI_API_KEY"):
        raise ValueError("Set GEMINI_API_KEY on the server to write drafts with AI.")
    with connect() as db:
        lead = run(db, "SELECT * FROM leads WHERE id=? AND service=?", (lead_id, service)).fetchone()
        if not lead:
            raise LookupError("Lead not found in this service.")
        if lead["review_decision"] != "active":
            raise ValueError("Restore this company before drafting a message to it.")
        if growth.is_paused(db, run, service):
            raise ValueError("This workspace is paused. Resume it before drafting.")
        room = run(db, "SELECT room_notes FROM growth_leads WHERE lead_id=?", (lead_id,)).fetchone()
        earlier = [{"subject": r["title"], "status": r["state"], "text": r["body"][:600]}
                   for r in run(db, "SELECT title, body, state FROM growth_items WHERE lead_id=? AND kind='outreach' AND state IN ('approved', 'done') ORDER BY id DESC LIMIT 3", (lead_id,))]
    if purpose == "Follow-up" and not earlier:
        raise ValueError("There is no approved or sent message to follow up on yet. Draft a first contact instead.")
    reserve_ai_draft()
    draft = ai_draft.write_draft(dict(lead), service, purpose, room["room_notes"] if room else "", earlier, guidance.strip())
    with connect() as db:
        item = growth.save_item(db, run, None, {"service": service, "kind": "outreach", "lead_id": lead_id, "title": draft["title"],
                                                "body": draft["body"], "channel": "Email", "label": purpose, "due": datetime.now(timezone.utc).strftime("%Y-%m-%d")})
        growth.event(db, run, service, item["id"], lead_id, "ai_drafted", {"title": item["title"], "kind": "outreach", "model": draft["model"], "purpose": purpose})
    return item


def finish_search(run_id: int, meter: provider_search.Meter, error: str = "") -> None:
    """Record every provider request the search attempted, including failed ones."""
    with connect() as db:
        month = run(db, "SELECT month FROM search_runs WHERE id=?", (run_id,)).fetchone()["month"]
        for provider, operation in meter.calls:
            run(db, "INSERT INTO provider_usage (run_id, month, provider, operation, created_at) VALUES (?, ?, ?, ?, ?)",
                (run_id, month, provider, operation, now()))
        run(db, "UPDATE search_runs SET status=?, actual_json=?, error=?, finished_at=? WHERE id=?",
            ("failed" if error else "completed", json.dumps(meter.totals()), error[:500], now(), run_id))


def log_event(db, lead_id: int, service: str, event: str, detail: dict) -> None:
    run(db, "INSERT INTO lead_events (lead_id, service, event, detail_json, created_at) VALUES (?, ?, ?, ?, ?)",
        (lead_id, service, event, json.dumps(detail), now()))


def storage_info(db) -> dict:
    """Non-secret description of where data is stored, for checking a deployment."""
    counts = {table: run(db, f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"] for table in ("leads", "lead_events", "search_runs", "provider_usage")}
    if DATABASE_URL:
        host = urllib.parse.urlparse(DATABASE_URL).hostname or ""
        return {"database": "postgresql", "server_version": run(db, "SHOW server_version").fetchone()["server_version"],
                "render_internal_host": host.startswith("dpg-") and "." not in host, "row_counts": counts}
    return {"database": "sqlite", "data_directory_is_mount": os.path.ismount(DB_PATH.parent),
            "note": "SQLite keeps data only if its directory is on a persistent disk.", "row_counts": counts}


def get_icp(db, service: str) -> dict:
    row = run(db, "SELECT * FROM icps WHERE service = ?", (service,)).fetchone()
    result = dict(row)
    result["categories"] = json.loads(result["categories"])
    profile = json.loads(result["profile_json"] or "{}")
    if not profile.get("countries"):
        profile["countries"] = list(COUNTRIES.values())
    for key in ("employee_min", "employee_max", "titles", "keywords", "exclusions", "goal"):
        profile.setdefault(key, "")
    result.update(profile)
    result["search_mode"] = "Apollo + Brave" if (os.environ.get("APOLLO_API_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY")) else "OpenStreetMap city samples"
    result["enrichment_enabled"] = os.environ.get("APOLLO_ENRICH_DETAILS") == "1"
    result["ai_qualification_enabled"] = bool(os.environ.get("GEMINI_API_KEY"))
    result["review_reasons"] = REVIEW_REASONS
    return result


def find_companies(icp: dict) -> dict:
    # Search only the selected countries with available city-sample adapters.
    # Public Overpass is not suitable for country-wide bulk prospecting.
    filters = list(dict.fromkeys(pair for category in icp["categories"] for pair in CATEGORIES[category]))
    companies = []
    coverage = []
    supported_count = 0
    endpoint = OVERPASS
    for country_name in icp["countries"]:
        location = LOCATION_BY_COUNTRY.get(country_name)
        if not location:
            coverage.append({"country": country_name, "city": None, "found": 0, "error": "No discovery provider connected for this country."})
            continue
        country, city, lat, lon = location
        if supported_count:
            time.sleep(1)
        supported_count += 1
        selectors = "".join(f'  nwr(around:12000,{lat},{lon})["{key}"="{value}"]["name"];\n' for key, value in filters)
        query = f"[out:json][timeout:20];\n(\n{selectors});\nout center 40;"
        data = urllib.parse.urlencode({"data": query}).encode()
        try:
            try:
                result = public_get(endpoint, data=data)
            except MapConnectionError as primary_error:
                if endpoint == OVERPASS_BACKUP:
                    raise
                # Switch once for this search, not for HTTP errors such as 429.
                endpoint = OVERPASS_BACKUP
                try:
                    result = public_get(endpoint, data=data)
                except RuntimeError as backup_error:
                    raise RuntimeError(f"Primary connection failed: {primary_error} Backup failed: {backup_error}") from backup_error
        except RuntimeError as exc:
            coverage.append({"country": country, "city": city, "found": 0, "error": str(exc)})
            continue
        count = 0
        for element in result.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name", "").strip()
            if not name:
                continue
            email = tags.get("contact:email") or tags.get("email") or None
            phone = tags.get("contact:phone") or tags.get("phone") or None
            website = tags.get("contact:website") or tags.get("website") or None
            if website and not website.startswith(("https://", "http://")):
                website = None
            companies.append({
                "source_id": f'{element["type"]}/{element["id"]}',
                "company": name[:200], "category": next((tags.get(k) for k, _ in filters if tags.get(k)), "business")[:100],
                "city": city, "country": country,
                "email": email[:254] if email else None, "phone": phone[:100] if phone else None,
                "website": website[:500] if website else None,
                "source_url": f'https://www.openstreetmap.org/{element["type"]}/{element["id"]}',
                "match_reason": f"OpenStreetMap lists it as a {next((tags.get(k) for k, _ in filters if tags.get(k)), 'business')} within 12 km of {city}.",
            })
            count += 1
        coverage.append({"country": country, "city": city, "found": count})
    if not supported_count:
        raise ValueError("No search provider is connected for the selected countries. The free prototype currently searches USA, UAE, Saudi Arabia, India and Singapore city samples.")
    if not any("error" not in item for item in coverage):
        first_error = next(item["error"] for item in coverage if item["city"])
        raise RuntimeError(f"All supported public-map searches failed. First error: {first_error}")
    return {"companies": companies, "coverage": coverage}


class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self) -> None:
        # Hosting probes use HEAD before the browser supplies demo credentials.
        if urllib.parse.urlparse(self.path).path != "/":
            self.send_response(404)
        else:
            self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def authorized(self) -> bool:
        if PUBLIC_NO_AUTH or not (AUTH_USER and AUTH_PASSWORD):
            return True
        value = self.headers.get("Authorization", "")
        try:
            scheme, token = value.split(" ", 1)
            if scheme.lower() != "basic":
                raise ValueError("Unsupported authentication")
            decoded = base64.b64decode(token, validate=True).decode("utf-8")
            user, password = decoded.split(":", 1)
            if hmac.compare_digest(user, AUTH_USER) and hmac.compare_digest(password, AUTH_PASSWORD):
                return True
        except (ValueError, UnicodeError, binascii.Error):
            pass
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            token = cookie["voxel1_session"].value if "voxel1_session" in cookie else ""
        except Exception:
            token = ""
        with session_lock:
            expires = sessions.get(token, 0) if token else 0
            if expires > time.time():
                return True
            if token:
                sessions.pop(token, None)
        if not urllib.parse.urlparse(self.path).path.startswith("/api/"):
            self.send_response(302)
            self.send_header("Location", "/login")
        else:
            self.send_response(401)
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def session_cookie(self, token: str, max_age: int) -> str:
        host = self.headers.get("Host", "")
        secure = self.headers.get("X-Forwarded-Proto", "").lower() == "https" or not host.startswith(("localhost", "127.0.0.1"))
        return f"voxel1_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}" + ("; Secure" if secure else "")

    def same_origin_write(self) -> bool:
        # Reject browser-initiated cross-site writes, including a form POST.
        origin = self.headers.get("Origin")
        host = self.headers.get("Host", "")
        if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site" or (
            origin and origin not in (f"https://{host}", f"http://{host}")
        ):
            self.respond(403, {"error": "Cross-site requests are not allowed."})
            return False
        return True

    def respond(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_optional_json(self) -> dict:
        return self.read_json() if int(self.headers.get("Content-Length", "0") or 0) else {}

    def read_json(self) -> dict:
        size = int(self.headers.get("Content-Length", "0"))
        if size < 1 or size > 20000:
            raise ValueError("Invalid request size.")
        payload = json.loads(self.rfile.read(size))
        if not isinstance(payload, dict):
            raise ValueError("Expected a JSON object.")
        return payload

    def service_from_path(self, parts: list[str]) -> str:
        if len(parts) < 3 or parts[2] not in SERVICES:
            raise ValueError("Choose Training or BIM Services.")
        return parts[2]

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/login":
            body = (ROOT / "web" / "login.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not self.authorized():
            return
        if path == "/" or path in ("/app.js", "/style.css", "/extra.css"):
            filename = "index.html" if path == "/" else path[1:]
            mime = "text/html" if filename.endswith(".html") else "text/javascript" if filename.endswith(".js") else "text/css"
            body = (ROOT / "web" / filename).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        parts = path.strip("/").split("/")
        if parts == ["api", "growth"]:
            with connect() as db:
                return self.respond(200, growth.snapshot(db, run))
        if parts == ["api", "budget"]:
            with connect() as db:
                return self.respond(200, budget_status(db))
        if parts == ["api", "system"]:
            with connect() as db:
                return self.respond(200, storage_info(db))
        try:
            if parts[:2] != ["api", "services"]:
                return self.respond(404, {"error": "Not found"})
            service = self.service_from_path(parts)
            with connect() as db:
                if len(parts) == 4 and parts[3] == "icp":
                    return self.respond(200, get_icp(db, service))
                if len(parts) == 4 and parts[3] == "leads":
                    rows = run(db, "SELECT * FROM leads WHERE service = ? ORDER BY updated_at DESC, id DESC", (service,)).fetchall()
                    return self.respond(200, [dict(row) for row in rows])
                if len(parts) == 6 and parts[3] == "leads" and parts[5] == "history":
                    rows = run(db, "SELECT event, detail_json, created_at FROM lead_events WHERE lead_id=? AND service=? ORDER BY id DESC", (int(parts[4]), service)).fetchall()
                    history = [{"event": row["event"], "detail": json.loads(row["detail_json"]), "created_at": row["created_at"]} for row in rows]
                    history += growth.lead_history(db, run, service, int(parts[4]))
                    return self.respond(200, sorted(history, key=lambda item: item["created_at"], reverse=True))
        except ValueError as exc:
            return self.respond(400, {"error": str(exc)})
        self.respond(404, {"error": "Not found"})

    def do_PUT(self) -> None:
        if not self.authorized() or not self.same_origin_write():
            return
        if self.growth_write("PUT"):
            return
        parts = urllib.parse.urlparse(self.path).path.strip("/").split("/")
        try:
            service = self.service_from_path(parts)
            if parts[:2] != ["api", "services"] or parts[3:] != ["icp"]:
                return self.respond(404, {"error": "Not found"})
            icp = validate_icp(self.read_json())
            with connect() as db:
                profile = {key: icp[key] for key in ("countries", "employee_min", "employee_max", "titles", "keywords", "exclusions", "goal")}
                run(db, "UPDATE icps SET name=?, country=?, city=?, categories=?, notes=?, profile_json=?, updated_at=? WHERE service=?",
                           (icp["name"], icp["country"], icp["city"], json.dumps(icp["categories"]), icp["notes"], json.dumps(profile), now(), service))
                return self.respond(200, get_icp(db, service))
        except (ValueError, json.JSONDecodeError) as exc:
            self.respond(400, {"error": str(exc)})

    def do_POST(self) -> None:
        if urllib.parse.urlparse(self.path).path == "/api/login":
            if not self.same_origin_write():
                return
            remote = getattr(self, "client_address", ("unknown",))[0]
            with session_lock:
                recent = [attempt for attempt in failed_logins.get(remote, []) if time.time() - attempt < 60]
                failed_logins[remote] = recent
                if len(recent) >= 5:
                    return self.respond(429, {"error": "Too many sign-in attempts. Try again in a minute."})
            try:
                payload = self.read_json()
                user = str(payload.get("username", ""))
                password = str(payload.get("password", ""))
            except (ValueError, json.JSONDecodeError):
                return self.respond(400, {"error": "Enter username and password."})
            if not AUTH_USER or not AUTH_PASSWORD or not (hmac.compare_digest(user, AUTH_USER) and hmac.compare_digest(password, AUTH_PASSWORD)):
                with session_lock:
                    failed_logins.setdefault(remote, []).append(time.time())
                return self.respond(401, {"error": "Invalid username or password."})
            token = secrets.token_urlsafe(32)
            with session_lock:
                failed_logins.pop(remote, None)
                expired = [key for key, expiry in sessions.items() if expiry <= time.time()]
                for key in expired:
                    sessions.pop(key, None)
                if len(sessions) >= 100:
                    sessions.clear()
                sessions[token] = time.time() + SESSION_SECONDS
            body = b'{"ok":true}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Set-Cookie", self.session_cookie(token, SESSION_SECONDS))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not self.authorized() or not self.same_origin_write():
            return
        parts = urllib.parse.urlparse(self.path).path.strip("/").split("/")
        if parts[:2] == ["api", "services"] and len(parts) == 6 and parts[3] == "leads" and parts[4].isdigit() and parts[5] == "ai-draft":
            try:
                service = self.service_from_path(parts)
                return self.respond(200, ai_draft_lead(service, int(parts[4]), self.read_json()))
            except LookupError as exc:
                return self.respond(404, {"error": str(exc)})
            except BudgetBlocked as exc:
                return self.respond(409, {"error": str(exc)})
            except provider_search.ProviderError as exc:
                return self.respond(502, {"error": str(exc)})
            except (ValueError, json.JSONDecodeError) as exc:
                return self.respond(400, {"error": str(exc)})
        if self.growth_write("POST"):
            return
        try:
            service = self.service_from_path(parts)
            if parts[:2] != ["api", "services"] or parts[3:] != ["discover"]:
                return self.respond(404, {"error": "Not found"})
            if not search_lock.acquire(blocking=False):
                return self.respond(429, {"error": "Another search is running. Please try again shortly."})
            try:
                with connect() as db:
                    icp = get_icp(db, service)
                    if growth.is_paused(db, run, service):
                        return self.respond(409, {"error": "This workspace is paused. Resume it before starting a search."})
                provider_ready = bool(os.environ.get("APOLLO_API_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY"))
                if provider_ready and PUBLIC_NO_AUTH and os.environ.get("VOXEL1_ALLOW_PUBLIC_SEARCH") != "1":
                    return self.respond(403, {"error": "API search is disabled on this public app. Set VOXEL1_ALLOW_PUBLIC_SEARCH=1 after accepting that visitors can use the search credits, or enable app authentication."})
                if provider_ready:
                    request = self.read_optional_json()
                    with connect() as db:
                        budget = budget_status(db)
                    if not budget["allowed"]:
                        return self.respond(409, {"error": " ".join(budget["blocked_reasons"]), "budget": budget})
                    # The browser must echo the exact estimate it showed, so a
                    # settings change between preview and click needs a new confirmation.
                    if request.get("confirmed") is not True or request.get("estimate") != budget["estimate"]:
                        return self.respond(409, {"error": "Review and confirm this search's estimated provider requests before searching.", "needs_confirmation": True, "budget": budget})
                    try:
                        run_id, allowance = reserve_search(service)
                    except BudgetBlocked as exc:
                        with connect() as db:
                            return self.respond(409, {"error": str(exc), "budget": budget_status(db)})
                    meter = provider_search.Meter(allowance)
                    try:
                        with connect() as db:
                            skip_ids = {row["source_id"].split("/", 1)[1] for row in run(db, "SELECT source_id FROM leads WHERE service=? AND review_decision<>'active'", (service,))
                                        if row["source_id"].startswith("apollo/")}
                        discovery = provider_search.discover(icp, service, meter, skip_ids)
                    except Exception as exc:
                        finish_search(run_id, meter, str(exc) or exc.__class__.__name__)
                        raise
                    finish_search(run_id, meter)
                    discovery["usage"] = {"run_id": run_id, "estimate": allowance, "actual": meter.totals()}
                else:
                    discovery = find_companies(icp)
                companies = discovery["companies"]
                inserted = 0
                skipped = discovery.get("skipped_reviewed", 0)
                with connect() as db:
                    for company in companies:
                        existing = run(db, "SELECT id, review_decision FROM leads WHERE service=? AND source_id=?", (service, company["source_id"])).fetchone()
                        if existing and existing["review_decision"] != "active":
                            skipped += 1  # A rejected or archived candidate keeps its saved record unchanged.
                            continue
                        screened = bool(company.get("ai_screened"))
                        cur = run(db, """INSERT INTO leads
                            (service, source_id, company, category, city, country, email, phone, website, source_url, contact_name, contact_title, evidence_url, ai_screened,
                             match_reason, ai_reason, ai_model, screened_at, discovered_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(service, source_id) DO UPDATE SET
                            company=excluded.company,
                            category=CASE WHEN excluded.category <> 'business' THEN excluded.category ELSE leads.category END,
                            city=CASE WHEN excluded.city <> '' THEN excluded.city ELSE leads.city END,
                            country=CASE WHEN excluded.country <> '' THEN excluded.country ELSE leads.country END,
                            email=COALESCE(excluded.email, leads.email), phone=COALESCE(excluded.phone, leads.phone),
                            website=excluded.website, source_url=excluded.source_url,
                            contact_name=CASE WHEN excluded.contact_name <> '' THEN excluded.contact_name ELSE leads.contact_name END,
                            contact_title=CASE WHEN excluded.contact_title <> '' THEN excluded.contact_title ELSE leads.contact_title END,
                            evidence_url=excluded.evidence_url,
                            ai_screened=CASE WHEN excluded.ai_screened=1 THEN 1 ELSE leads.ai_screened END,
                            match_reason=CASE WHEN excluded.match_reason <> '' THEN excluded.match_reason ELSE leads.match_reason END,
                            ai_reason=CASE WHEN excluded.ai_screened=1 THEN excluded.ai_reason ELSE leads.ai_reason END,
                            ai_model=CASE WHEN excluded.ai_screened=1 THEN excluded.ai_model ELSE leads.ai_model END,
                            screened_at=CASE WHEN excluded.ai_screened=1 THEN excluded.screened_at ELSE leads.screened_at END,
                            updated_at=excluded.updated_at""",
                            (service, company["source_id"], company["company"], company["category"], company["city"], company["country"], company["email"], company["phone"], company["website"], company["source_url"], company.get("contact_name", ""), company.get("contact_title", ""), company.get("evidence_url", ""), int(screened),
                             company.get("match_reason", ""), company.get("ai_reason", "") if screened else "", company.get("ai_model", "") if screened else "", now() if screened else "", now(), now()))
                        lead_id = existing["id"] if existing else run(db, "SELECT id FROM leads WHERE service=? AND source_id=?", (service, company["source_id"])).fetchone()["id"]
                        log_event(db, lead_id, service, "found_again" if existing else "discovered",
                                  {"source": discovery.get("source", "OpenStreetMap"), "match_reason": company.get("match_reason", ""), "ai_screened": screened})
                        inserted += int(existing is None and cur.rowcount > 0)
                return self.respond(200, {"found": len(companies), "added": inserted, "source": discovery.get("source", "OpenStreetMap"), "coverage": discovery["coverage"], "warnings": discovery.get("warnings", []), "usage": discovery.get("usage"), "skipped_reviewed": skipped})
            finally:
                search_lock.release()
        except ValueError as exc:
            self.respond(400, {"error": str(exc)})
        except RuntimeError as exc:
            self.respond(502, {"error": str(exc)})

    def do_PATCH(self) -> None:
        if not self.authorized() or not self.same_origin_write():
            return
        if self.growth_write("PATCH"):
            return
        parts = urllib.parse.urlparse(self.path).path.strip("/").split("/")
        try:
            service = self.service_from_path(parts)
            if parts[:4] != ["api", "services", service, "leads"] or len(parts) != 6 or parts[5] not in ("status", "review"):
                return self.respond(404, {"error": "Not found"})
            lead_id = int(parts[4])
            payload = self.read_json()
            notes = str(payload.get("notes", "")).strip()[:500]
            if parts[5] == "status":
                status = payload.get("status")
                if status not in ("new", "interested", "not_interested"):
                    raise ValueError("Invalid interest status.")
            else:
                decision = payload.get("decision")
                reason = payload.get("reason") or ""
                if decision not in REVIEW_DECISIONS:
                    raise ValueError("Choose reject, archive or restore.")
                if decision != "active" and reason not in REVIEW_REASONS:
                    raise ValueError("Choose a reason for rejecting or archiving this company.")
                if decision != "active" and reason == "other" and not notes:
                    raise ValueError("Add a short note when the reason is Other.")
                if decision == "active":
                    reason = ""
            with connect() as db:
                current = run(db, "SELECT * FROM leads WHERE id=? AND service=?", (lead_id, service)).fetchone()
                if not current:
                    return self.respond(404, {"error": "Lead not found"})
                if parts[5] == "status":
                    run(db, "UPDATE leads SET status=?, notes=?, updated_at=? WHERE id=?", (status, notes, now(), lead_id))
                    log_event(db, lead_id, service, "interest", {"from": current["status"], "to": status, "note": notes})
                else:
                    run(db, "UPDATE leads SET review_decision=?, review_reason=?, review_note=?, reviewed_at=?, updated_at=? WHERE id=?",
                        (decision, reason, notes, now(), now(), lead_id))
                    log_event(db, lead_id, service, "review", {"from": current["review_decision"], "to": decision, "reason": reason, "note": notes})
                return self.respond(200, dict(run(db, "SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()))
        except (ValueError, json.JSONDecodeError) as exc:
            self.respond(400, {"error": str(exc)})

    def growth_write(self, method):
        parts = urllib.parse.urlparse(self.path).path.strip("/").split("/")
        if parts[:2] != ["api", "growth"]:
            return False
        try:
            payload = self.read_json()
            with connect() as db:
                result = growth.mutate(db, run, method, parts[2:], payload, log_event)
            self.respond(200, result)
        except LookupError as exc:
            self.respond(404, {"error": str(exc)})
        except growth.Conflict as exc:
            self.respond(409, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError) as exc:
            self.respond(400, {"error": str(exc)})
        return True


if __name__ == "__main__":
    if HOST not in ("127.0.0.1", "localhost", "::1") and not (PUBLIC_NO_AUTH or (AUTH_USER and AUTH_PASSWORD)):
        raise SystemExit("Public binding requires credentials or VOXEL1_PUBLIC_NO_AUTH=1.")
    init_db()
    print(f"Voxel1 prototype: http://{HOST}:{PORT}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
