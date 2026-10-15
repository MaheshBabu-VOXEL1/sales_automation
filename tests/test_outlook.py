import json
import io
import base64
import os
import tempfile
import time
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

import growth
import outlook
import server


class OutlookTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(server, "DB_PATH", Path(self.temp.name) / "test.db"),
                        patch.object(server, "AUTH_USER", "owner"), patch.object(server, "AUTH_PASSWORD", "test-password"),
                        patch.object(server, "PUBLIC_NO_AUTH", False), patch.dict(os.environ, {
                            "OUTLOOK_CLIENT_ID": "test-id", "OUTLOOK_CLIENT_SECRET": "test-secret",
                            "OUTLOOK_TENANT_ID": "tenant", "OUTLOOK_REDIRECT_URI": "https://example.test/api/outlook/callback",
                            "OUTLOOK_TOKEN_KEY": Fernet.generate_key().decode()})]
        for p in self.patches:
            p.start()
        server.init_db()
        self.instant = datetime(2026, 10, 15, 10, tzinfo=timezone.utc)
        self.account()

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def sql(self, statement, values=()):
        with closing(server.connect()) as db, db:
            return [dict(r) for r in server.run(db, statement, values)]

    def account(self, tested=True):
        encrypted = outlook.cipher().encrypt(json.dumps({"access_token": "access-secret", "refresh_token": "refresh-secret", "expires_at": time.time() + 3600}).encode()).decode()
        self.sql("INSERT INTO outlook_account (id, email, tokens, tested) VALUES (1, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET tokens=excluded.tokens, tested=excluded.tested", (outlook.SENDER, encrypted, int(tested)))

    def approved(self, index=1):
        with closing(server.connect()) as db, db:
            lead = growth.add_company(db, server.run, {"service": "bim", "company": f"Firm {index}", "email": f"person{index}@example.test"}, server.log_event)
            item = growth.save_item(db, server.run, None, {"service": "bim", "kind": "outreach", "title": "BIM support", "body": "A reviewed message.", "channel": "Email", "lead_id": lead["id"]})
            return growth.save_item(db, server.run, item["id"], {"action": "approve", "revision": item["revision"]}), lead

    def queue(self, item, lead):
        return outlook.queue(server, {"item_id": item["id"], "revision": item["revision"], "recipient": lead["email"], "timezone": "UTC", "permission_confirmed": True})

    def test_existing_approvals_do_not_send_until_explicitly_queued(self):
        item, lead = self.approved()
        with patch.object(outlook, "send") as send:
            outlook.tick(server, self.instant)
            send.assert_not_called()
        with self.assertRaises(ValueError):
            outlook.queue(server, {"item_id": item["id"], "revision": item["revision"], "recipient": lead["email"], "timezone": "UTC"})
        self.queue(item, lead)
        with self.assertRaises(ValueError):
            self.queue(item, lead)
        with patch.object(outlook, "send") as send:
            outlook.tick(server, self.instant)
            outlook.tick(server, self.instant)
            send.assert_called_once_with("access-secret", lead["email"], item["title"], item["body"])
        self.assertEqual(self.sql("SELECT state FROM outlook_queue")[0]["state"], "accepted")
        self.assertEqual(self.sql("SELECT state FROM growth_items")[0]["state"], "done")

    def test_pause_and_recipient_hours_wait_then_stale_approval_cancels(self):
        item, lead = self.approved()
        self.queue(item, lead)
        self.sql("UPDATE growth_settings SET paused=1 WHERE service='global'")
        with patch.object(outlook, "send") as send:
            outlook.tick(server, self.instant)
            self.sql("UPDATE growth_settings SET paused=0 WHERE service='global'")
            outlook.tick(server, datetime(2026, 10, 15, 3, tzinfo=timezone.utc))
            outlook.tick(server, datetime(2026, 10, 17, 10, tzinfo=timezone.utc))
            send.assert_not_called()
        with closing(server.connect()) as db, db:
            growth.save_item(db, server.run, item["id"], {**item, "body": "Changed message"})
        with patch.object(outlook, "send") as send:
            outlook.tick(server, self.instant)
            send.assert_not_called()
        self.assertEqual(self.sql("SELECT state FROM outlook_queue")[0]["state"], "cancelled")

    def test_provider_timeout_does_not_retry_or_mark_sent(self):
        item, lead = self.approved()
        self.queue(item, lead)
        with patch.object(outlook, "send", side_effect=RuntimeError("Timeout")) as send:
            outlook.tick(server, self.instant)
            outlook.tick(server, self.instant)
            self.assertEqual(send.call_count, 1)
        self.assertEqual(self.sql("SELECT state FROM outlook_queue")[0]["state"], "uncertain")
        self.assertEqual(self.sql("SELECT state FROM growth_items")[0]["state"], "approved")

    def test_daily_cap_counts_attempts(self):
        for index in range(6):
            self.queue(*self.approved(index))
        with patch.object(outlook, "send") as send:
            outlook.tick(server, self.instant)
            self.assertEqual(send.call_count, 5)
        self.assertEqual(len(self.sql("SELECT id FROM outlook_queue WHERE state='queued'")), 1)

    def test_rejected_lead_and_account_test_gate(self):
        item, lead = self.approved()
        self.account(tested=False)
        with self.assertRaises(ValueError):
            self.queue(item, lead)
        self.account()
        self.queue(item, lead)
        self.sql("UPDATE leads SET status='not_interested'")
        with patch.object(outlook, "send") as send:
            outlook.tick(server, self.instant)
            send.assert_not_called()
        self.assertEqual(self.sql("SELECT state FROM outlook_queue")[0]["state"], "cancelled")

    def test_oauth_browser_binding_pkce_sender_and_encryption(self):
        url, browser = outlook.begin(server)
        from urllib.parse import parse_qs, urlparse
        params = parse_qs(urlparse(url).query)
        self.assertEqual(params["code_challenge_method"], ["S256"])
        self.assertNotIn("test-secret", url)
        query = {"state": params["state"], "code": ["code"]}
        with patch.object(outlook, "http") as network:
            with self.assertRaises(ValueError):
                outlook.callback(server, query, "wrong-browser")
            network.assert_not_called()
        url, browser = outlook.begin(server)
        query["state"] = parse_qs(urlparse(url).query)["state"]
        with patch.object(outlook, "http", side_effect=[(200, {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 3600}), (200, {"mail": outlook.SENDER})]):
            outlook.callback(server, query, browser)
        stored = self.sql("SELECT * FROM outlook_account")[0]
        self.assertNotIn("new-refresh", stored["tokens"])
        self.assertEqual(stored["tested"], 0)
        self.assertEqual(outlook.access_token(server), "new-access")
        with closing(server.connect()) as db:
            public = outlook.status(db, server.run)
        self.assertNotIn("new-access", json.dumps(public))
        self.assertNotIn("tokens", public)

    def test_self_test_only_to_owner_and_restart_uncertainty(self):
        self.account(tested=False)
        with patch.object(outlook, "send") as send:
            outlook.test_email(server)
            self.assertEqual(send.call_args.args[1], outlook.SENDER)
        self.assertEqual(self.sql("SELECT tested FROM outlook_account")[0]["tested"], 1)
        self.sql("UPDATE outlook_queue SET state='sending'")
        outlook.recover(server)
        self.assertEqual(self.sql("SELECT state FROM outlook_queue")[0]["state"], "uncertain")

    def test_public_mode_rejects_connection_and_queue(self):
        with patch.object(server, "PUBLIC_NO_AUTH", True):
            with self.assertRaises(ValueError):
                outlook.begin(server)
            with self.assertRaises(ValueError):
                outlook.queue(server, {})

    def test_http_connect_requires_login_and_same_origin_and_sets_bound_cookie(self):
        def request(auth=True, origin="https://example.test"):
            handler = object.__new__(server.Handler)
            handler.path = "/api/outlook/connect"
            handler.headers = {"Content-Length": "2", "Host": "example.test", "Origin": origin}
            if auth:
                handler.headers["Authorization"] = "Basic " + base64.b64encode(b"owner:test-password").decode()
            handler.rfile, handler.wfile = io.BytesIO(b"{}"), io.BytesIO()
            headers = {}
            handler.send_response = lambda code: setattr(handler, "response_code", code)
            handler.send_header = lambda key, value: headers.update({key: value})
            handler.end_headers = lambda: None
            handler.do_POST()
            return handler.response_code, headers, handler.wfile.getvalue()
        self.assertEqual(request(auth=False)[0], 401)
        self.assertEqual(request(origin="https://evil.test")[0], 403)
        code, headers, body = request()
        self.assertEqual(code, 200)
        self.assertIn("SameSite=Lax", headers["Set-Cookie"])
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("code_challenge", json.loads(body)["url"])
        self.assertNotIn("test-secret", body.decode())

    def test_wrong_microsoft_account_cannot_replace_sender(self):
        from urllib.parse import parse_qs, urlparse
        url, browser = outlook.begin(server)
        query = {"state": parse_qs(urlparse(url).query)["state"], "code": ["code"]}
        with patch.object(outlook, "http", side_effect=[(200, {"access_token": "wrong-access", "refresh_token": "refresh"}), (200, {"mail": "someone@example.test"})]):
            with self.assertRaises(ValueError):
                outlook.callback(server, query, browser)
        self.assertEqual(outlook.access_token(server), "access-secret")

    def test_token_refresh_rotates_encrypted_refresh_token(self):
        tokens = {"access_token": "old", "refresh_token": "old-refresh", "expires_at": 0}
        self.sql("UPDATE outlook_account SET tokens=?", (outlook.cipher().encrypt(json.dumps(tokens).encode()).decode(),))
        with patch.object(outlook, "http", return_value=(200, {"access_token": "fresh", "refresh_token": "rotated", "expires_in": 3600})):
            self.assertEqual(outlook.access_token(server), "fresh")
        encrypted = self.sql("SELECT tokens FROM outlook_account")[0]["tokens"]
        self.assertNotIn("rotated", encrypted)
        self.assertEqual(json.loads(outlook.cipher().decrypt(encrypted.encode()))["refresh_token"], "rotated")


if __name__ == "__main__":
    unittest.main()
