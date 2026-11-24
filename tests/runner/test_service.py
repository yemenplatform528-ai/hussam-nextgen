from __future__ import annotations

import logging

from app.runner.service import RunnerService


class FakeQueue:
    def __init__(self, *, fail_reaper=False):
        self.reaped = []
        self.worker_heartbeats = []
        self.fail_reaper = fail_reaper

    def touch_worker(self, *, worker_id, process_instance_id, build_version):
        self.worker_heartbeats.append((worker_id, process_instance_id, build_version))
        return worker_id

    def reap_exhausted(self, *, tenant_id):
        self.reaped.append(tenant_id)
        if self.fail_reaper:
            raise RuntimeError("Authorization: Bearer service-test-secret")
        return 2


class FakeWorker:
    def __init__(self, *, tenant_id=41, fail_reaper=False):
        import uuid

        self.tenant_id = tenant_id
        self.worker_id = "worker-test"
        self.process_instance_id = uuid.uuid4()
        self.build_version = "test-build"
        self.queue = FakeQueue(fail_reaper=fail_reaper)
        self.calls = []

    def run_once(self, *, shutdown_event=None):
        self.calls.append(shutdown_event)
        return True


class FakeScheduler:
    def __init__(self):
        self.calls = []

    def materialize_due(self, *, tenant_id, limit):
        self.calls.append((tenant_id, limit))
        return 3


class FakeOutboxRelay:
    def __init__(self):
        self.calls = []

    def relay_once(self, *, tenant_id, limit):
        self.calls.append((tenant_id, limit))
        return 4


def test_service_runs_reaper_scheduler_and_outbox_on_cadence():
    clock = [100.0]
    worker = FakeWorker()
    scheduler = FakeScheduler()
    relay = FakeOutboxRelay()
    service = RunnerService(
        worker, scheduler=scheduler, outbox_relay=relay,
        maintenance_interval_seconds=15,
        scheduler_batch_size=12, outbox_batch_size=34,
        monotonic=lambda: clock[0],
    )

    assert service.run_once() is True
    assert worker.queue.reaped == [41]
    assert len(worker.queue.worker_heartbeats) == 1
    assert scheduler.calls == [(41, 12)]
    assert relay.calls == [(41, 34)]

    service.run_once()
    assert worker.queue.reaped == [41]
    assert len(scheduler.calls) == 1
    assert len(relay.calls) == 1

    clock[0] += 15
    service.run_once()
    assert worker.queue.reaped == [41, 41]
    assert len(worker.queue.worker_heartbeats) == 2
    assert len(scheduler.calls) == 2
    assert len(relay.calls) == 2
    assert len(worker.calls) == 3


def test_service_continues_maintenance_without_leaking_exception_text(caplog):
    worker = FakeWorker(fail_reaper=True)
    scheduler = FakeScheduler()
    relay = FakeOutboxRelay()
    service = RunnerService(
        worker, scheduler=scheduler, outbox_relay=relay,
        monotonic=lambda: 100.0,
    )

    with caplog.at_level(logging.ERROR):
        service.run_once()

    assert scheduler.calls == [(41, 25)]
    assert relay.calls == [(41, 100)]
    assert "service-test-secret" not in caplog.text
    assert "Authorization:" not in caplog.text
    assert "runner maintenance failed component=lease_reaper" in caplog.text


def test_service_does_not_claim_work_after_shutdown_is_requested():
    import threading

    worker = FakeWorker()
    stop = threading.Event()
    stop.set()
    service = RunnerService(worker, monotonic=lambda: 100.0)

    assert service.run_once(shutdown_event=stop) is False
    assert worker.calls == []
    assert worker.queue.reaped == []
