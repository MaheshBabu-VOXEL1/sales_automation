"""Bounded Apollo + Brave company discovery for the Voxel1 pilot."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

APOLLO = "https://api.apollo.io/api/v1"
BRAVE = "https://api.search.brave.com/res/v1/web/search"
LIMIT = 10  # At most ten company candidates per click.
ENRICH_LIMIT = 3  # Paid enrichment never exceeds three companies and three people per click.
DEFAULT_TITLES = {
    "training": ("BIM Manager", "Learning and Development Manager", "Training Manager", "Technical Director"),
    "bim": ("BIM Manager", "Head of Design", "Technical Director", "Managing Director"),
}
SERVICE_TERMS = {"training": ("BIM", "Revit"), "bim": ("BIM", "Revit")}
CATEGORY_TAGS = {"architecture": "architecture", "construction": "construction", "engineering": "civil engineering", "real_estate": "real estate", "education": "education"}


class ProviderError(RuntimeError):
    pass


def request_json(url, key_header, key, params):
    query = urllib.parse.urlencode(params, doseq=True)
    method = "POST" if url.startswith(APOLLO) and not url.endswith("/organizations/enrich") else "GET"
    req = urllib.request.Request(url + "?" + query, headers={key_header: key, "Accept": "application/json"}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"{('Apollo' if url.startswith(APOLLO) else 'Brave')} returned HTTP {exc.code}. Check API access, credits and rate limits.") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise ProviderError(f"{('Apollo' if url.startswith(APOLLO) else 'Brave')} request failed; try again later.") from exc


def website_of(org):
    raw = org.get("website_url") or org.get("primary_domain") or ""
    if not raw:
        return None
    url = raw if raw.startswith(("https://", "http://")) else "https://" + raw
    parsed = urllib.parse.urlparse(url)
    return url[:500] if parsed.hostname else None


def discover(icp, service):
    apollo_key = os.environ.get("APOLLO_API_KEY", "")
    brave_key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
    if not apollo_key or not brave_key:
        missing = ", ".join(name for name, value in (("APOLLO_API_KEY", apollo_key), ("BRAVE_SEARCH_API_KEY", brave_key)) if not value)
        raise ValueError(f"Configure {missing} on the server before searching.")
    countries = icp["countries"]
    keywords = [CATEGORY_TAGS[category] for category in icp.get("categories", []) if category in CATEGORY_TAGS]
    keywords += [part.strip() for part in icp.get("keywords", "").split(",") if part.strip()]
    exclusions = [part.strip() for part in icp.get("exclusions", "").split(",") if part.strip()]
    titles = [part.strip() for part in icp.get("titles", "").split(",") if part.strip()] or list(DEFAULT_TITLES[service])
    params = {"organization_locations[]": countries, "page": 1, "per_page": LIMIT}
    if keywords:
        params["q_organization_keyword_tags[]"] = keywords[:5]
    if exclusions:
        params["q_not_organization_keyword_tags[]"] = exclusions[:5]
    if icp.get("employee_min") or icp.get("employee_max"):
        params["organization_num_employees_ranges[]"] = f'{icp.get("employee_min") or 1},{icp.get("employee_max") or 1000000}'
    response = request_json(APOLLO + "/mixed_companies/search", "x-api-key", apollo_key, params)
    if not isinstance(response, dict) or not isinstance(response.get("organizations"), list):
        raise ProviderError("Apollo returned an unexpected company response.")
    found = []
    warnings = []
    enrich = os.environ.get("APOLLO_ENRICH_DETAILS") == "1"
    for org in response["organizations"][:LIMIT]:
        if not isinstance(org, dict) or not org.get("id") or not org.get("name"):
            continue
        website = website_of(org)
        if not website:
            continue
        domain = urllib.parse.urlparse(website).hostname
        query = f'site:{domain} "{SERVICE_TERMS[service][0]}" OR "{SERVICE_TERMS[service][1]}"'
        try:
            evidence = request_json(BRAVE, "X-Subscription-Token", brave_key, {"q": query, "count": 5, "result_filter": "web"})
            root_domain = domain.removeprefix("www.")
            hits = [hit for hit in evidence.get("web", {}).get("results", [])
                    if urllib.parse.urlparse(hit.get("url", "")).hostname in (root_domain, "www." + root_domain)
                    and any(term.casefold() in (str(hit.get("title") or "") + " " + str(hit.get("description") or "")).casefold()
                            for term in SERVICE_TERMS[service])]
        except ProviderError as exc:
            warnings.append(str(exc))
            continue
        if not hits:
            continue  # Do not label a company relevant without a matching public page.
        # Brave results are used only in memory for qualification. Its Search
        # API terms do not permit retaining response data in our database.
        found.append({"source_id": "apollo/" + str(org["id"]), "company": str(org["name"])[:200],
                      "category": str(org.get("industry") or "business")[:100], "city": str(org.get("city") or "")[:100],
                      "country": str(org.get("country") or (countries[0] if len(countries) == 1 else ""))[:100], "email": None, "phone": None,
                      "website": website, "source_url": website,
                      "contact_name": "", "contact_title": "",
                      "evidence_url": ""})
    for index, lead in enumerate(found):
        try:
            people = request_json(APOLLO + "/mixed_people/api_search", "x-api-key", apollo_key,
                                  {"organization_ids[]": [lead["source_id"].split("/", 1)[1]],
                                   "person_titles[]": titles[:8], "per_page": 3, "page": 1})
            matches = people.get("people", [])
            if matches:
                person = matches[0]
                first = str(person.get("first_name") or "").strip()
                last = str(person.get("last_name") or person.get("last_name_obfuscated") or "").strip()
                lead["contact_name"] = str(person.get("name") or " ".join(part for part in (first, last) if part))[:200]
                lead["contact_title"] = str(person.get("title") or "")[:200]
                if enrich and index < ENRICH_LIMIT and person.get("id"):
                    try:
                        detail = request_json(APOLLO + "/people/match", "x-api-key", apollo_key,
                                              {"id": person["id"], "reveal_personal_emails": "false", "reveal_phone_number": "false"})
                        enriched = detail.get("person") or {}
                        if enriched.get("name"):
                            lead["contact_name"] = str(enriched["name"])[:200]
                        if enriched.get("email_status") == "verified" and enriched.get("email"):
                            email = str(enriched["email"]).strip()
                            if "@" in email and " " not in email:
                                lead["email"] = email[:254]
                    except ProviderError as exc:
                        warnings.append(str(exc))
        except ProviderError as exc:
            warnings.append(str(exc))
        if enrich and index < ENRICH_LIMIT:
            try:
                organization = request_json(APOLLO + "/organizations/enrich", "x-api-key", apollo_key,
                                            {"domain": urllib.parse.urlparse(lead["website"]).hostname.removeprefix("www.")}).get("organization") or {}
                if organization.get("city"):
                    lead["city"] = str(organization["city"])[:100]
                if organization.get("country"):
                    lead["country"] = str(organization["country"])[:100]
                if organization.get("industry"):
                    lead["category"] = str(organization["industry"])[:100]
                if organization.get("phone"):
                    lead["phone"] = str(organization["phone"])[:100]
            except ProviderError as exc:
                warnings.append(str(exc))
    return {"companies": found, "coverage": [{"country": name, "city": None, "found": sum(c["country"].casefold() == name.casefold() for c in found)} for name in countries],
            "warnings": list(dict.fromkeys(warnings)), "source": "Apollo + Brave"}
