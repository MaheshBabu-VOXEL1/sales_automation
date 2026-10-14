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
            return {"people": [{"organization_id": "a", "name": "Alex", "title": "BIM Manager"}]}
        with patch.dict(os.environ, {"APOLLO_API_KEY": "secret", "BRAVE_SEARCH_API_KEY": "secret"}), patch.object(provider_search, "request_json", side_effect=fake) as request:
            result = provider_search.discover({"countries": ["India"], "employee_min": "20", "employee_max": "200"}, "training")
        self.assertEqual(request.call_count, 4)
        self.assertEqual(result["source"], "Apollo + Brave")
        self.assertEqual(len(result["companies"]), 1)
        self.assertEqual(result["companies"][0]["contact_name"], "Alex")
        self.assertEqual(result["companies"][0]["source_url"], "https://example.com")
        self.assertEqual(result["companies"][0]["evidence_url"], "")
        self.assertIsNone(result["companies"][0]["email"])


if __name__ == "__main__":
    unittest.main()
