import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import render_operator_audit as audit


class RenderOperatorAuditTests(unittest.TestCase):
    def test_missing_key_is_blocked_without_request(self):
        with patch.dict(os.environ, {"RENDER_API_KEY": ""}, clear=False):
            with self.assertRaisesRegex(audit.RenderAPIError, "not configured"):
                audit.get_json("/services")

    def test_error_does_not_expose_response_body_or_token(self):
        error = HTTPError(
            "https://api.render.com/v1/services", 403, "Forbidden", {}, None
        )
        error.read = lambda: b"secret-like-provider-response"
        with patch.dict(os.environ, {"RENDER_API_KEY": "test-token"}), patch(
            "urllib.request.urlopen", side_effect=error
        ):
            with self.assertRaises(audit.RenderAPIError) as caught:
                audit.get_json("/services")
        self.assertNotIn("secret-like-provider-response", str(caught.exception))
        self.assertNotIn("test-token", str(caught.exception))

    def test_owner_id_supports_render_resource_shapes(self):
        self.assertEqual(audit.owner_id({"ownerId": "workspace-a"}), "workspace-a")
        self.assertEqual(audit.owner_id({"owner": {"id": "workspace-b"}}), "workspace-b")
        self.assertIsNone(audit.owner_id({"name": "no-owner-field"}))

    def test_pick_only_returns_explicit_safe_fields(self):
        value = audit.pick(
            {"id": "srv-1", "name": "service", "envVars": [{"key": "TOKEN", "value": "do-not-leak"}]},
            "id", "name",
        )
        self.assertEqual(value, {"id": "srv-1", "name": "service"})
        self.assertNotIn("do-not-leak", json.dumps(value))

    def test_unwrap_handles_render_owner_and_resource_envelopes(self):
        self.assertEqual(audit.unwrap({"cursor": "c", "owner": {"id": "tea-1"}}), {"id": "tea-1"})
        self.assertEqual(audit.unwrap({"cursor": "c", "service": {"id": "srv-1"}}), {"id": "srv-1"})
        self.assertEqual(audit.unwrap({"id": "plain"}), {"id": "plain"})

    def test_list_pages_uses_sibling_cursor_and_marks_page_cap(self):
        page_one = [{"cursor": "cursor-1", "owner": {"id": "one"}}]
        with patch.object(audit, "MAX_PAGES", 1), patch.object(
            audit, "get_json", return_value=page_one
        ) as get_json:
            rows, truncated = audit.list_pages("/owners")
        self.assertEqual(rows, [{"id": "one"}])
        self.assertTrue(truncated)
        self.assertEqual(get_json.call_args.args[1], {"limit": audit.PAGE_SIZE})


if __name__ == "__main__":
    unittest.main()
