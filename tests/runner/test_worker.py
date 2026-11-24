from __future__ import annotations

import threading

from app.runner.worker import Worker


class FakeConnection:
    def close(self):
        return None


class FakeQueue:
    def __init__(self):
        self.connection = FakeConnection()
        self.deferred = []
        self.completed = []
        self.failed = []

    def claim(self, **kwargs):
        return {
            "id": "task-1",
            "tenant_id": 7,
            "task_type": "demo",
            "handler_version": "1",
            "lease_owner": "worker-1",
            "fencing_token": 1,
            "attempts": 1,
            "max_attempts": 3,
        }

    def latest_checkpoint(self, task):
        return {
            "sequence_no": 3,
            "handler_version": "1",
            "payload": {"cursor": 27},
            "sha256": "verified-test-digest",
        }

    def heartbeat(self, task, **kwargs):
        return None

    def checkpoint(self, task, payload):
        return 1

    def defer(self, task):
        self.deferred.append(task["id"])

    def complete(self, task):
        self.completed.append(task["id"])

    def fail(self, task, **kwargs):
        self.failed.append(task["id"])


def test_worker_restores_checkpoint_and_defers_when_shutdown_arrives():
    queue = FakeQueue()
    shutdown = threading.Event()
    started = threading.Event()
    observed = {}

    def handler(task, checkpoint, stop_event):
        observed["resume"] = task["resume_checkpoint"]
        started.set()
        assert stop_event.wait(2), "shutdown was not propagated to the active handler"

    worker = Worker(
        queue, heartbeat_queue_factory=FakeQueue, tenant_id=7, worker_id="worker-1",
        handlers={"demo": handler}, lease_seconds=10, heartbeat_seconds=1,
    )
    thread = threading.Thread(target=worker.run_once, kwargs={"shutdown_event": shutdown})
    thread.start()
    assert started.wait(2), "handler did not start"
    shutdown.set()
    thread.join(timeout=3)

    assert not thread.is_alive()
    assert observed["resume"]["payload"] == {"cursor": 27}
    assert queue.deferred == ["task-1"]
    assert queue.completed == []
    assert queue.failed == []
