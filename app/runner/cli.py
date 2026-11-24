"""Secret-safe portable entry point for a configured RunnerService."""
from __future__ import annotations

import importlib
import logging
import os
import re
import signal
import threading
from typing import Any

_LOG = logging.getLogger("hussam.runner.cli")
_FACTORY_PATTERN = re.compile(
    r"(?P<module>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*):"
    r"(?P<factory>[A-Za-z_][A-Za-z0-9_]*)"
)


def load_runner_service(factory_spec: str | None = None) -> Any:
    """Load a trusted application factory; never derive imports from task data."""
    spec = factory_spec or os.getenv("HUSSAM_RUNNER_FACTORY", "")
    match = _FACTORY_PATTERN.fullmatch(spec)
    if match is None:
        raise ValueError(
            "HUSSAM_RUNNER_FACTORY must be a trusted module path and callable name"
        )

    try:
        module = importlib.import_module(match.group("module"))
        factory = getattr(module, match.group("factory"))
        if not callable(factory):
            raise TypeError("configured factory is not callable")
        service = factory()
    except Exception as exc:
        # Do not include exception text: import/factory errors can contain credentials.
        raise RuntimeError(
            f"runner factory initialization failed ({type(exc).__name__})"
        ) from None

    if not callable(getattr(service, "serve", None)):
        raise TypeError("configured factory must return an object with serve()")
    return service


def main() -> int:
    """Run the configured service until a graceful process-stop signal arrives."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        service = load_runner_service()
    except Exception as exc:
        _LOG.error("runner startup failed error_type=%s", type(exc).__name__)
        return 2

    stop_event = threading.Event()

    def request_stop(signum: int, _frame: Any) -> None:
        _LOG.info("runner shutdown requested signal=%s", signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    try:
        service.serve(stop_event=stop_event)
    except Exception as exc:
        _LOG.error("runner service failed error_type=%s", type(exc).__name__)
        return 1

    _LOG.info("runner service stopped")
    return 0
