import os
import io
import json
import unittest
from unittest.mock import patch

import provider_search


class ProviderSearchTest(unittest.TestCase):
    def test_obvious_job_boards_and_publications_skip_paid_followup_calls(self):
        seen = []
        def fake(url, _header, _key, _params):
            seen.append(url)
            if url.endswith("mixed_companies/search"):
                return {"organizations": [
                    {"id": "a", "name": "Construction Jobs", "website_url": "https://jobs.test"},
                    {"id": "b", "name": "Civil Engineering & Construction Review", "website_url": "https://review.test"},
                    {"id": "c", "name": "Ode Consultants", "industry": "construction", "website_url": "https://ode.test"},
                ]}
            if url == provider_search.BRAVE:
                return {"web": {"results": [{"url": "https://ode.test/bim", "title": "BIM projects"}]}}
            return {"people": []}
        with patch.dict(os.environ, {"APOLLO_API_KEY": "secret", "BRAVE_SEARCH_API_KEY": "secret"}), patch.object(provider_search, "request_json", side_effect=fake):
            result = provider_search.discover({"countries": ["India"]}, "training")
        self.assertEqual([lead["company"] for lead in result["companies"]], ["Ode Consultants"])
        self.assertEqual(sum(url == provider_search.BRAVE for url in seen), 1)

    def test_organization_enrichment_uses_get_and_people_match_uses_post(self):
        seen = []
        def opened(request, timeout):
            seen.append((request.get_method(), request.full_url))
            return io.BytesIO(json.dumps({"organization": {}}).encode())
        with patch.object(provider_search.urllib.request, "urlopen", side_effect=opened):
            provider_search.request_json(provider_search.APOLLO + "/organizations/enrich", "x-api-key", "secret", {"domain": "example.com"})
            provider_search.request_json(provider_search.APOLLO + "/people/match", "x-api-key", "secret", {"id": "person"})
        self.assertEqual([item[0] for item in seen], ["GET", "POST"])

    def test_missing_keys_prevent_provider_request(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(provider_search, "request_json") as request:
            with self.assertRaisesRegex(ValueError, "APOLLO_API_KEY, BRAVE_SEARCH_API_KEY"):
                provider_search.discover({"countries": ["India"]}, "bim")
            request.assert_not_called()

    def test_one_click_filters_unverified_and_returns_contact(self):
        def fake(url, _header, _key, params):
            if url.endswith("mixed_companies/search"):
                self.assertEqual(params["organization_locations[]"], ["India"])
                self.assertEqual(params["organization_num_employees_ranges[]"], "20,200")
                return {"organizations": [
                    {"id": "a", "name": "Verified Architects", "website_url": "https://example.com", "country": "India"},
                    {"id": "b", "name": "Unverified Co", "website_url": "https://other.test", "country": "India"},
                ]}
            if url == provider_search.BRAVE:
                if "example.com" in params["q"]:
                    return {"web": {"results": [{"url": "https://example.com/bim", "description": "BIM projects"}]}}
                return {"web": {"results": []}}
            self.assertEqual(params["organization_ids[]"], ["a"])
            return {"people": [{"first_name": "Alex", "last_name_obfuscated": "Sm***h", "title": "BIM Manager"}]}
        with patch.dict(os.environ, {"APOLLO_API_KEY": "secret", "BRAVE_SEARCH_API_KEY": "secret"}), patch.object(provider_search, "request_json", side_effect=fake) as request:
            result = provider_search.discover({"countries": ["India"], "employee_min": "20", "employee_max": "200"}, "training")
        self.assertEqual(request.call_count, 4)
        self.assertEqual(result["source"], "Apollo + Brave")
        self.assertEqual(len(result["companies"]), 1)
        self.assertEqual(result["companies"][0]["contact_name"], "Alex Sm***h")
        self.assertEqual(result["companies"][0]["source_url"], "https://example.com")
        self.assertEqual(result["companies"][0]["evidence_url"], "")
        self.assertIsNone(result["companies"][0]["email"])

    def test_single_country_filter_labels_results_when_apollo_omits_country(self):
        def fake(url, _header, _key, _params):
            if url.endswith("mixed_companies/search"):
                return {"organizations": [{"id": "a", "name": "Architects", "website_url": "https://example.com"}]}
            if url == provider_search.BRAVE:
                return {"web": {"results": [{"url": "https://example.com/bim", "title": "BIM projects"}]}}
            return {"people": []}
        with patch.dict(os.environ, {"APOLLO_API_KEY": "secret", "BRAVE_SEARCH_API_KEY": "secret"}), patch.object(provider_search, "request_json", side_effect=fake):
            result = provider_search.discover({"countries": ["India"]}, "bim")
        self.assertEqual(result["companies"][0]["country"], "India")
        self.assertEqual(result["coverage"][0]["found"], 1)

    def test_people_without_organization_ids_attach_to_separate_companies(self):
        def fake(url, _header, _key, params):
            if url.endswith("mixed_companies/search"):
                return {"organizations": [
                    {"id": "a", "name": "Alpha", "website_url": "https://alpha.test"},
                    {"id": "b", "name": "Beta", "website_url": "https://beta.test"},
                ]}
            if url == provider_search.BRAVE:
                domain = "alpha.test" if "alpha.test" in params["q"] else "beta.test"
                return {"web": {"results": [{"url": f"https://{domain}/bim", "title": "BIM projects"}]}}
            person = "Alex" if params["organization_ids[]"] == ["a"] else "Blair"
            return {"people": [{"first_name": person, "title": "BIM Manager"}]}
        with patch.dict(os.environ, {"APOLLO_API_KEY": "secret", "BRAVE_SEARCH_API_KEY": "secret"}), patch.object(provider_search, "request_json", side_effect=fake) as request:
            result = provider_search.discover({"countries": ["India"]}, "bim")
        self.assertEqual([item["contact_name"] for item in result["companies"]], ["Alex", "Blair"])
        self.assertEqual(request.call_count, 5)

    def test_opt_in_enrichment_is_capped_and_excludes_personal_email_and_mobile(self):
        calls = []
        def fake(url, _header, _key, params):
            calls.append((url, params))
            if url.endswith("mixed_companies/search"):
                return {"organizations": [{"id": str(i), "name": f"Firm {i}", "website_url": f"https://firm{i}.test"} for i in range(4)]}
            if url == provider_search.BRAVE:
                domain = params["q"].split("site:", 1)[1].split(" ", 1)[0]
                return {"web": {"results": [{"url": f"https://{domain}/bim", "title": "BIM projects"}]}}
            if url.endswith("mixed_people/api_search"):
                return {"people": [{"id": "person-" + params["organization_ids[]"][0], "first_name": "Pat", "title": "BIM Manager"}]}
            if url.endswith("people/match"):
                self.assertEqual(params["reveal_personal_emails"], "false")
                self.assertEqual(params["reveal_phone_number"], "false")
                return {"person": {"name": "Pat Example", "email": "pat@example.com", "email_status": "verified"}}
            return {"organization": {"city": "Mumbai", "country": "India", "industry": "architecture", "phone": "+91 12345"}}
        env = {"APOLLO_API_KEY": "secret", "BRAVE_SEARCH_API_KEY": "secret", "APOLLO_ENRICH_DETAILS": "1"}
        with patch.dict(os.environ, env), patch.object(provider_search, "request_json", side_effect=fake):
            result = provider_search.discover({"countries": ["India"]}, "bim")
        self.assertEqual(sum(url.endswith("people/match") for url, _ in calls), 3)
        self.assertEqual(sum(url.endswith("organizations/enrich") for url, _ in calls), 3)
        self.assertEqual(result["companies"][0]["email"], "pat@example.com")
        self.assertEqual(result["companies"][0]["city"], "Mumbai")
        self.assertIsNone(result["companies"][3]["email"])
        self.assertEqual(result["companies"][3]["city"], "")


if __name__ == "__main__":
    unittest.main()
