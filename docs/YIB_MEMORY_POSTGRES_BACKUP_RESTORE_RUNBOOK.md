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
5. Write a custom-format `pg_dump` archive to protected storage outside both the repository and the database provider. Verify it with `pg_restore --list`, then compute SHA-256 and record size/time.
6. Restore only to a distinct, isolated, disposable database. The existing `scripts/postgres_backup_restore_drill.sh` uses `pg_restore --clean --if-exists`; inspect its credential handling before use and never point the restore target at production.
7. Validate connectivity, schema/migration revision, and safe integrity invariants. Archive listing alone is not a successful restore.
8. Remove any temporary allowlist entry and read back the final allowlist state.

## Stop conditions

Stop if the database identity is ambiguous, credentials cannot be accessed through an authorized secret mechanism, egress is unstable, the restore target is not isolated, storage is not protected, or tooling fails. Never delete or modify production data to work around a failed drill.

## Evidence to record

UTC timestamp; Render resource ID/status/expiry; tool versions; authorized host and access method (no credentials); backup file size and SHA-256; archive verification result; isolated restore target identity; restore validation and duration; confirmation temporary access was removed; outcome `PASS` / `FAIL` / `BLOCKED`; next action.


## Script-specific safety review

The repository script `scripts/postgres_backup_restore_drill.sh` was inspected. It requires `DATABASE_URL`, `BACKUP_FILE`, `RESTORE_DATABASE_URL`, `pg_dump`, and `pg_restore`; it creates a custom-format archive, verifies that the archive can be listed, then performs `pg_restore --clean --if-exists` against the supplied target and checks `SELECT 1`.

**Important limitation:** the script's source/target guard compares the raw connection URL strings only. It does not prove that two differently formatted URLs identify different databases, and it does not calculate a checksum or compare source/restore database identity. Therefore do not use it against any valuable target until the operator independently confirms that the restore target is isolated and disposable. After backup, calculate SHA-256 and file size separately. A successful `pg_restore --list` alone is not proof of a successful restore or correct target isolation.
