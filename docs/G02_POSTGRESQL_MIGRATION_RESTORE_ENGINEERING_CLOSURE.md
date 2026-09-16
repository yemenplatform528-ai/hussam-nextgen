# G02 — PostgreSQL / Migration / Restore Engineering Closure

## Status

**ENGINEERING_READY** — production certification is **not closed**.

The repository contains the PostgreSQL production configuration contract, Alembic migration chain, readiness probe, and a controlled backup/restore drill. No production database or restore evidence is claimed by this document.

## Engineering controls verified

- Production and staging configuration require a PostgreSQL-compatible `DATABASE_URL`.
- PostgreSQL URLs normalize to the `psycopg` SQLAlchemy driver.
- Alembic has one canonical baseline migration followed by the OIDC identity-binding migration.
- Fresh-database migration was verified on SQLite as a schema/migration contract check; this does **not** substitute for PostgreSQL certification.
- `alembic check` passes with no pending schema operations.
- Application readiness exposes database configuration and performs a deep `SELECT 1` connectivity probe.
- Backup/restore is isolated in `scripts/postgres_backup_restore_drill.sh` and requires explicit PostgreSQL source and restore targets.
- The restore target must be explicitly supplied and must not equal the source database URL.
- The drill uses PostgreSQL custom-format backup plus `pg_restore`, then verifies database connectivity.

## External evidence still required

1. Real staging/production PostgreSQL instance.
2. Real Alembic upgrade from the deployed starting revision to the deployed head.
3. Real backup artifact and archive listing.
4. Restore into an isolated PostgreSQL target.
5. Post-restore schema/application verification.
6. Restore timing and operator record where required by the environment.
7. External artifact SHA-256 and reviewer decision.
8. Evidence Protocol validation before G02 can become **CLOSED**.

## Boundary

This closure does not claim PostgreSQL availability, backup success, restore success, RPO/RTO compliance, or production database certification. Those require real external evidence.
