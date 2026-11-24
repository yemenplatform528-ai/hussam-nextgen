from app.runner.redaction import safe_metadata, safe_json, redact_text


def test_redacts_secret_keys_recursively():
    result = safe_metadata({
        "api_key": "do-not-leak",
        "nested": {"Authorization": "Bearer abc.def.ghi", "message": "safe"},
    })
    rendered = safe_json(result)
    assert "do-not-leak" not in rendered
    assert "abc.def.ghi" not in rendered
    assert "[REDACTED]" in rendered
    assert "safe" in rendered


def test_redacts_bearer_and_database_url():
    raw = "Authorization: Bearer abc123 postgres://user:password@host/db"
    safe = redact_text(raw)
    assert "abc123" not in safe
    assert "user:password" not in safe
    assert "[REDACTED]" in safe


def test_bounds_nested_metadata():
    value = {"items": list(range(500))}
    safe = safe_metadata(value)
    assert len(safe["items"]) == 100
