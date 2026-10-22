#!/usr/bin/env bash
set -euo pipefail

# Destructive restore drill. Fail closed unless the operator explicitly attests
# that the target is isolated/disposable and its parsed identity differs.
: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_FILE:?BACKUP_FILE is required}"
: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is required before backup begins}"
: "${RESTORE_TARGET_DISPOSABLE:?Set RESTORE_TARGET_DISPOSABLE=YES only after independently verifying the target is isolated and disposable}"
if [[ "$RESTORE_TARGET_DISPOSABLE" != "YES" ]]; then
  echo "RESTORE_TARGET_DISPOSABLE must be exactly YES after independent target verification" >&2
  exit 2
fi

# pg_dump/libpq do not accept SQLAlchemy's postgresql+psycopg URI scheme.
case "$DATABASE_URL" in
  postgresql+psycopg://*) DATABASE_URL="postgresql://${DATABASE_URL#postgresql+psycopg://}" ;;
esac
case "$RESTORE_DATABASE_URL" in
  postgresql+psycopg://*) RESTORE_DATABASE_URL="postgresql://${RESTORE_DATABASE_URL#postgresql+psycopg://}" ;;
esac
case "$DATABASE_URL" in
  postgresql://*|postgres://*) ;;
  *) echo "DATABASE_URL must be a PostgreSQL libpq URI" >&2; exit 2 ;;
esac
case "$RESTORE_DATABASE_URL" in
  postgresql://*|postgres://*) ;;
  *) echo "RESTORE_DATABASE_URL must be a PostgreSQL libpq URI" >&2; exit 2 ;;
esac
export DATABASE_URL RESTORE_DATABASE_URL

command -v python3 >/dev/null || { echo "python3 is required for safe URI identity comparison" >&2; exit 2; }
command -v pg_dump >/dev/null || { echo "pg_dump is required" >&2; exit 2; }
command -v pg_restore >/dev/null || { echo "pg_restore is required" >&2; exit 2; }
command -v psql >/dev/null || { echo "psql is required" >&2; exit 2; }
command -v sha256sum >/dev/null || { echo "sha256sum is required" >&2; exit 2; }
command -v realpath >/dev/null || { echo "realpath is required" >&2; exit 2; }

# Compare host/port/database, not raw URLs (which may differ only by credentials,
# query order, encoding, or URI scheme). Never print either connection URL.
python3 - <<'PY'
import os
import sys
from urllib.parse import unquote, urlsplit

def identity(env_name):
    value = os.environ[env_name]
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").lower()
        port = parsed.port or 5432
        database = unquote(parsed.path.lstrip("/"))
    except ValueError:
        raise SystemExit(f"{env_name} has an invalid PostgreSQL URI")
    if not host or not database:
        raise SystemExit(f"{env_name} must include a host and database name")
    return host, port, database

source = identity("DATABASE_URL")
target = identity("RESTORE_DATABASE_URL")
if source == target:
    raise SystemExit("Source and restore target resolve to the same parsed host/port/database identity")
print("Source/target URI identity check: distinct host/port/database tuple (operator must still verify target isolation).")
PY

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null || true)"
BACKUP_ABS="$(realpath -m -- "$BACKUP_FILE")"
if [[ -n "$REPO_ROOT" && ( "$BACKUP_ABS" == "$REPO_ROOT" || "$BACKUP_ABS" == "$REPO_ROOT/"* ) ]]; then
  echo "BACKUP_FILE must be outside the repository" >&2
  exit 2
fi

mkdir -p "$(dirname "$BACKUP_ABS")"
echo "[backup] creating custom-format backup"
pg_dump --format=custom --no-owner --file="$BACKUP_ABS" "$DATABASE_URL"
echo "[backup] verifying archive"
pg_restore --list "$BACKUP_ABS" >/dev/null
BACKUP_SHA256="$(sha256sum "$BACKUP_ABS" | awk '{print $1}')"
BACKUP_SIZE_BYTES="$(stat -c '%s' "$BACKUP_ABS")"
printf 'BACKUP_SHA256=%s\nBACKUP_SIZE_BYTES=%s\n' "$BACKUP_SHA256" "$BACKUP_SIZE_BYTES"

echo "[restore] restoring only to the explicitly attested disposable target"
pg_restore --clean --if-exists --no-owner --dbname="$RESTORE_DATABASE_URL" "$BACKUP_ABS"
psql "$RESTORE_DATABASE_URL" -v ON_ERROR_STOP=1 -c 'SELECT 1;' >/dev/null
if [[ -n "${EXPECTED_ALEMBIC_REVISION:-}" ]]; then
  command -v alembic >/dev/null || { echo "alembic is required when EXPECTED_ALEMBIC_REVISION is set" >&2; exit 2; }
  DATABASE_URL="$RESTORE_DATABASE_URL" alembic current | grep -F -- "$EXPECTED_ALEMBIC_REVISION" >/dev/null || {
    echo "restore target is not at expected Alembic revision: $EXPECTED_ALEMBIC_REVISION" >&2
    exit 1
  }
fi
echo "BACKUP_RESTORE_DRILL=PASS"
