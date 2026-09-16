# Contributing to Hussam NextGen

## Rules

1. Preserve the architecture dependency direction: `domain → shared engine → Sovereign Core`.
2. Do not create a second source of truth for finance, inventory, payments, identity, or audit.
3. Use Decimal/Numeric for money; never introduce binary floating point for monetary authority.
4. Every tenant-scoped mutation must enforce authenticated active membership and object ownership/authorization as appropriate.
5. Mutations that can be retried must have explicit idempotency semantics.
6. AI proposals are advisory/control-plane inputs and must pass normal authorization/policy/audit boundaries.
7. Add tests for every invariant and every cross-tenant boundary.
8. Database changes require an Alembic migration and a fresh upgrade test.
9. Do not commit `.env`, credentials, database files, logs, caches, virtual environments, or generated build artifacts.

## Required local checks

```text
python scripts/baseline_audit.py
python -m compileall -q app alembic tests
python -m pytest -q
DATABASE_URL=sqlite:////tmp/hussam-nextgen-v130-migration.db alembic upgrade head
DATABASE_URL=sqlite:////tmp/hussam-nextgen-v130-migration.db alembic check
```

PostgreSQL integration is a required production gate and should also be exercised in CI when a PostgreSQL service is available.
