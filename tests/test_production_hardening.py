import os
from app.core.security.production import ProductionConfigError, ProductionSettings
from fastapi.testclient import TestClient
from app.api.main import app


def test_production_config_fails_closed_on_missing_values(monkeypatch):
    for key in ("DATABASE_URL", "JWT_SECRET", "OIDC_CLIENT_ID", "OIDC_ISSUER", "OIDC_CLIENT_SECRET", "OIDC_REDIRECT_URI", "OIDC_STATE_SECRET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    try:
        ProductionSettings.from_env()
        assert False, "expected production config failure"
    except ProductionConfigError as exc:
        assert "DATABASE_URL" in str(exc)


def test_production_config_accepts_postgres_and_required_identity(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/app")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("OIDC_CLIENT_ID", "client")
    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "https://app.example.com/api/v1/auth/oidc/callback")
    monkeypatch.setenv("OIDC_STATE_SECRET", "s" * 32)
    monkeypatch.setenv("RATE_LIMIT_EDGE_ENFORCED", "true")
    settings = ProductionSettings.from_env()
    assert settings.environment == "production"


def test_health_security_headers_and_readiness(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/app")
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.headers["X-Content-Type-Options"] == "nosniff"
    assert health.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" in health.headers
    ready = client.get("/ready?deep=false")
    assert ready.status_code == 200
    assert ready.json()["database_configured"] is True


def test_readiness_deep_uses_database_probe(monkeypatch):
    class DummyConnection:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, statement):
            assert str(statement) == "SELECT 1"

    class DummyEngine:
        def connect(self): return DummyConnection()
        def dispose(self): pass

    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/app")
    import app.api.main as main
    monkeypatch.setattr(main, "create_engine", lambda *args, **kwargs: DummyEngine())
    client = TestClient(main.app)
    response = client.get("/ready?deep=true")
    assert response.status_code == 200
    assert response.json()["database_reachable"] is True


def test_api_rate_limit_returns_429(monkeypatch):
    import app.api.main as main
    main._rate_limit.limit = 1
    main._rate_limit.reset()
    client = TestClient(main.app)
    first = client.get("/api/v1/platform/manifest")
    second = client.get("/api/v1/platform/manifest")
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["Retry-After"]
    main._rate_limit.limit = 600
    main._rate_limit.reset()

def test_production_settings_requires_distributed_rate_limit_in_staging(monkeypatch):
    from app.core.security.production import ProductionConfigError, ProductionSettings
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("OIDC_CLIENT_ID", "client")
    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret")
    monkeypatch.setenv("OIDC_REDIRECT_URI", "https://app.example.com/api/v1/auth/oidc/callback")
    monkeypatch.setenv("OIDC_STATE_SECRET", "s" * 32)
    monkeypatch.delenv("RATE_LIMIT_EDGE_ENFORCED", raising=False)
    try:
        ProductionSettings.from_env(strict=True)
    except ProductionConfigError as exc:
        assert "RATE_LIMIT_EDGE_ENFORCED" in str(exc)
    else:
        raise AssertionError("staging must require distributed rate-limit enforcement")
