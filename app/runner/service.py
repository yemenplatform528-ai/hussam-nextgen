"""Process supervisor for durable queue, schedule, outbox, and lease maintenance."""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from app.runner.redaction import redact_text
from app.runner.worker import Worker

Maintenance = Any


class RunnerService:
    """Run a worker together with periodic scheduler, outbox, and reaper work.

    The service is tenant-scoped through its Worker. Scheduler and outbox adapters
    are optional and must be configured with trusted allowlists and connections.
    """

    def __init__(
        self,
        worker: Worker,
        *,
        scheduler: Maintenance | None = None,
        outbox_relay: Maintenance | None = None,
        maintenance_interval_seconds: float = 15.0,
        scheduler_batch_size: int = 25,
        outbox_batch_size: int = 100,
        monotonic: Callable[[], float] = time.monotonic,
    ):
        if maintenance_interval_seconds <= 0:
            raise ValueError("maintenance interval must be positive")
        if not 1 <= scheduler_batch_size <= 250:
            raise ValueError("scheduler batch size must be between 1 and 250")
        if not 1 <= outbox_batch_size <= 500:
            raise ValueError("outbox batch size must be between 1 and 500")
        self.worker = worker
        self.scheduler = scheduler
        self.outbox_relay = outbox_relay
        self.maintenance_interval_seconds = maintenance_interval_seconds
        self.scheduler_batch_size = scheduler_batch_size
        self.outbox_batch_size = outbox_batch_size
        self.monotonic = monotonic
        self._next_maintenance = 0.0
        self.log = logging.getLogger("hussam.runner.service")

    def _maintain(self) -> None:
        tenant_id = self.worker.tenant_id
        operations = [
            ("worker_heartbeat", lambda: self.worker.queue.touch_worker(
                worker_id=self.worker.worker_id,
                process_instance_id=self.worker.process_instance_id,
                build_version=self.worker.build_version,
            )),
            ("lease_reaper", lambda: self.worker.queue.reap_exhausted(tenant_id=tenant_id)),
        ]
        if self.scheduler is not None:
            operations.append((
                "scheduler",
                lambda: self.scheduler.materialize_due(
                    tenant_id=tenant_id, limit=self.scheduler_batch_size
                ),
            ))
        if self.outbox_relay is not None:
            operations.append((
                "outbox_relay",
                lambda: self.outbox_relay.relay_once(
                    tenant_id=tenant_id, limit=self.outbox_batch_size
                ),
            ))

        for component, operation in operations:
            try:
                count = operation()
                self.log.info("runner maintenance component=%s processed=%s",
                              component, count)
            except Exception as exc:
                # Never persist exception messages; they may contain provider credentials.
                self.log.error("runner maintenance failed component=%s error_type=%s",
                               component, redact_text(type(exc).__name__))

    def run_once(self, *, shutdown_event: threading.Event | None = None) -> bool:
        if shutdown_event is not None and shutdown_event.is_set():
            return False
        now = self.monotonic()
        if now >= self._next_maintenance:
            self._next_maintenance = now + self.maintenance_interval_seconds
            self._maintain()
        return self.worker.run_once(shutdown_event=shutdown_event)

    def serve(self, *, poll_seconds: float = 1.0,
              stop_event: threading.Event | None = None) -> None:
        if poll_seconds < 0:
            raise ValueError("poll interval cannot be negative")
        stop_event = stop_event or threading.Event()
        while not stop_event.is_set():
            try:
                did_work = self.run_once(shutdown_event=stop_event)
            except Exception as exc:
                self.log.error("runner service loop error_type=%s",
                               redact_text(type(exc).__name__))
                did_work = False
            if not did_work:
                stop_event.wait(poll_seconds)
