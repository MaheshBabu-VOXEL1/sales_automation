"""Setup guidance must not imply that missing business data is ready."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

import server


class WorkflowSetupTest(unittest.TestCase):
    def evaluate(self, script):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is not installed")
        source = (Path(server.ROOT) / "web/app.js").read_text(encoding="utf-8")
        functions = source[source.index("function setupChecks("):source.index("function workflowSetup(")]
        result = subprocess.run([node, "-e", functions + script], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_missing_setup_and_zero_targets_are_explicit(self):
        rows = self.evaluate("console.log(JSON.stringify(setupChecks({full_rhythm:true,content_targets:{LinkedIn:0}}, {searches_used:5,limits:{searches:5,gemini:100},used:{gemini:75},held:{gemini:0}}, {awaiting_approval:13}, false)));")
        self.assertTrue(any("Research blocked" in r for r in rows))
        self.assertTrue(any("New discovery blocked" in r for r in rows))
        self.assertTrue(any("Partner activity" in r for r in rows))
        self.assertTrue(any("Client activity" in r for r in rows))
        self.assertTrue(any("Social drafts disabled" in r for r in rows))
        self.assertTrue(any("Public proof unavailable" in r for r in rows))
        self.assertTrue(any("13 website-derived" in r for r in rows))
        self.assertFalse(any("New AI drafts blocked" in r for r in rows))

    def test_configured_fields_do_not_keep_missing_input_warnings(self):
        rows = self.evaluate("console.log(JSON.stringify(setupChecks({full_rhythm:true,partner_accounts:'Partner',existing_clients:'Client',content_targets:{LinkedIn:1},proof_consent:true,approved_proof:'Approved fact'},null,{awaiting_approval:0},true)));")
        self.assertEqual(rows, [])

    def test_disabled_partner_is_not_a_missing_requirement(self):
        rows = self.evaluate("console.log(JSON.stringify(setupChecks({full_rhythm:true,partner_enabled:false},null,null,true)));")
        self.assertFalse(any("Partner activity" in r for r in rows))

    def test_held_requests_also_block_new_drafts(self):
        rows = self.evaluate("console.log(JSON.stringify(setupChecks({}, {searches_used:0,limits:{searches:5,gemini:100},used:{gemini:99},held:{gemini:1}},null,true)));")
        self.assertTrue(any("New AI drafts blocked" in r for r in rows))

    def test_no_campaign_needs_goal_instead_of_claiming_scheduled_work(self):
        rows = self.evaluate("console.log(JSON.stringify(setupChecks(null,null,null,false)));")
        self.assertEqual(rows, ["Set a Sales Goal before scheduling this workspace."])
