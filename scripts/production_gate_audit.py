#!/usr/bin/env python3
"""Machine-check production configuration without pretending external evidence exists."""
import os

checks = {
    "production_database": bool(os.getenv("DATABASE_URL", "").startswith(("postgresql://", "postgresql+psycopg://", "postgres://"))),
    "jwt_secret": len(os.getenv("JWT_SECRET", "")) >= 32,
    "oidc": all(os.getenv(k, "").strip() for k in ("OIDC_CLIENT_ID", "OIDC_ISSUER", "OIDC_CLIENT_SECRET")),
    "https_intent": os.getenv("ENVIRONMENT", "development").lower() not in {"production", "staging"} or os.getenv("REQUIRE_HTTPS", "true").lower() in {"1", "true", "yes"},
}
for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'PENDING_EXTERNAL_CONFIGURATION'}")
print("External evidence still required: payment providers, accounting, carriers, browser/mobile E2E, security assessment, backup/restore, observability, operations, legal/compliance.")
