#!/usr/bin/env bash
set -euo pipefail

python scripts/baseline_audit.py
python scripts/artifact_manifest.py . /tmp/hussam-release-manifest.json
python -m compileall -q app alembic tests
python -m pytest -q
rm -f /tmp/hussam-nextgen-v130-release.db
DATABASE_URL=sqlite:////tmp/hussam-nextgen-v130-release.db alembic upgrade head
DATABASE_URL=sqlite:////tmp/hussam-nextgen-v130-release.db alembic check
