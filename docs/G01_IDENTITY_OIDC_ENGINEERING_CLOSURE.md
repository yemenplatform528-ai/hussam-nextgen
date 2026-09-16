# G01 — Identity / OIDC Engineering Closure

## Status

**ENGINEERING_READY** — production certification is **not closed**.

The repository now contains a provider-neutral OpenID Connect authorization-code boundary. It is intentionally separate from the Sovereign Core authorization authority.

## Implemented

- OpenID Connect discovery from the configured issuer.
- Authorization Code redirect with `state` and `nonce`.
- Signed, short-lived state validation and browser state cookie.
- Authorization-code token exchange without exposing the client secret to the browser.
- ID-token validation against issuer, audience, expiry, nonce, and provider JWKS.
- Verified-email requirement.
- Explicit issuer+subject identity binding in `oidc_identities`.
- Existing local user and active tenant membership remain the authorization authority.
- No automatic user creation, tenant creation, or privilege elevation from OIDC claims.
- If a provisioned OIDC identity has multiple active tenant memberships, the callback fails closed with `409` and requires explicit tenant selection; it never silently selects a tenant.
- Local API session is issued as an HttpOnly cookie after successful OIDC authentication.
- Existing Bearer JWT authentication remains supported for controlled/legacy clients.
- OIDC logout removes the local session cookie.
- Production configuration now requires HTTPS OIDC issuer/redirect URI and a dedicated state-signing secret.
- Database migration `0002_oidc_identity_binding` adds the provider-neutral identity binding table.

## Verification performed

- Full automated test suite: **181 passed**.
- Python compile check: passed.
- Alembic upgrade from an empty SQLite database: passed.
- `alembic check`: passed with no pending operations.
- `scripts/baseline_audit.py`: passed with zero failures and zero warnings.
- OIDC state signature/expiry tests: passed.
- Production OIDC configuration tests: passed.

## What this does not prove

This engineering closure does **not** close the production gate.

The following external evidence is still required:

1. Real production/staging Identity Provider issuer metadata.
2. Real client registration and redirect URI approval.
3. Secret-manager reference proving secure secret injection.
4. A real browser login using the configured provider.
5. Successful callback, ID-token validation, local session creation and logout.
6. Tenant authorization evidence for the real provisioned identity.
7. Session-refresh evidence where the selected provider requires it.
8. Captured external artifact with SHA-256 and reviewer decision.

Until those artifacts exist and pass the repository Evidence Protocol validator, G01 remains **PENDING_EXTERNAL**.

## Scope boundary

G02–G10 were not started by this closure work.

No Yemen-specific payment, logistics, currency, or provider implementation was added.
