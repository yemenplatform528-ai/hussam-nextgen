"""Small PostgreSQL queue repository; caller owns connection lifecycle."""
from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from app.runner.redaction import safe_metadata, redact_text


class LeaseLost(RuntimeError):
    """Raised when a worker no longer owns the current fenced lease."""


class CheckpointIntegrityError(RuntimeError):
    """Raised when a persisted checkpoint fails integrity or version checks."""


class PostgresQueue:
    MAX_JSON_BYTES = 65536

    def __init__(self, connection: Any):
        self.connection = connection

    def _set_tenant(self, tenant_id: int) -> None:
        self.connection.execute(
            "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),)
        )

    def touch_worker(self, *, worker_id: str, process_instance_id: uuid.UUID,
                     build_version: str) -> str:
        """Upsert a secret-free process heartbeat in the global worker registry."""
        if not worker_id or len(worker_id) > 160:
            raise ValueError("worker_id must contain 1..160 characters")
        if not build_version or len(build_version) > 80:
            raise ValueError("build_version must contain 1..80 characters")
        with self.connection.transaction():
            row = self.connection.execute(
                """INSERT INTO hussam_runner_v1.workers
                       (worker_id,process_instance_id,build_version,last_seen_at)
                   VALUES (%s,%s,%s,now())
                   ON CONFLICT (worker_id) DO UPDATE
                   SET process_instance_id=EXCLUDED.process_instance_id,
                       build_version=EXCLUDED.build_version,last_seen_at=now()
                   RETURNING worker_id""",
                (worker_id,process_instance_id,build_version),
            ).fetchone()
            return row[0]

    def enqueue(self, *, tenant_id: int, task_type: str, payload: dict[str, Any],
                idempotency_key: str, handler_version: str = "1",
                priority: int = 0, max_attempts: int = 5) -> uuid.UUID:
        if not idempotency_key or len(idempotency_key) > 255:
            raise ValueError("idempotency_key must contain 1..255 characters")
        if not task_type or len(task_type) > 120 or max_attempts < 1:
            raise ValueError("invalid task type or max_attempts")
        safe_payload = safe_metadata(payload)
        encoded_payload = json.dumps(safe_payload, ensure_ascii=False)
        if len(encoded_payload.encode("utf-8")) > self.MAX_JSON_BYTES:
            raise ValueError("task payload exceeds 64 KiB")
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
                 encoded_payload, idempotency_key, priority, max_attempts),
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
                    WHERE tenant_id=%s AND run_after <= now()
                      AND (
                          (state='pending' AND attempts < max_attempts)
                          OR state='retry_wait'
                          OR (state='running' AND lease_expires_at < now()
                              AND attempts < max_attempts)
                      )
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
        if len(encoded.encode("utf-8")) > self.MAX_JSON_BYTES:
            raise ValueError("checkpoint payload exceeds 64 KiB")
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

    def latest_checkpoint(self, task: dict[str, Any]) -> dict[str, Any] | None:
        """Load and verify the latest checkpoint while the caller still owns the lease."""
        with self.connection.transaction():
            self._set_tenant(task["tenant_id"])
            self._assert_lease(task)
            row = self.connection.execute(
                """SELECT sequence_no,handler_version,payload,sha256,fencing_token
                   FROM hussam_runner_v1.checkpoints
                   WHERE task_id=%s AND tenant_id=%s
                   ORDER BY sequence_no DESC LIMIT 1""",
                (task["id"],task["tenant_id"]),
            ).fetchone()
            if row is None:
                return None
            sequence_no, handler_version, payload, stored_digest, checkpoint_token = row
            if handler_version != task["handler_version"]:
                raise CheckpointIntegrityError("checkpoint handler version mismatch")
            if checkpoint_token > task["fencing_token"]:
                raise CheckpointIntegrityError("checkpoint fencing token is from the future")
            if isinstance(payload,str):
                try:
                    payload = json.loads(payload)
                except (TypeError,ValueError) as exc:
                    raise CheckpointIntegrityError("checkpoint payload is invalid JSON") from exc
            if not isinstance(payload,dict):
                raise CheckpointIntegrityError("checkpoint payload must be an object")
            encoded = json.dumps(payload,sort_keys=True,separators=(",",":"))
            digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            if not __import__("hmac").compare_digest(digest,str(stored_digest)):
                raise CheckpointIntegrityError("checkpoint SHA-256 verification failed")
            return {
                "sequence_no": sequence_no,
                "handler_version": handler_version,
                "payload": payload,
                "sha256": digest,
            }

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

    def defer(self, task: dict[str, Any], *, reason_code: str = "WORKER_SHUTDOWN") -> None:
        """Yield an active lease for graceful shutdown without recording a task failure."""
        safe_code = reason_code.upper()
        if not safe_code or len(safe_code) > 100 or not all(
            char.isalnum() or char == "_" for char in safe_code
        ):
            safe_code = "WORKER_SHUTDOWN"
        with self.connection.transaction():
            self._set_tenant(task["tenant_id"])
            self._assert_lease(task)
            self.connection.execute(
                """UPDATE hussam_runner_v1.tasks
                   SET state='retry_wait',run_after=now(),safe_error_code=%s,
                       safe_error_summary='Task yielded for graceful worker shutdown',
                       updated_at=now(),lease_owner=NULL,lease_expires_at=NULL,
                       completed_at=NULL
                   WHERE id=%s AND tenant_id=%s AND lease_owner=%s AND fencing_token=%s""",
                (safe_code,task["id"],task["tenant_id"],
                 task["lease_owner"],task["fencing_token"]),
            )
            self._finish_attempt(task,"retry",safe_code)
            self._audit(task,"task.deferred",task["lease_owner"],{"reason_code":safe_code})

    def fail(self, task: dict[str, Any], *, error_code: str,
             safe_summary: str, retry_delay_seconds: int = 30) -> None:
        summary = redact_text(safe_summary)
        safe_code = error_code.upper()
        if not safe_code or len(safe_code) > 100 or not all(
            char.isalnum() or char == "_" for char in safe_code
        ):
            safe_code = "HANDLER_ERROR"
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
                 max(0,retry_delay_seconds),safe_code,summary,terminal,
                 task["id"],task["tenant_id"],task["lease_owner"],task["fencing_token"]),
            )
            self._finish_attempt(task,outcome,safe_code)
            self._audit(task,"task.failed",task["lease_owner"],
                        {"error_code":safe_code,"summary":summary})

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
