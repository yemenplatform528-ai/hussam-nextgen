"""Small PostgreSQL queue repository; caller owns connection lifecycle."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from app.runner.redaction import safe_metadata, redact_text


class LeaseLost(RuntimeError):
    """Raised when a worker no longer owns the current fenced lease."""


class PostgresQueue:
    def __init__(self, connection: Any):
        self.connection = connection

    def _set_tenant(self, tenant_id: int) -> None:
        self.connection.execute(
            "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),)
        )

    def enqueue(self, *, tenant_id: int, task_type: str, payload: dict[str, Any],
                idempotency_key: str, handler_version: str = "1",
                priority: int = 0, max_attempts: int = 5) -> uuid.UUID:
        if not idempotency_key or len(idempotency_key) > 255:
            raise ValueError("idempotency_key must contain 1..255 characters")
        if not task_type or len(task_type) > 120 or max_attempts < 1:
            raise ValueError("invalid task type or max_attempts")
        safe_payload = safe_metadata(payload)
        with self.connection.transaction():
            self._set_tenant(tenant_id)
            row = self.connection.execute(
                """
                INSERT INTO hussam_runner_v1.tasks
                    (id, tenant_id, task_type, handler_version, payload,
                     idempotency_key, priority, max_attempts)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s)
                ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
                RETURNING id
                """,
                (uuid.uuid4(), tenant_id, task_type, handler_version,
                 json.dumps(safe_payload), idempotency_key, priority, max_attempts),
            ).fetchone()
            if row:
                return row[0]
            existing = self.connection.execute(
                """SELECT id FROM hussam_runner_v1.tasks
                   WHERE tenant_id=%s AND idempotency_key=%s""",
                (tenant_id, idempotency_key),
            ).fetchone()
            if existing is None:
                raise RuntimeError("idempotency conflict could not be resolved")
            return existing[0]

    def claim(self, *, tenant_id: int, worker_id: str,
              lease_seconds: int = 60) -> dict[str, Any] | None:
        if lease_seconds < 5:
            raise ValueError("lease_seconds must be at least 5")
        with self.connection.transaction():
            self._set_tenant(tenant_id)
            row = self.connection.execute(
                """
                WITH candidate AS (
                    SELECT id FROM hussam_runner_v1.tasks
                    WHERE tenant_id=%s AND attempts < max_attempts
                      AND run_after <= now()
                      AND (state IN ('pending','retry_wait')
                           OR (state='running' AND lease_expires_at < now()))
                    ORDER BY priority DESC, run_after, created_at
                    LIMIT 1 FOR UPDATE SKIP LOCKED
                )
                UPDATE hussam_runner_v1.tasks AS t
                SET state='running', attempts=t.attempts+1, lease_owner=%s,
                    lease_expires_at=now() + (%s * interval '1 second'),
                    fencing_token=t.fencing_token+1,
                    started_at=COALESCE(t.started_at,now()), updated_at=now()
                FROM candidate c WHERE t.id=c.id
                RETURNING t.id,t.tenant_id,t.task_type,t.handler_version,t.payload,
                          t.attempts,t.max_attempts,t.lease_owner,t.lease_expires_at,
                          t.fencing_token
                """,
                (tenant_id, worker_id, lease_seconds),
            ).fetchone()
            if row is None:
                return None
            keys = ("id","tenant_id","task_type","handler_version","payload",
                    "attempts","max_attempts","lease_owner","lease_expires_at",
                    "fencing_token")
            task = dict(zip(keys, row))
            if task["attempts"] > 1:
                self.connection.execute(
                    """UPDATE hussam_runner_v1.attempts
                       SET finished_at=now(),outcome='lease_lost',
                           safe_error_code='LEASE_EXPIRED_RECLAIMED'
                       WHERE task_id=%s AND tenant_id=%s AND attempt_no=%s
                         AND finished_at IS NULL""",
                    (task["id"],tenant_id,task["attempts"] - 1),
                )
                self._audit(task,"task.lease_reclaimed",worker_id,
                            {"previous_attempt":task["attempts"] - 1})
            self.connection.execute(
                """INSERT INTO hussam_runner_v1.attempts
                   (task_id,tenant_id,attempt_no,worker_id,fencing_token)
                   VALUES (%s,%s,%s,%s,%s)""",
                (task["id"],tenant_id,task["attempts"],worker_id,task["fencing_token"]),
            )
            self._audit(task, "task.claimed", worker_id)
            return task

    def heartbeat(self, task: dict[str, Any], *, lease_seconds: int = 60) -> None:
        with self.connection.transaction():
            self._set_tenant(task["tenant_id"])
            result = self.connection.execute(
                """UPDATE hussam_runner_v1.tasks
                   SET lease_expires_at=now() + (%s * interval '1 second'),updated_at=now()
                   WHERE id=%s AND tenant_id=%s AND state='running'
                     AND lease_owner=%s AND fencing_token=%s AND lease_expires_at > now()""",
                (lease_seconds,task["id"],task["tenant_id"],
                 task["lease_owner"],task["fencing_token"]),
            )
            if result.rowcount != 1:
                raise LeaseLost("lease ownership lost")

    def checkpoint(self, task: dict[str, Any], payload: dict[str, Any]) -> int:
        safe_payload = safe_metadata(payload)
        encoded = json.dumps(safe_payload, sort_keys=True, separators=(",",":"))
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        with self.connection.transaction():
            self._set_tenant(task["tenant_id"])
            self._assert_lease(task)
            row = self.connection.execute(
                """
                INSERT INTO hussam_runner_v1.checkpoints
                    (task_id,tenant_id,sequence_no,handler_version,payload,sha256,fencing_token)
                SELECT %s,%s,next_seq,%s,%s::jsonb,%s,%s
                FROM (SELECT COALESCE(MAX(sequence_no),0)+1 AS next_seq
                      FROM hussam_runner_v1.checkpoints WHERE task_id=%s) q
                RETURNING sequence_no
                """,
                (task["id"],task["tenant_id"],task["handler_version"],
                 encoded,digest,task["fencing_token"],task["id"]),
            ).fetchone()
            self._audit(task,"task.checkpointed",task["lease_owner"],
                        {"sequence":row[0],"sha256":digest})
            return row[0]

    def complete(self, task: dict[str, Any]) -> None:
        with self.connection.transaction():
            self._set_tenant(task["tenant_id"])
            self._assert_lease(task)
            self.connection.execute(
                """UPDATE hussam_runner_v1.tasks
                   SET state='succeeded',completed_at=now(),updated_at=now(),
                       lease_owner=NULL,lease_expires_at=NULL
                   WHERE id=%s AND tenant_id=%s AND lease_owner=%s AND fencing_token=%s""",
                (task["id"],task["tenant_id"],task["lease_owner"],task["fencing_token"]),
            )
            self._finish_attempt(task,"succeeded")
            self._audit(task,"task.succeeded",task["lease_owner"])

    def fail(self, task: dict[str, Any], *, error_code: str,
             safe_summary: str, retry_delay_seconds: int = 30) -> None:
        summary = redact_text(safe_summary)
        terminal = task["attempts"] >= task["max_attempts"]
        outcome = "failed" if terminal else "retry"
        with self.connection.transaction():
            self._set_tenant(task["tenant_id"])
            self._assert_lease(task)
            self.connection.execute(
                """UPDATE hussam_runner_v1.tasks
                   SET state=%s,run_after=now() + (%s * interval '1 second'),
                       safe_error_code=%s,safe_error_summary=%s,updated_at=now(),
                       lease_owner=NULL,lease_expires_at=NULL,
                       completed_at=CASE WHEN %s THEN now() ELSE NULL END
                   WHERE id=%s AND tenant_id=%s AND lease_owner=%s AND fencing_token=%s""",
                ("dead_letter" if terminal else "retry_wait",
                 max(0,retry_delay_seconds),error_code[:100],summary,terminal,
                 task["id"],task["tenant_id"],task["lease_owner"],task["fencing_token"]),
            )
            self._finish_attempt(task,outcome,error_code[:100])
            self._audit(task,"task.failed",task["lease_owner"],
                        {"error_code":error_code[:100],"summary":summary})

    def reap_exhausted(self, *, tenant_id: int, limit: int = 100) -> int:
        """Move expired final-attempt leases to dead_letter and close their attempts."""
        with self.connection.transaction():
            self._set_tenant(tenant_id)
            rows = self.connection.execute(
                """
                WITH expired AS (
                    SELECT id,tenant_id,attempts,lease_owner,fencing_token
                    FROM hussam_runner_v1.tasks
                    WHERE tenant_id=%s AND state='running'
                      AND lease_expires_at < now() AND attempts >= max_attempts
                    ORDER BY lease_expires_at LIMIT %s FOR UPDATE SKIP LOCKED
                )
                UPDATE hussam_runner_v1.tasks t
                SET state='dead_letter',safe_error_code='LEASE_EXPIRED_FINAL_ATTEMPT',
                    safe_error_summary='Worker lease expired on final attempt',
                    completed_at=now(),updated_at=now(),lease_owner=NULL,lease_expires_at=NULL
                FROM expired e WHERE t.id=e.id
                RETURNING t.id,t.tenant_id,e.attempts,e.lease_owner,e.fencing_token
                """, (tenant_id,limit)
            ).fetchall()
            for task_id, tid, attempt_no, owner, token in rows:
                self.connection.execute(
                    """UPDATE hussam_runner_v1.attempts
                       SET finished_at=now(),outcome='failed',
                           safe_error_code='LEASE_EXPIRED_FINAL_ATTEMPT'
                       WHERE task_id=%s AND tenant_id=%s AND attempt_no=%s
                         AND worker_id=%s AND fencing_token=%s AND finished_at IS NULL""",
                    (task_id,tid,attempt_no,owner,token),
                )
                self.connection.execute(
                    """INSERT INTO hussam_runner_v1.audit_events
                       (task_id,tenant_id,event_type,worker_id,fencing_token,safe_metadata)
                       VALUES (%s,%s,'task.dead_lettered',%s,%s,'{}'::jsonb)""",
                    (task_id,tid,owner,token),
                )
            return len(rows)

    def _assert_lease(self, task: dict[str, Any]) -> None:
        row = self.connection.execute(
            """SELECT 1 FROM hussam_runner_v1.tasks
               WHERE id=%s AND tenant_id=%s AND state='running'
                 AND lease_owner=%s AND fencing_token=%s AND lease_expires_at > now()
               FOR UPDATE""",
            (task["id"],task["tenant_id"],task["lease_owner"],task["fencing_token"]),
        ).fetchone()
        if row is None:
            raise LeaseLost("lease ownership lost")

    def _finish_attempt(self, task: dict[str, Any], outcome: str,
                        error_code: str | None = None) -> None:
        self.connection.execute(
            """UPDATE hussam_runner_v1.attempts
               SET finished_at=now(),outcome=%s,safe_error_code=%s
               WHERE task_id=%s AND tenant_id=%s AND attempt_no=%s
                 AND worker_id=%s AND fencing_token=%s AND finished_at IS NULL""",
            (outcome,error_code,task["id"],task["tenant_id"],task["attempts"],
             task["lease_owner"],task["fencing_token"]),
        )

    def _audit(self, task: dict[str, Any], event: str, worker: str,
               metadata: dict[str, Any] | None = None) -> None:
        self.connection.execute(
            """INSERT INTO hussam_runner_v1.audit_events
               (task_id,tenant_id,event_type,worker_id,fencing_token,safe_metadata)
               VALUES (%s,%s,%s,%s,%s,%s::jsonb)""",
            (task["id"],task["tenant_id"],event,worker,task["fencing_token"],
             json.dumps(safe_metadata(metadata or {}))),
        )
