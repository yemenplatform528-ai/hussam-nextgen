"""Worker loop with lease renewal, verified checkpoint restore, and cooperative shutdown."""
from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from typing import Any

from app.runner.postgres import CheckpointIntegrityError, LeaseLost, PostgresQueue
from app.runner.redaction import redact_text

Handler = Callable[[dict[str, Any], Callable[[dict[str, Any]], int], threading.Event], None]
QueueFactory = Callable[[], PostgresQueue]


class Worker:
    def __init__(self, queue: PostgresQueue, *, heartbeat_queue_factory: QueueFactory,
                 tenant_id: int, worker_id: str, handlers: dict[str, Handler],
                 lease_seconds: int = 60, heartbeat_seconds: int = 15,
                 build_version: str = "prototype-v1"):
        if lease_seconds < 10 or heartbeat_seconds < 1 or heartbeat_seconds >= lease_seconds / 2:
            raise ValueError("heartbeat must be positive and less than half the lease")
        self.queue = queue
        self.heartbeat_queue_factory = heartbeat_queue_factory
        self.tenant_id = tenant_id
        self.worker_id = worker_id
        self.process_instance_id = uuid.uuid4()
        self.build_version = build_version
        self.handlers = dict(handlers)
        self.lease_seconds = lease_seconds
        self.heartbeat_seconds = heartbeat_seconds
        self.log = logging.getLogger("hussam.runner")

    def run_once(self, *, shutdown_event: threading.Event | None = None) -> bool:
        task = self.queue.claim(tenant_id=self.tenant_id, worker_id=self.worker_id,
                                lease_seconds=self.lease_seconds)
        if task is None:
            return False
        handler = self.handlers.get(task["task_type"])
        if handler is None:
            self.queue.fail(task, error_code="HANDLER_NOT_REGISTERED",
                            safe_summary="No allowlisted handler is registered")
            return True

        handler_stop = threading.Event()
        heartbeat_stop = threading.Event()
        lost = threading.Event()
        shutdown_seen = threading.Event()
        watcher_done = threading.Event()

        def watch_shutdown() -> None:
            if shutdown_event is None:
                return
            while not watcher_done.wait(0.1):
                if shutdown_event.is_set():
                    shutdown_seen.set()
                    handler_stop.set()
                    return

        watcher = None
        if shutdown_event is not None:
            watcher = threading.Thread(
                target=watch_shutdown, name="runner-shutdown-watcher", daemon=True
            )
            watcher.start()

        def renew() -> None:
            heartbeat_queue = None
            try:
                heartbeat_queue = self.heartbeat_queue_factory()
                while not heartbeat_stop.wait(self.heartbeat_seconds):
                    heartbeat_queue.heartbeat(task, lease_seconds=self.lease_seconds)
            except Exception:
                # Fail closed and suppress exception text; never share the worker connection.
                lost.set()
                handler_stop.set()
                heartbeat_stop.set()
            finally:
                if heartbeat_queue is not None:
                    try:
                        heartbeat_queue.connection.close()
                    except Exception:
                        pass

        thread = threading.Thread(target=renew, name="runner-lease-renewal", daemon=True)
        thread.start()
        try:
            task["resume_checkpoint"] = self.queue.latest_checkpoint(task)
            handler(task, lambda state: self.queue.checkpoint(task, state), handler_stop)
            if lost.is_set():
                raise LeaseLost("lease renewal failed")
            if shutdown_seen.is_set():
                self.queue.defer(task)
                self.log.info("runner task deferred for shutdown task_id=%s", task["id"])
            else:
                self.queue.complete(task)
        except LeaseLost:
            self.log.warning("runner lease lost task_id=%s", task["id"])
        except CheckpointIntegrityError:
            if not lost.is_set() and not shutdown_seen.is_set():
                try:
                    self.queue.fail(
                        task, error_code="CHECKPOINT_INVALID",
                        safe_summary="Persisted checkpoint failed integrity or version validation",
                    )
                except LeaseLost:
                    self.log.warning("runner lease lost while recording checkpoint failure task_id=%s",
                                     task["id"])
            self.log.error("runner checkpoint validation failed task_id=%s", task["id"])
        except Exception as exc:
            if shutdown_seen.is_set() and not lost.is_set():
                try:
                    self.queue.defer(task)
                except LeaseLost:
                    self.log.warning("runner lease lost while deferring task_id=%s", task["id"])
            elif not lost.is_set():
                try:
                    self.queue.fail(task, error_code="HANDLER_ERROR",
                                    safe_summary=redact_text(type(exc).__name__))
                except LeaseLost:
                    self.log.warning("runner lease lost while recording failure task_id=%s",
                                     task["id"])
            self.log.error("runner handler failed task_id=%s error_type=%s",
                           task["id"], redact_text(type(exc).__name__))
        finally:
            watcher_done.set()
            handler_stop.set()
            heartbeat_stop.set()
            thread.join(timeout=self.heartbeat_seconds + 1)
            if watcher is not None:
                watcher.join(timeout=0.2)
        return True

    def serve(self, *, poll_seconds: float = 1.0,
              stop_event: threading.Event | None = None) -> None:
        stop_event = stop_event or threading.Event()
        while not stop_event.is_set():
            try:
                did_work = self.run_once(shutdown_event=stop_event)
            except Exception as exc:
                self.log.error("runner loop error_type=%s",
                               redact_text(type(exc).__name__))
                did_work = False
            if not did_work:
                stop_event.wait(poll_seconds)
