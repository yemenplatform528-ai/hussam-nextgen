#!/bin/sh
set -eu

# Render Free supplies the listening port through PORT.  Apply idempotent
# migrations before starting the API so the staging service is self-contained.
alembic upgrade head
exec uvicorn app.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
