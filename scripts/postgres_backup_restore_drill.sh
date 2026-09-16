#!/usr/bin/env bash
set -euo pipefail
# External production drill: never run against an unknown database.
: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_FILE:?BACKUP_FILE is required}"

case "$DATABASE_URL" in
  postgresql://*|postgres://*|postgresql+psycopg://*) ;;
  *) echo "DATABASE_URL must be PostgreSQL" >&2; exit 2 ;;
esac

command -v pg_dump >/dev/null || { echo "pg_dump is required" >&2; exit 2; }
command -v pg_restore >/dev/null || { echo "pg_restore is required" >&2; exit 2; }

mkdir -p "$(dirname "$BACKUP_FILE")"
echo "[backup] creating custom-format backup"
pg_dump --format=custom --no-owner --file="$BACKUP_FILE" "$DATABASE_URL"
echo "[backup] verifying archive"
pg_restore --list "$BACKUP_FILE" >/dev/null
echo "[restore] DRILL ONLY: provide RESTORE_DATABASE_URL explicitly"
: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is required for restore phase}"
if [ "$DATABASE_URL" = "$RESTORE_DATABASE_URL" ]; then
  echo "RESTORE_DATABASE_URL must point to a distinct restore target" >&2
  exit 2
fi
case "$RESTORE_DATABASE_URL" in
  postgresql://*|postgres://*|postgresql+psycopg://*) ;;
  *) echo "RESTORE_DATABASE_URL must be PostgreSQL" >&2; exit 2 ;;
esac
pg_restore --clean --if-exists --no-owner --dbname="$RESTORE_DATABASE_URL" "$BACKUP_FILE"
psql "$RESTORE_DATABASE_URL" -v ON_ERROR_STOP=1 -c 'SELECT 1;' >/dev/null
if [ -n "${EXPECTED_ALEMBIC_REVISION:-}" ]; then
  command -v alembic >/dev/null || { echo "alembic is required when EXPECTED_ALEMBIC_REVISION is set" >&2; exit 2; }
  DATABASE_URL="$RESTORE_DATABASE_URL" alembic current | grep -F "${EXPECTED_ALEMBIC_REVISION}" >/dev/null || {
    echo "restore target is not at expected Alembic revision: ${EXPECTED_ALEMBIC_REVISION}" >&2
    exit 1
  }
fi
echo "BACKUP_RESTORE_DRILL=PASS"
