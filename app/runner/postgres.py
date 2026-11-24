"""Small PostgreSQL queue repository; caller owns connection lifecycle."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any

from app.runner.redaction import safe_metadata


class LeaseLost(RuntimeError):
    """Raised when a worker no longer owns the current fenced lease."""


class PostgresQueue:
    def __init__(self, connection: Any):
        self.connection = connection

    def enqueue(
        self, *, tenant_id: int, task_type: str, payload: dict[str, Any],
        idempotency_key: str, handler_version: str = "1",
        priority: int = 0, max_attempts: int = 5,
    ) -> uuid.UUID:
        task_id = uuid.uuid4()
        safe_payload = safe_metadata(payload)
        with self.connection.transaction():
            row = self.connection.execute(
                """
                INSERT INTO hussam_runner_v1.tasks
                    (id, tenant_id, task_type, handler_version, payload,
                     idempotency_key, priority, max_attempts)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (tenant_id, idempotency_key)
                DO UPDATE SET idempotency_key = EXCLUDED.idempotency_key
                RETURNING id
                """,
                (task_id, tenant_id, task_type, handler_version,
                 json.dumps(safe_payload), idempotency_key, priority, max_attempts),
            ).fetchone()
            return row[0]

    def claim(self, *, tenant_id: int, worker_id: str,
              lease_seconds: int = 60) -> dict[str, Any] | None:
        if lease_seconds < 5:
            raise ValueError("lease_seconds must be at least 5")
        with self.connection.transaction():
            row = self.connection.execute(
                """
                WITH candidate AS (
                    SELECT id FROM hussam_runner_v1.tasks
                    WHERE tenant_id = %s
                      AND attempts < max_attempts
                      AND run_after <= now()
                      AND (state IN ('pending','retry_wait')
                           OR (state = 'running' AND lease_expires_at < now()))
                    ORDER BY priority DESC, run_after, created_at
                    FOR UPDATE SKIP LOCKED LIMIT 1
                )
                UPDATE hussam_runner_v1.tasks AS t
                SET state='running', attempts=t.attempts+1,
                    lease_owner=%s,
                    lease_expires_at=now() + (%s * interval '1 second'),
                    fencing_token=t.fencing_token+1,
                    started_at=COALESCE(t.started_at, now()), updated_at=now()
                FROM candidate c WHERE t.id=c.id
                RETURNING t.id,t.tenant_id,t.task_type,t.handler_version,
                          t.payload,t.attempts,t.lease_owner,t.lease_expires_at,
                          t.fencing_token
                """,
                (tenant_id, worker_id, lease_seconds),
            ).fetchone()
            if row is None:
                return None
            task = dict(zip(
                ("id","tenant_id","task_type","handler_version","payload",
                 "attempts","lease_owner","lease_expires_at","fencing_token"), row
            ))
            self.connection.execute(
                """
                INSERT INTO hussam_runner_v1.attempts
                    (task_id,tenant_id,attempt_no,worker_id,fencing_token)
                VALUES (%s,%s,%s,%s,%s)
                """,
                (task["id"], tenant_id, task["attempts"], worker_id,
                 task["fencing_token"]),
            )
            self._audit(task, "task.claimed", worker_id)
            return task

    def heartbeat(self, task: dict[str, Any], *, lease_seconds: int = 60) -> None:
        with self.connection.transaction():
            result = self.connection.execute(
                """
                UPDATE hussam_runner_v1.tasks
                SET lease_expires_at=now() + (%s * interval '1 second'),
                    updated_at=now()
                WHERE id=%s AND tenant_id=%s AND state='running'
                  AND lease_owner=%s AND fencing_token=%s
                  AND lease_expires_at > now()
                """,
                (lease_seconds, task["id"], task["tenant_id"],
                 task["lease_owner"], task["fencing_token"]),
            )
            if result.rowcount != 1:
                raise LeaseLost("lease ownership lost")

    def checkpoint(self, task: dict[str, Any], payload: dict[str, Any]) -> int:
        safe_payload = safe_metadata(payload)
        encoded = json.dumps(safe_payload, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with self.connection.transaction():
            self._assert_lease(task)
            row = self.connection.execute(
                """
                INSERT INTO hussam_runner_v1.checkpoints
                    (task_id,tenant_id,sequence_no,handler_version,payload,sha256,fencing_token)
                SELECT %s,%s,COALESCE(MAX(sequence_no),0)+1,%s,%s::jsonb,%s,%s
                FROM hussam_runner_v1.checkpoints WHERE task_id=%s
                RETURNING sequence_no
                """,
                (task["id"],task["tenant_id"],task["handler_version"],
                 encoded,digest,task["fencing_token"],task["id"]),
            ).fetchone()
            self._audit(task, "task.checkpointed", task["lease_owner"],
                        {"sequence": row[0], "sha256": digest})
            return row[0]

    def complete(self, task: dict[str, Any]) -> None:
        with self.connection.transaction():
            self._assert_lease(task)
            self.connection.execute(
                """
                UPDATE hussam_runner_v1.tasks
                SET state='succeeded',completed_at=now(),updated_at=now(),
                    lease_owner=NULL,lease_expires_at=NULL
                WHERE id=%s AND tenant_id=%s AND lease_owner=%s AND fencing_token=%s
                """,
                (task["id"],task["tenant_id"],task["lease_owner"],task["fencing_token"]),
            )
            self._finish_attempt(task, "succeeded")
            self._audit(task, "task.succeeded", task["lease_owner"])

    def fail(self, task: dict[str, Any], *, error_code: str,
             safe_summary: str, retry_delay_seconds: int = 30) -> None:
        from app.runner.redaction import redact_text
        summary = redact_text(safe_summary)
        with self.connection.transaction():
            self._assert_lease(task)
            self.connection.execute(
                """
                UPDATE hussam_runner_v1.tasks
                SET state=CASE WHEN attempts >= max_attempts THEN 'dead_letter'
                               ELSE 'retry_wait' END,
                    run_after=now() + (%s * interval '1 second'),
                    safe_error_code=%s,safe_error_summary=%s,
                    updated_at=now(),lease_owner=NULL,lease_expires_at=NULL,
                    completed_at=CASE WHEN attempts >= max_attempts THEN now() ELSE NULL END
                WHERE id=%s AND tenant_id=%s AND lease_owner=%s AND fencing_token=%s
                """,
                (max(0,retry_delay_seconds),error_code[:100],summary,
                 task["id"],task["tenant_id"],task["lease_owner"],task["fencing_token"]),
            )
            self._finish_attempt(task, "failed")
            self._audit(task, "task.failed", task["lease_owner"],
                        {"error_code": error_code[:100], "summary": summary})

    def _assert_lease(self, task: dict[str, Any]) -> None:
        row = self.connection.execute(
            """
            SELECT 1 FROM hussam_runner_v1.tasks
            WHERE id=%s AND tenant_id=%s AND state='running'
              AND lease_owner=%s AND fencing_token=%s
              AND lease_expires_at > now()
            FOR UPDATE
            """,
            (task["id"],task["tenant_id"],task["lease_owner"],task["fencing_token"]),
        ).fetchone()
        if row is None:
            raise LeaseLost("lease ownership lost")

    def _finish_attempt(self, task: dict[str, Any], outcome: str) -> None:
        self.connection.execute(
            """
            UPDATE hussam_runner_v1.attempts
            SET finished_at=now(),outcome=%s
            WHERE task_id=%s AND tenant_id=%s AND attempt_no=%s
              AND worker_id=%s AND fencing_token=%s AND finished_at IS NULL
            """,
            (outcome,task["id"],task["tenant_id"],task["attempts"],
             task["lease_owner"],task["fencing_token"]),
        )

    def _audit(self, task: dict[str, Any], event: str, worker: str,
               metadata: dict[str, Any] | None = None) -> None:
        self.connection.execute(
            """
            INSERT INTO hussam_runner_v1.audit_events
                (task_id,tenant_id,event_type,worker_id,fencing_token,safe_metadata)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb)
            """,
            (task["id"],task["tenant_id"],event,worker,task["fencing_token"],
             json.dumps(safe_metadata(metadata or {}))),
        )
