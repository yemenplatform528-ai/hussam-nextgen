import json
import os
import unittest
from unittest.mock import patch

from scripts import render_operator_audit as audit


class RenderOperatorAuditTests(unittest.TestCase):
    def test_missing_key_is_blocked_without_request(self):
        with patch.dict(os.environ, {"RENDER_API_KEY": ""}, clear=False):
            with self.assertRaisesRegex(audit.RenderAPIError, "not configured"):
                audit.get_json("/services")

    def test_error_does_not_expose_response_body(self):
        class FakeHTTPError(Exception):
            code = 403
        err = FakeHTTPError()
        err.read = lambda: b"secret-like-provider-response"
        with patch.dict(os.environ, {"RENDER_API_KEY": "test-token"}), patch(
            "urllib.request.urlopen", side_effect=__import__("urllib.error").error.HTTPError(
                "https://api.render.com/v1/services", 403, "Forbidden", {}, None
            )
        ):
            with self.assertRaises(audit.RenderAPIError) as caught:
                audit.get_json("/services")
        self.assertNotIn("secret-like-provider-response", str(caught.exception))
        self.assertNotIn("test-token", str(caught.exception))

    def test_pick_only_returns_explicit_safe_fields(self):
        value = audit.pick({"id": "srv-1", "name": "service", "envVars": [{"key": "TOKEN", "value": "do-not-leak"}]}, "id", "name")
        self.assertEqual(value, {"id": "srv-1", "name": "service"})
        self.assertNotIn("do-not-leak", json.dumps(value))


if __name__ == "__main__":
    unittest.main()
