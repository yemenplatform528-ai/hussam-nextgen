from __future__ import annotations

import os
import uuid
from datetime import timedelta

import psycopg
import pytest

from app.runner.scheduler import PostgresScheduler

DB_URL = os.getenv("RUNNER_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="isolated runner PostgreSQL is not configured")


@pytest.fixture
def db():
    connection = psycopg.connect(DB_URL)
    try:
        yield connection
    finally:
        connection.close()


def test_due_schedule_materializes_once_and_advances(db):
    # Reuse the shared db fixture from test_postgres_queue.
    tenant = uuid.uuid4().int % 2_000_000_000 + 1
    schedule_id = uuid.uuid4()
    with db.transaction():
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        due = db.execute("SELECT now() - interval '1 minute'").fetchone()[0]
        db.execute(
            """INSERT INTO hussam_runner_v1.schedules
               (id,tenant_id,task_type,payload,cron_expression,timezone,next_run_at,misfire_policy)
               VALUES (%s,%s,'demo','{}'::jsonb,'* * * * *','UTC',%s,'catch_up')""",
            (schedule_id,tenant,due),
        )

    def next_occurrence(expression, timezone_name, after):
        return after + timedelta(minutes=1)

    scheduler = PostgresScheduler(db, next_occurrence=next_occurrence)
    assert scheduler.materialize_due(tenant_id=tenant) == 1
    assert scheduler.materialize_due(tenant_id=tenant) == 0
    with db.transaction():
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        rows = db.execute(
            "SELECT count(*) FROM hussam_runner_v1.schedule_occurrences WHERE schedule_id=%s",
            (schedule_id,),
        ).fetchone()[0]
        tasks = db.execute(
            "SELECT count(*) FROM hussam_runner_v1.tasks WHERE tenant_id=%s AND task_type='demo'",
            (tenant,),
        ).fetchone()[0]
    assert rows == 1
    assert tasks == 1
