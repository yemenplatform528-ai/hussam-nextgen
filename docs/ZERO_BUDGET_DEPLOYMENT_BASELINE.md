# Hussam NextGen — Zero-Budget Deployment Baseline

## Purpose

This document defines the first public deployment path without changing Marketplace, AI, or HUS authority boundaries.

## Deployment roles

- GitHub: source of truth and CI.
- Render Free: public staging/demo API and the bundled `/console` UI.
- Neon Free: durable PostgreSQL database.
- Cloudflare Pages: optional split frontend target after the API URL is known and CORS/OIDC redirect configuration is explicitly provisioned.

Render Free is a staging/demo target only. Render documents Free services as suitable for testing, hobby projects and previews, not production applications. Free web services also sleep after inactivity and use an ephemeral filesystem, so SQLite/local files are not a persistence strategy. Use Neon for relational persistence.

## Render contract

The container receives `PORT` from Render. `scripts/render_start.sh` runs `alembic upgrade head` and then starts Uvicorn on `0.0.0.0:${PORT}`.

Required secret/runtime variables:

- `DATABASE_URL` — Neon PostgreSQL URL.
- `JWT_SECRET` — random secret, at least 32 characters.
- `ENVIRONMENT=staging`.
- `RATE_LIMIT_EDGE_ENFORCED=true`.
- `OIDC_CLIENT_ID`.
- `OIDC_ISSUER` (HTTPS).
- `OIDC_CLIENT_SECRET`.
- `OIDC_REDIRECT_URI` (HTTPS, exact provider callback).
- `OIDC_STATE_SECRET` (at least 32 characters).

No secret is stored in the repository.

## First deployment order

1. Create the Neon Free PostgreSQL project.
2. Apply the current migrations against that database.
3. Create the Render web service from `render.yaml`.
4. Add the required runtime secrets in Render.
5. Deploy and verify `/health` and `/ready`.
6. Open `/console/` from the Render service URL.
7. Keep payment, legal/compliance, backup/restore and production certification gates closed until their external evidence exists.

## Production boundary

A successful Render/Neon staging deployment is not a production certification result. The external production evidence register remains the authority for closure.
