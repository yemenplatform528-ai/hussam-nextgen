# YIB Memory PostgreSQL — Backup and Restore Runbook

**Status:** BLOCKED pending permitted database access. Last checked: 2026-10-22. No successful export or restore is evidenced.

## Current state

- Render resource: `yib-world-independent-memory` (`dpg-db3v8m942hec73f6k260-a`).
- Reported state: available, Free plan, PostgreSQL 18, Frankfurt.
- Recorded expiry: `2026-11-07T19:51:53.875885Z`; re-check before relying on it.
- The database IP allowlist is empty; the connected query tool cannot connect.
- The online Codespace does not have `pg_dump`, `pg_restore`, or `psql` installed.
- No allowlist change, query, export, restore, or billing change was performed.

## Safest next path

1. Prefer an owner-authorized host already permitted to connect. Otherwise, obtain explicit owner approval for a narrowly scoped temporary allowlist entry on a trusted host with confirmed stable egress. A Codespace egress IP can change; do not assume it is static.
2. Re-check database identity and expiry in Render immediately before starting. Do not upgrade or pay as a workaround.
3. Obtain the external database URL only through authorized host settings. Never paste or echo connection credentials in chat, tickets, commits, shell history, or logs.
4. Use PostgreSQL client tools on the authorized host. Keep credentials out of command output and shell tracing.
5. Write a custom-format `pg_dump` archive to protected storage outside both the repository and the database provider. Verify it with `pg_restore --list`; the hardened script prints the SHA-256 and byte size for the archive.
6. Restore only to a distinct, isolated, disposable database. The script requires `RESTORE_TARGET_DISPOSABLE=YES`, compares parsed host/port/database identities (not raw URL strings), rejects archive paths inside the repository, and uses destructive `pg_restore --clean --if-exists` only after preflight checks. The operator must independently verify the restore target is isolated and disposable before setting the attestation.
7. Validate connectivity, schema/migration revision, and safe integrity invariants. Archive listing alone is not a successful restore.
8. Remove any temporary allowlist entry and read back the final allowlist state.

## Stop conditions

Stop if the database identity is ambiguous, credentials cannot be accessed through an authorized secret mechanism, egress is unstable, the restore target is not isolated, storage is not protected, or tooling fails. Never delete or modify production data to work around a failed drill.

## Evidence to record

UTC timestamp; Render resource ID/status/expiry; tool versions; authorized host and access method (no credentials); backup file size and SHA-256; archive verification result; isolated restore target identity; restore validation and duration; confirmation temporary access was removed; outcome `PASS` / `FAIL` / `BLOCKED`; next action.


## Script-specific safety review

The repository script `scripts/postgres_backup_restore_drill.sh` requires `DATABASE_URL`, `BACKUP_FILE`, `RESTORE_DATABASE_URL`, `RESTORE_TARGET_DISPOSABLE=YES`, and the required PostgreSQL/checksum utilities. It normalizes SQLAlchemy's `postgresql+psycopg://` scheme for libpq tools, compares parsed source/target host/port/database identities before touching the source, rejects a backup path inside the repository, creates and verifies a custom-format archive, prints its SHA-256 and byte size, then performs `pg_restore --clean --if-exists` against the attested target and checks `SELECT 1`.

**Safety boundary:** the script compares parsed host/port/database identity and records the backup SHA-256 and size. It requires an explicit `RESTORE_TARGET_DISPOSABLE=YES` attestation and keeps the archive outside the repository. These checks reduce accidental misuse but cannot prove that DNS aliases or separate endpoints are not the same underlying database. The operator must independently verify target isolation before setting the attestation. A successful `pg_restore --list` alone is not proof of a successful restore; the script continues with an actual restore and a connectivity check only after all preflight gates pass.
