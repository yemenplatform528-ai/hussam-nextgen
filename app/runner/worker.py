"""Minimal worker loop. Register handlers in code; never trust payload module names."""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from app.runner.postgres import LeaseLost, PostgresQueue
from app.runner.redaction import redact_text

Handler = Callable[[dict[str, Any], Callable[[dict[str, Any]], int]], None]


class Worker:
    def __init__(self, queue: PostgresQueue, *, tenant_id: int, worker_id: str,
                 handlers: dict[str, Handler], lease_seconds: int = 60,
                 heartbeat_seconds: int = 15):
        if heartbeat_seconds >= lease_seconds / 2:
            raise ValueError("heartbeat interval must be less than half the lease")
        self.queue = queue
        self.tenant_id = tenant_id
        self.worker_id = worker_id
        self.handlers = dict(handlers)
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.log = logging.getLogger("hussam.runner")

    def run_once(self) -> bool:
        task = self.queue.claim(tenant_id=self.tenant_id, worker_id=self.worker_id,
                                lease_seconds=self.lease_seconds)
        if task is None:
            return False
        handler = self.handlers.get(task["task_type"])
        if handler is None:
            self.queue.fail(task, error_code="HANDLER_NOT_REGISTERED",
                            safe_summary="No allowlisted handler is registered")
            return True

        stop = threading.Event()
        lost = threading.Event()

        def renew() -> None:
            while not stop.wait(self.heartbeat_seconds):
                try:
                    self.queue.heartbeat(task, lease_seconds=self.lease_seconds)
                except LeaseLost:
                    lost.set()
                    stop.set()
                except Exception:
                    # Fail closed: stop the handler; never log raw exception text.
                    lost.set()
                    stop.set()

        thread = threading.Thread(target=renew, name="runner-lease-renewal", daemon=True)
        thread.start()
        try:
            handler(task, lambda state: self.queue.checkpoint(task, state))
            if lost.is_set():
                raise LeaseLost("lease renewal failed")
            self.queue.complete(task)
        except LeaseLost:
            self.log.warning("runner lease lost task_id=%s", task["id"])
        except Exception as exc:
            if not lost.is_set():
                self.queue.fail(task, error_code="HANDLER_ERROR",
                                safe_summary=redact_text(type(exc).__name__))
            self.log.error("runner handler failed task_id=%s error_type=%s",
                           task["id"], redact_text(type(exc).__name__))
        finally:
            stop.set()
            thread.join(timeout=self.heartbeat_seconds + 1)
        return True

    def serve(self, *, poll_seconds: float = 1.0,
              stop_event: threading.Event | None = None) -> None:
        stop_event = stop_event or threading.Event()
        while not stop_event.is_set():
            try:
                did_work = self.run_once()
            except Exception as exc:
                self.log.error("runner loop error_type=%s",
                               redact_text(type(exc).__name__))
                did_work = False
            if not did_work:
                stop_event.wait(poll_seconds)
