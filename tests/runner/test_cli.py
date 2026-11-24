from __future__ import annotations

import signal
import sys
import types

import pytest

from app.runner import cli


def test_factory_spec_must_be_a_trusted_module_callable():
    with pytest.raises(ValueError, match="HUSSAM_RUNNER_FACTORY"):
        cli.load_runner_service("malicious path;print:factory")


def test_factory_loader_returns_service_from_configured_module(monkeypatch):
    expected = object()
    module = types.ModuleType("runner_factory_test")
    module.build = lambda: expected
    monkeypatch.setitem(sys.modules, "runner_factory_test", module)

    assert cli.load_runner_service("runner_factory_test:build") is expected


def test_factory_loader_rejects_objects_without_serve(monkeypatch):
    module = types.ModuleType("runner_factory_invalid")
    module.build = lambda: object()
    monkeypatch.setitem(sys.modules, "runner_factory_invalid", module)

    with pytest.raises(TypeError, match="serve"):
        cli.load_runner_service("runner_factory_invalid:build")


def test_main_passes_signal_shutdown_to_service(monkeypatch):
    observed = {}

    handlers = {}

    class FakeService:
        def serve(self, *, stop_event):
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            observed["stop_event"] = stop_event
            assert stop_event.is_set()

    module = types.ModuleType("runner_factory_signal_test")
    module.build = FakeService
    monkeypatch.setitem(sys.modules, "runner_factory_signal_test", module)
    monkeypatch.setenv("HUSSAM_RUNNER_FACTORY", "runner_factory_signal_test:build")

    monkeypatch.setattr(
        cli.signal, "signal", lambda sig, handler: handlers.__setitem__(sig, handler)
    )
    monkeypatch.setattr(cli.logging, "basicConfig", lambda **kwargs: None)

    assert cli.main() == 0
    assert signal.SIGTERM in handlers and signal.SIGINT in handlers
    assert observed["stop_event"].is_set()


def test_main_does_not_log_factory_exception_message(monkeypatch, caplog):
    module = types.ModuleType("runner_factory_secret_test")

    def fail():
        raise RuntimeError("postgres://secret-user:secret-password@db.internal")

    module.build = fail
    monkeypatch.setitem(sys.modules, "runner_factory_secret_test", module)
    monkeypatch.setenv("HUSSAM_RUNNER_FACTORY", "runner_factory_secret_test:build")
    monkeypatch.setattr(cli.logging, "basicConfig", lambda **kwargs: None)

    with caplog.at_level("ERROR"):
        assert cli.main() == 2

    assert "secret-password" not in caplog.text
    assert "db.internal" not in caplog.text
    assert "error_type=RuntimeError" in caplog.text
