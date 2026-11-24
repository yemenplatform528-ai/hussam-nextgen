from __future__ import annotations

import uuid

import pytest

from app.runner.outbox import PostgresOutboxRelay


def test_outbox_relay_enqueues_once_and_marks_source_published(db):
    tenant = uuid.uuid4().int % 2_000_000_000 + 1
    event_id = uuid.uuid4().hex
    with db.transaction():
        db.execute(
            """CREATE TABLE IF NOT EXISTS outbox_events (
               id bigserial PRIMARY KEY,event_id varchar(64) UNIQUE NOT NULL,
               tenant_id bigint NOT NULL,event_type varchar(200) NOT NULL,
               aggregate_type varchar(100) NOT NULL,aggregate_id varchar(100) NOT NULL,
               payload jsonb NOT NULL,published boolean NOT NULL DEFAULT false)"""
        )
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        db.execute(
            """INSERT INTO outbox_events
               (event_id,tenant_id,event_type,aggregate_type,aggregate_id,payload)
               VALUES (%s,%s,'order.created','order','ord-1','{"amount":5}'::jsonb)""",
            (event_id,tenant),
        )
    relay = PostgresOutboxRelay(db,event_handlers={"order.created":"handle_order_created"})
    assert relay.relay_once(tenant_id=tenant) == 1
    assert relay.relay_once(tenant_id=tenant) == 0
    with db.transaction():
        db.execute("SELECT set_config('app.tenant_id', %s, true)", (str(tenant),))
        published = db.execute(
            "SELECT published FROM outbox_events WHERE event_id=%s",(event_id,)
        ).fetchone()[0]
        task = db.execute(
            "SELECT task_type,payload::text FROM hussam_runner_v1.tasks WHERE tenant_id=%s AND idempotency_key=%s",
            (tenant,f"outbox:{event_id}"),
        ).fetchone()
    assert published is True
    assert task[0] == "handle_order_created"
    assert event_id in task[1]
