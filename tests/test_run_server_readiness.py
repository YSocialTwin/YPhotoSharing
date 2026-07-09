from importlib import util
from pathlib import Path

import pytest


def _load_run_server_module():
    module_path = Path(__file__).resolve().parents[1] / "run_server.py"
    spec = util.spec_from_file_location("yphotosharing_run_server", module_path)
    module = util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_photo_sharing_server_writes_ray_ready_marker(tmp_path, monkeypatch):
    module = _load_run_server_module()

    config_dir = tmp_path
    (config_dir / "server_config.json").write_text("{}", encoding="utf-8")
    ready_file = config_dir / "ray_ready.temp"

    class _FakeRuntimeContext:
        gcs_address = "127.0.0.1:12345"

    class _FakeActor:
        class _ReadyCall:
            @staticmethod
            def remote():
                return True

        def __init__(self):
            self.is_ready = self._ReadyCall()

    class _FakeOptions:
        @staticmethod
        def remote(**kwargs):
            return _FakeActor()

    class _FakeServer:
        @staticmethod
        def options(**kwargs):
            return _FakeOptions()

    monkeypatch.setattr(module, "validate_config_directory", lambda *args, **kwargs: config_dir)
    monkeypatch.setattr(module, "setup_logging", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "database_exists", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "initialize_database", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "OrchestratorServer", _FakeServer)
    monkeypatch.setattr(module.ray, "init", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.ray, "get_runtime_context", lambda: _FakeRuntimeContext())
    monkeypatch.setattr(module.ray, "get", lambda value: value)
    monkeypatch.setattr(module.ray, "get_actor", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError()))
    monkeypatch.setattr(module.ray, "kill", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.ray, "shutdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(module.sys, "argv", ["run_server.py", "--config", str(config_dir)])

    def _sleep_then_interrupt(_seconds):
        assert ready_file.exists()
        raise KeyboardInterrupt

    monkeypatch.setattr(module.time, "sleep", _sleep_then_interrupt)

    module.main()

    assert ready_file.exists() is False
