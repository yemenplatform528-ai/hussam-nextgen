"""Transactional schedule materializer; cron calculation is injected and timezone-aware."""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.runner.redaction import safe_metadata

NextOccurrence = Callable[[str, str, datetime], datetime]


class PostgresScheduler:
    """Materialize due schedule occurrences atomically with durable tasks.

    next_occurrence(expression, IANA_timezone, after_utc) must return a strictly
    later timezone-aware datetime. Inject a tested cron/DST implementation;
    this module deliberately does not invent cron parsing semantics.
    """

    def __init__(self, connection: Any, *, next_occurrence: NextOccurrence):
        self.connection = connection
        self.next_occurrence = next_occurrence

    def materialize_due(self, *, tenant_id: int, limit: int = 25) -> int:
        if limit < 1 or limit > 250:
            raise ValueError("limit must be between 1 and 250")
        materialized = 0
        with self.connection.transaction():
            self.connection.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),)
            )
            now = self.connection.execute("SELECT now()").fetchone()[0]
            schedules = self.connection.execute(
                """
                SELECT id,task_type,handler_version,payload,cron_expression,
                       timezone,next_run_at,misfire_policy
                FROM hussam_runner_v1.schedules
                WHERE tenant_id=%s AND enabled AND next_run_at <= %s
                ORDER BY next_run_at
                LIMIT %s FOR UPDATE SKIP LOCKED
                """,
                (tenant_id,now,limit),
            ).fetchall()

            for (schedule_id, task_type, handler_version, payload, expression,
                 timezone_name, scheduled_for, misfire_policy) in schedules:
                # "skip" records missed occurrences without enqueuing work.
                skip = misfire_policy == "skip" and scheduled_for < now
                task_id = None
                if not skip:
                    task_id = uuid.uuid4()
                    idempotency_key = (
                        f"schedule:{schedule_id}:{scheduled_for.isoformat()}"
                    )
                    self.connection.execute(
                        """
                        INSERT INTO hussam_runner_v1.tasks
                            (id,tenant_id,task_type,handler_version,payload,
                             idempotency_key,state,run_after)
                        VALUES (%s,%s,%s,%s,%s::jsonb,%s,'pending',%s)
                        ON CONFLICT (tenant_id,idempotency_key) DO NOTHING
                        """,
                        (task_id,tenant_id,task_type,handler_version,
                         json.dumps(safe_metadata(payload)),idempotency_key,
                         max(now,scheduled_for) if misfire_policy == "run_once" else scheduled_for),
                    )
                    existing = self.connection.execute(
                        """SELECT id FROM hussam_runner_v1.tasks
                           WHERE tenant_id=%s AND idempotency_key=%s""",
                        (tenant_id,idempotency_key),
                    ).fetchone()
                    task_id = existing[0] if existing else None
                    if task_id is None:
                        raise RuntimeError("schedule task materialization failed")

                self.connection.execute(
                    """
                    INSERT INTO hussam_runner_v1.schedule_occurrences
                        (schedule_id,tenant_id,scheduled_for,task_id)
                    VALUES (%s,%s,%s,%s)
                    ON CONFLICT (schedule_id,scheduled_for) DO NOTHING
                    """,
                    (schedule_id,tenant_id,scheduled_for,task_id),
                )
                calculation_base = now if misfire_policy in ("skip","run_once") else scheduled_for
                following = self.next_occurrence(expression,timezone_name,calculation_base)
                if following.tzinfo is None or following <= calculation_base:
                    raise ValueError("next_occurrence must return a later timezone-aware datetime")
                self.connection.execute(
                    """UPDATE hussam_runner_v1.schedules
                       SET next_run_at=%s,updated_at=now()
                       WHERE id=%s AND tenant_id=%s""",
                    (following,schedule_id,tenant_id),
                )
                if task_id is not None:
                    materialized += 1
        return materialized
