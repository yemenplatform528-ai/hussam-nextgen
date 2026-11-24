"""Transactional bridge from the existing application Outbox into Runner V1."""
from __future__ import annotations

import json
from typing import Any

from app.runner.redaction import safe_metadata


class PostgresOutboxRelay:
    """Move allowlisted domain events into the durable task queue atomically.

    Event types are mapped to registered task types by trusted application code.
    Unknown event types remain unpublished for explicit operator handling.
    """

    MAX_JSON_BYTES = 65536

    def __init__(self, connection: Any, *, event_handlers: dict[str, str]):
        self.connection = connection
        self.event_handlers = dict(event_handlers)

    def relay_once(self, *, tenant_id: int, limit: int = 100) -> int:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        if not self.event_handlers:
            return 0
        relayed = 0
        with self.connection.transaction():
            self.connection.execute(
                "SELECT set_config('app.tenant_id', %s, true)", (str(tenant_id),)
            )
            rows = self.connection.execute(
                """
                SELECT id,event_id,event_type,aggregate_type,aggregate_id,payload
                FROM outbox_events
                WHERE tenant_id=%s AND published=false
                  AND event_type = ANY(%s)
                ORDER BY id
                LIMIT %s FOR UPDATE SKIP LOCKED
                """,
                (tenant_id,list(self.event_handlers),limit),
            ).fetchall()
            for (event_pk,event_id,event_type,aggregate_type,aggregate_id,payload) in rows:
                task_type = self.event_handlers[event_type]
                task_payload = safe_metadata({
                    "event_id": event_id,
                    "event_type": event_type,
                    "aggregate_type": aggregate_type,
                    "aggregate_id": aggregate_id,
                    "data": payload,
                })
                encoded = json.dumps(task_payload,ensure_ascii=False)
                if len(encoded.encode("utf-8")) > self.MAX_JSON_BYTES:
                    # Keep the event unpublished; an operator can inspect its safe ID.
                    continue
                idempotency_key = f"outbox:{event_id}"
                inserted = self.connection.execute(
                    """
                    INSERT INTO hussam_runner_v1.tasks
                        (id,tenant_id,task_type,handler_version,payload,idempotency_key)
                    VALUES (gen_random_uuid(),%s,%s,'1',%s::jsonb,%s)
                    ON CONFLICT (tenant_id,idempotency_key) DO NOTHING
                    RETURNING id
                    """,
                    (tenant_id,task_type,encoded,idempotency_key),
                ).fetchone()
                if inserted:
                    task_id = inserted[0]
                else:
                    existing = self.connection.execute(
                        """SELECT id FROM hussam_runner_v1.tasks
                           WHERE tenant_id=%s AND idempotency_key=%s""",
                        (tenant_id,idempotency_key),
                    ).fetchone()
                    if existing is None:
                        raise RuntimeError("outbox idempotency conflict could not be resolved")
                    task_id = existing[0]
                self.connection.execute(
                    """UPDATE outbox_events SET published=true
                       WHERE id=%s AND tenant_id=%s AND published=false""",
                    (event_pk,tenant_id),
                )
                self.connection.execute(
                    """INSERT INTO hussam_runner_v1.audit_events
                       (task_id,tenant_id,event_type,safe_metadata)
                       VALUES (%s,%s,'outbox.relayed',%s::jsonb)""",
                    (task_id,tenant_id,json.dumps({"event_id":event_id,"source_event_type":event_type})),
                )
                relayed += 1
        return relayed
