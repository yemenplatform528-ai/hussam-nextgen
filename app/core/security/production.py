import os
from dataclasses import dataclass

class ProductionConfigError(RuntimeError):
    pass

@dataclass(frozen=True)
class ProductionSettings:
    environment: str
    database_url: str
    jwt_secret: str
    oidc_client_id: str
    oidc_issuer: str
    oidc_client_secret: str
    oidc_redirect_uri: str
    oidc_state_secret: str
    require_https: bool = True
    rate_limit_edge_enforced: bool = False
    rate_limit_backend: str = "memory"
    rate_limit_redis_url: str = ""

    @classmethod
    def from_env(cls, *, strict: bool = True) -> "ProductionSettings":
        env = os.getenv("ENVIRONMENT", "development").strip().lower()
        db = os.getenv("DATABASE_URL", "").strip()
        jwt = os.getenv("JWT_SECRET", "")
        oidc_id = os.getenv("OIDC_CLIENT_ID", "").strip()
        oidc_issuer = os.getenv("OIDC_ISSUER", "").strip()
        oidc_secret = os.getenv("OIDC_CLIENT_SECRET", "")
        oidc_redirect_uri = os.getenv("OIDC_REDIRECT_URI", "").strip()
        oidc_state_secret = os.getenv("OIDC_STATE_SECRET", "")
        rate_limit_edge = os.getenv("RATE_LIMIT_EDGE_ENFORCED", "false").strip().lower() in {"1", "true", "yes"}
        rate_limit_backend = os.getenv("RATE_LIMIT_BACKEND", "memory").strip().lower()
        rate_limit_redis_url = os.getenv("RATE_LIMIT_REDIS_URL", "").strip()
        if strict and env in {"production", "staging"}:
            missing = [name for name, value in {
                "DATABASE_URL": db,
                "JWT_SECRET": jwt,
                "OIDC_CLIENT_ID": oidc_id,
                "OIDC_ISSUER": oidc_issuer,
                "OIDC_CLIENT_SECRET": oidc_secret,
                "OIDC_REDIRECT_URI": oidc_redirect_uri,
                "OIDC_STATE_SECRET": oidc_state_secret,
            }.items() if not value]
            if missing:
                raise ProductionConfigError("missing production configuration: " + ", ".join(missing))
            if len(oidc_state_secret) < 32:
                raise ProductionConfigError("OIDC_STATE_SECRET must be at least 32 characters")
            if not oidc_issuer.startswith("https://"):
                raise ProductionConfigError("production OIDC_ISSUER must use HTTPS")
            if not oidc_redirect_uri.startswith("https://"):
                raise ProductionConfigError("production OIDC_REDIRECT_URI must use HTTPS")
            if len(jwt) < 32:
                raise ProductionConfigError("JWT_SECRET must be at least 32 characters")
            if not db.startswith(("postgresql://", "postgres://", "postgresql+psycopg://")):
                raise ProductionConfigError("production DATABASE_URL must use PostgreSQL")
            if rate_limit_backend not in {"redis", "edge"} and not rate_limit_edge:
                raise ProductionConfigError("production requires distributed rate limiting: RATE_LIMIT_BACKEND=redis or RATE_LIMIT_EDGE_ENFORCED=true")
            if rate_limit_backend == "redis" and not rate_limit_redis_url:
                raise ProductionConfigError("RATE_LIMIT_REDIS_URL is required when RATE_LIMIT_BACKEND=redis")
        return cls(env, db, jwt, oidc_id, oidc_issuer, oidc_secret, oidc_redirect_uri, oidc_state_secret, True, rate_limit_edge, rate_limit_backend, rate_limit_redis_url)
