"""Small, dependency-light production observability primitives."""
from __future__ import annotations

import json
import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")
PROCESS_START_TIME = time.time()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


@dataclass
class Metrics:
    _lock: Lock = field(default_factory=Lock)
    requests_total: int = 0
    requests_failed: int = 0
    request_seconds: float = 0.0
    readiness_ok: int = 0

    def observe_request(self, elapsed: float, failed: bool = False) -> None:
        with self._lock:
            self.requests_total += 1
            self.request_seconds += elapsed
            if failed:
                self.requests_failed += 1

    def set_readiness(self, ready: bool) -> None:
        with self._lock:
            self.readiness_ok = 1 if ready else 0

    def prometheus(self) -> str:
        with self._lock:
            return (
                "# HELP hussam_info Platform build and runtime information.\n"
                "# TYPE hussam_info gauge\n"
                'hussam_info{platform="hussam-nextgen"} 1\n'
                "# HELP hussam_process_start_time_seconds Unix start time of the API process.\n"
                "# TYPE hussam_process_start_time_seconds gauge\n"
                f"hussam_process_start_time_seconds {PROCESS_START_TIME:.6f}\n"
                "# HELP hussam_readiness_ok Whether the last deep readiness probe succeeded.\n"
                "# TYPE hussam_readiness_ok gauge\n"
                f"hussam_readiness_ok {self.readiness_ok}\n"
                "# HELP hussam_http_requests_total Total HTTP requests.\n"
                "# TYPE hussam_http_requests_total counter\n"
                f"hussam_http_requests_total {self.requests_total}\n"
                "# HELP hussam_http_requests_failed_total HTTP requests returning 5xx.\n"
                "# TYPE hussam_http_requests_failed_total counter\n"
                f"hussam_http_requests_failed_total {self.requests_failed}\n"
                "# HELP hussam_http_request_seconds_total Sum of observed request durations.\n"
                "# TYPE hussam_http_request_seconds_total counter\n"
                f"hussam_http_request_seconds_total {self.request_seconds:.6f}\n"
            )


metrics = Metrics()
