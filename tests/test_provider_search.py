import os
import unittest
from unittest.mock import patch

import provider_search


class ProviderSearchTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
