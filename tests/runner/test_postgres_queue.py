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


def test_heartbeat_renews_current_lease(db):
    queue = PostgresQueue(db)
    tenant = tenant_id()
    task_id = queue.enqueue(tenant_id=tenant, task_type="demo", payload={},
                            idempotency_key=str(uuid.uuid4()))
    task = queue.claim(tenant_id=tenant, worker_id="worker-heartbeat", lease_seconds=10)
    assert task and task["id"] == task_id
    queue.heartbeat(task, lease_seconds=30)
    queue.complete(task)


def test_fail_uses_retry_then_dead_letter_state(db):
    queue = PostgresQueue(db)
    tenant = tenant_id()
    task_id = queue.enqueue(tenant_id=tenant, task_type="demo", payload={},
                            idempotency_key=str(uuid.uuid4()), max_attempts=2)
    first = queue.claim(tenant_id=tenant, worker_id="worker-retry")
    assert first and first["id"] == task_id
    queue.fail(first, error_code="temporary_failure", safe_summary="retry safely",
               retry_delay_seconds=0)
    with db.transaction():
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        db.execute("UPDATE hussam_runner_v1.tasks SET run_after=now() WHERE id=%s", (task_id,))
    second = queue.claim(tenant_id=tenant, worker_id="worker-retry")
    assert second and second["attempts"] == 2
    queue.fail(second, error_code="final_failure", safe_summary="final safe failure")
    with db.transaction():
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        row = db.execute(
            "SELECT state,safe_error_code FROM hussam_runner_v1.tasks WHERE id=%s",
            (task_id,),
        ).fetchone()
    assert row == ("dead_letter", "FINAL_FAILURE")


def test_enqueue_rejects_oversized_payload_before_database_access():
    class NoDatabase:
        def transaction(self):
            raise AssertionError("database must not be accessed for oversized payload")

    queue = PostgresQueue(NoDatabase())
    with pytest.raises(ValueError, match="64 KiB"):
        queue.enqueue(tenant_id=1, task_type="demo",
                      payload={"large": ["x" * 1200 for _ in range(100)]},
                      idempotency_key="oversized")



def test_checkpoint_is_restored_after_lease_reclaim(db):
    queue = PostgresQueue(db)
    tenant = tenant_id()
    task_id = queue.enqueue(tenant_id=tenant, task_type="demo", payload={},
                            idempotency_key=str(uuid.uuid4()), max_attempts=3)
    first = queue.claim(tenant_id=tenant, worker_id="worker-before-crash", lease_seconds=5)
    assert first and first["id"] == task_id
    queue.checkpoint(first, {"cursor": 19, "page": 4})
    expire_lease(db, task_id, tenant)
    recovered = queue.claim(tenant_id=tenant, worker_id="worker-after-restart")
    assert recovered and recovered["id"] == task_id
    checkpoint = queue.latest_checkpoint(recovered)
    assert checkpoint is not None
    assert checkpoint["payload"] == {"cursor": 19, "page": 4}
    assert checkpoint["sequence_no"] == 1


def test_checkpoint_hash_tampering_fails_closed(db):
    from app.runner.postgres import CheckpointIntegrityError

    queue = PostgresQueue(db)
    tenant = tenant_id()
    task_id = queue.enqueue(tenant_id=tenant, task_type="demo", payload={},
                            idempotency_key=str(uuid.uuid4()))
    task = queue.claim(tenant_id=tenant, worker_id="worker-checkpoint-hash")
    assert task and task["id"] == task_id
    queue.checkpoint(task, {"cursor": 8})
    with db.transaction():
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        db.execute(
            """UPDATE hussam_runner_v1.checkpoints
               SET sha256=%s WHERE task_id=%s AND tenant_id=%s""",
            ("0" * 64, task_id, tenant),
        )
    with pytest.raises(CheckpointIntegrityError):
        queue.latest_checkpoint(task)


def test_checkpoint_version_mismatch_fails_closed(db):
    from app.runner.postgres import CheckpointIntegrityError

    queue = PostgresQueue(db)
    tenant = tenant_id()
    task_id = queue.enqueue(tenant_id=tenant, task_type="demo", payload={},
                            idempotency_key=str(uuid.uuid4()))
    task = queue.claim(tenant_id=tenant, worker_id="worker-checkpoint-version")
    assert task and task["id"] == task_id
    queue.checkpoint(task, {"cursor": 8})
    with db.transaction():
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        db.execute(
            """UPDATE hussam_runner_v1.checkpoints
               SET handler_version='older-version' WHERE task_id=%s AND tenant_id=%s""",
            (task_id, tenant),
        )
    with pytest.raises(CheckpointIntegrityError):
        queue.latest_checkpoint(task)


def test_graceful_defer_remains_claimable_without_marking_failure(db):
    queue = PostgresQueue(db)
    tenant = tenant_id()
    task_id = queue.enqueue(tenant_id=tenant, task_type="demo", payload={},
                            idempotency_key=str(uuid.uuid4()), max_attempts=1)
    first = queue.claim(tenant_id=tenant, worker_id="worker-shutting-down")
    assert first and first["id"] == task_id
    queue.checkpoint(first, {"cursor": 12})
    queue.defer(first)
    resumed = queue.claim(tenant_id=tenant, worker_id="worker-restarted")
    assert resumed and resumed["id"] == task_id
    assert resumed["attempts"] == 2
    assert queue.latest_checkpoint(resumed)["payload"] == {"cursor": 12}
    queue.complete(resumed)


def test_worker_registry_heartbeat_tracks_process_instance(db):
    queue = PostgresQueue(db)
    process_id = uuid.uuid4()
    worker_id = f"worker-{uuid.uuid4()}"
    assert queue.touch_worker(
        worker_id=worker_id, process_instance_id=process_id, build_version="test-v1"
    ) == worker_id
    with db.transaction():
        row = db.execute(
            """SELECT process_instance_id,build_version,last_seen_at
               FROM hussam_runner_v1.workers WHERE worker_id=%s""",
            (worker_id,),
        ).fetchone()
    assert row[0] == process_id
    assert row[1] == "test-v1"
    assert row[2] is not None
