from __future__ import annotations

import os
import uuid

import psycopg
import pytest

from app.runner.postgres import LeaseLost, PostgresQueue

DB_URL = os.getenv("RUNNER_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="isolated runner PostgreSQL is not configured")


@pytest.fixture
def db():
    connection = psycopg.connect(DB_URL)
    try:
        yield connection
    finally:
        connection.close()


def tenant_id() -> int:
    return uuid.uuid4().int % 2_000_000_000 + 1


def expire_lease(db, task_id, tenant):
    with db.transaction():
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        db.execute(
            """UPDATE hussam_runner_v1.tasks
               SET lease_expires_at=now()-interval '1 second'
               WHERE id=%s AND tenant_id=%s""",
            (task_id, tenant),
        )


def test_enqueue_is_idempotent_and_tenant_scoped(db):
    queue = PostgresQueue(db)
    tenant = tenant_id()
    key = str(uuid.uuid4())
    first = queue.enqueue(tenant_id=tenant, task_type="demo", payload={"x": 1},
                          idempotency_key=key)
    second = queue.enqueue(tenant_id=tenant, task_type="demo", payload={"x": 2},
                           idempotency_key=key)
    assert first == second
    assert queue.claim(tenant_id=tenant + 1, worker_id="other") is None
    claimed = queue.claim(tenant_id=tenant, worker_id="worker-a")
    assert claimed and claimed["id"] == first
    queue.complete(claimed)


def test_checkpoint_and_audit_are_persisted(db):
    queue = PostgresQueue(db)
    tenant = tenant_id()
    task_id = queue.enqueue(tenant_id=tenant, task_type="demo",
                            payload={"password": "must-not-persist"},
                            idempotency_key=str(uuid.uuid4()))
    task = queue.claim(tenant_id=tenant, worker_id="worker-b")
    assert task and task["id"] == task_id
    assert queue.checkpoint(task, {"cursor": 7, "api_key": "do-not-store"}) == 1
    queue.complete(task)
    with db.transaction():
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        checkpoint = db.execute(
            "SELECT payload::text FROM hussam_runner_v1.checkpoints WHERE task_id=%s",
            (task_id,),
        ).fetchone()[0]
        audit_count = db.execute(
            "SELECT count(*) FROM hussam_runner_v1.audit_events WHERE task_id=%s",
            (task_id,),
        ).fetchone()[0]
    assert "do-not-store" not in checkpoint
    assert audit_count >= 3


def test_fencing_rejects_stale_worker_after_reclaim(db):
    queue = PostgresQueue(db)
    tenant = tenant_id()
    task_id = queue.enqueue(tenant_id=tenant, task_type="demo", payload={},
                            idempotency_key=str(uuid.uuid4()), max_attempts=3)
    old = queue.claim(tenant_id=tenant, worker_id="worker-old", lease_seconds=5)
    assert old and old["id"] == task_id
    expire_lease(db, task_id, tenant)
    current = queue.claim(tenant_id=tenant, worker_id="worker-new", lease_seconds=30)
    assert current and current["fencing_token"] > old["fencing_token"]
    with pytest.raises(LeaseLost):
        queue.complete(old)
    queue.complete(current)


def test_expired_final_attempt_is_dead_lettered(db):
    queue = PostgresQueue(db)
    tenant = tenant_id()
    task_id = queue.enqueue(tenant_id=tenant, task_type="demo", payload={},
                            idempotency_key=str(uuid.uuid4()), max_attempts=1)
    task = queue.claim(tenant_id=tenant, worker_id="worker-crashed", lease_seconds=5)
    assert task and task["id"] == task_id
    expire_lease(db, task_id, tenant)
    assert queue.reap_exhausted(tenant_id=tenant) == 1
    with db.transaction():
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        state = db.execute(
            "SELECT state FROM hussam_runner_v1.tasks WHERE id=%s", (task_id,)
        ).fetchone()[0]
    assert state == "dead_letter"
