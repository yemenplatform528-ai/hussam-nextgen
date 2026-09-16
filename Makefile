.PHONY: test compile migrate-check baseline

PYTHON ?= python

test:
	$(PYTHON) -m pytest -q

compile:
	$(PYTHON) -m compileall -q app alembic tests

migrate-check:
	DATABASE_URL=sqlite:////tmp/hussam-nextgen-v130-migration.db alembic upgrade head
	DATABASE_URL=sqlite:////tmp/hussam-nextgen-v130-migration.db alembic check

baseline:
	$(PYTHON) scripts/baseline_audit.py
