import json
import logging
import tempfile
from pathlib import Path

from YPhotoSharing.common_utils import build_json_line_file_logger, setup_logging
from YPhotoSharing.YClient.LLM_interactions.usage_tracker import LLMUsageTracker
from YPhotoSharing.YServer.server import log_server_request


def _read_last_json_line(path: Path) -> dict:
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_setup_logging_writes_client_execution_log():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = setup_logging(Path(tmpdir), "client", enable_console=False, instance_name="client_001")
        logger.info("client log message", extra={"extra_data": {"round": 7}})

        log_file = Path(tmpdir) / "logs" / "client_001_execution.log"
        assert log_file.exists()
        payload = _read_last_json_line(log_file)
        assert payload["message"] == "client log message"
        assert payload["round"] == 7
        assert payload["level"] == "INFO"
        assert payload["module"] == "test_phase2_logging"
        assert "timestamp" in payload


def test_setup_logging_writes_client_actor_log():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = setup_logging(Path(tmpdir), "client", enable_console=False, instance_name="client_001")
        logger.info("actor log message")

        log_file = Path(tmpdir) / "logs" / "client_001_actor.log"
        assert log_file.exists()
        payload = _read_last_json_line(log_file)
        assert payload["message"] == "actor log message"
        assert payload["level"] == "INFO"


def test_setup_logging_writes_server_log_with_ysimulator_name():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = setup_logging(Path(tmpdir), "server", enable_console=False, instance_name="orchestrator_server")
        logger.info("server log message")

        log_file = Path(tmpdir) / "logs" / "orchestrator_server_server.log"
        assert log_file.exists()
        payload = _read_last_json_line(log_file)
        assert payload["message"] == "server log message"
        assert payload["level"] == "INFO"
        assert payload["module"] == "test_phase2_logging"
        assert "function" in payload


def test_server_request_logging_matches_y_simulator_shape():
    class DummyServer:
        def __init__(self, log_file: Path):
            self.request_logger = build_json_line_file_logger("dummy.requests", log_file, propagate=False)
            self.current_round_id = "round-7"
            self._current_day = 3
            self._current_hour = 11
            self.logger = build_json_line_file_logger("dummy.server", log_file.parent / "server.log")

        @log_server_request
        def ping(self, client_id: str, payload: str) -> dict:
            return {"client_id": client_id, "payload": payload}

    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "logs" / "_server.log"
        dummy = DummyServer(log_file)
        result = dummy.ping("client_42", "hello")
        assert result["client_id"] == "client_42"

        payload = _read_last_json_line(log_file)
        assert payload["client_name"] == "client_42"
        assert payload["path"] == "ping"
        assert payload["status_code"] == 200
        assert payload["tid"] == "round-7"
        assert payload["day"] == 3
        assert payload["hour"] == 11
        assert payload["duration"] >= 0
        assert "request_id" in payload
        assert "time" in payload


def test_llm_usage_tracker_writes_llm_usage_log_immediately():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "logs" / "client_001_llm_usage.log"
        tracker = LLMUsageTracker(log_file_path=log_file, enable_file_logging=True)
        tracker.record_call("generate_caption", input_tokens=12, output_tokens=8)
        tracker.log_gpu_selection(
            {
                "physical_gpu_id": 1,
                "logical_gpu_id": 0,
                "assignment_method": "ray_assigned",
                "cuda_visible_devices": "1",
            },
            model_name="test-model",
            backend="vllm",
        )

        assert log_file.exists()
        lines = [line for line in log_file.read_text().splitlines() if line.strip()]
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["method"] == "generate_caption"
        assert first["input_tokens"] == 12
        assert first["output_tokens"] == 8
        assert first["total_tokens"] == 20
        assert first["cumulative_calls"] == 1

        second = json.loads(lines[1])
        assert second["event"] == "gpu_selection"
        assert second["backend"] == "vllm"
        assert second["model"] == "test-model"


def test_server_request_logging_negative_day_hour_coerced_to_zero():
    class DummyServerNegative:
        def __init__(self, log_file: Path):
            self.request_logger = build_json_line_file_logger("dummy.requests", log_file, propagate=False)
            self.current_round_id = "round-init"
            self._current_day = -1
            self._current_hour = -1
            self.logger = build_json_line_file_logger("dummy.server", log_file.parent / "server.log")

        @log_server_request
        def register(self, client_id: str) -> dict:
            return {"client_id": client_id}

    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "logs" / "_server.log"
        dummy = DummyServerNegative(log_file)
        dummy.register("client_init")

        payload = _read_last_json_line(log_file)
        assert payload["client_name"] == "client_init"
        assert payload["path"] == "register"
        assert payload["day"] == 0
        assert payload["hour"] == 0


def test_client_action_logging_writes_client_log_and_summaries():
    from YPhotoSharing.YClient.client import SimulationClient
    from logging.handlers import RotatingFileHandler
    import shutil

    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)
        (config_path / "logs").mkdir(parents=True, exist_ok=True)
        
        client_cls = SimulationClient.__ray_metadata__.modified_class
        client = object.__new__(client_cls)
        client.client_id = "client_test"
        client.config_path = config_path
        
        client.logger = logging.getLogger("dummy.client")
        action_log_file = config_path / "logs" / "client_test_client.log"
        action_handler = RotatingFileHandler(
            action_log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        class ActionFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                return record.getMessage()
        action_handler.setFormatter(ActionFormatter())
        client.action_logger = logging.getLogger("dummy.client_test.Actions")
        client.action_logger.setLevel(logging.INFO)
        client.action_logger.handlers = [action_handler]
        client.action_logger.propagate = False
        
        client.hourly_actions = []
        client.daily_actions = []

        client._log_action("agent_1", "post_photo", 0.05, True, 1, 3)
        client._log_action("agent_2", "comment", 0.02, True, 1, 3)

        assert action_log_file.exists()
        lines = [line for line in action_log_file.read_text().splitlines() if line.strip()]
        assert len(lines) == 2
        
        entry1 = json.loads(lines[0])
        assert entry1["agent_name"] == "agent_1"
        assert entry1["method_name"] == "post_photo"
        assert entry1["execution_time_seconds"] == 0.05
        assert entry1["success"] is True

        client._log_hourly_summary(1, 3)
        
        lines = [line for line in action_log_file.read_text().splitlines() if line.strip()]
        assert len(lines) == 3
        
        hourly_summary = json.loads(lines[2])
        assert hourly_summary["summary_type"] == "hourly"
        assert hourly_summary["day"] == 1
        assert hourly_summary["slot"] == 3
        assert hourly_summary["total_actions"] == 2
        assert hourly_summary["actions_by_method"] == {"post_photo": 1, "comment": 1}

        client._log_daily_summary(1)
        
        lines = [line for line in action_log_file.read_text().splitlines() if line.strip()]
        assert len(lines) == 4
        
        daily_summary = json.loads(lines[3])
        assert daily_summary["summary_type"] == "daily"
        assert daily_summary["day"] == 1
        assert daily_summary["total_actions"] == 2


def test_llm_url_stripping_and_actor_log_configuration():
    from YPhotoSharing.YClient.LLM_interactions.llm_service import _build_ollama_url, LLMService
    import tempfile
    
    # 1. Verify URL stripping
    assert _build_ollama_url({"address": "localhost:8000/v1"}) == "http://localhost:8000"
    assert _build_ollama_url({"address": "http://127.0.0.1:8000/v1"}) == "http://127.0.0.1:8000"
    assert _build_ollama_url({"address": "localhost", "port": 11434}) == "http://localhost:11434"
    assert _build_ollama_url({"address": "127.0.0.1:11434/v1"}) == "http://127.0.0.1:11434"
    
    # 2. Verify actor logging configuration
    with tempfile.TemporaryDirectory() as tmpdir:
        # Avoid full __init__ by using object.__new__
        service_cls = LLMService.__ray_metadata__.modified_class
        service = object.__new__(service_cls)
        
        logging_config = {
            "log_dir": tmpdir,
            "instance_name": "test_llm_actor",
            "enable_actor_log": True,
        }
        
        service._setup_logger(logging_config)
        
        # Log a test message using the module logger
        from YPhotoSharing.YClient.LLM_interactions.llm_service import logger as llm_logger
        llm_logger.info("hello from llm actor")
        
        log_file = Path(tmpdir) / "test_llm_actor_actor.log"
        assert log_file.exists()
        
        payload = _read_last_json_line(log_file)
        assert payload["message"] == "hello from llm actor"
        assert payload["level"] == "INFO"
        assert "timestamp" in payload


def test_vllm_actor_log_configuration():
    from YPhotoSharing.YClient.LLM_interactions.vllm_service import VLLMService
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Avoid full __init__ by using object.__new__
        service_cls = VLLMService.__ray_metadata__.modified_class
        service = object.__new__(service_cls)
        
        logging_config = {
            "log_dir": tmpdir,
            "instance_name": "test_vllm_actor",
            "enable_actor_log": True,
        }
        
        service._setup_logger(logging_config)
        
        # Log a test message using the module logger
        from YPhotoSharing.YClient.LLM_interactions.vllm_service import logger as vllm_logger
        vllm_logger.info("hello from vllm actor")
        
        log_file = Path(tmpdir) / "test_vllm_actor_actor.log"
        assert log_file.exists()
        
        payload = _read_last_json_line(log_file)
        assert payload["message"] == "hello from vllm actor"
        assert payload["level"] == "INFO"
        assert "timestamp" in payload


def test_action_formatter_json_conversion():
    from YPhotoSharing.YClient.client import ActionFormatter
    import logging

    formatter = ActionFormatter()
    
    # Test record with raw string and extra_data
    record1 = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test_path",
        lineno=10,
        msg="Agent action completed",
        args=(),
        exc_info=None,
    )
    record1.extra_data = {
        "agent_id": "user-123",
        "action": "comment",
        "day": 2,
    }
    
    formatted1 = formatter.format(record1)
    data1 = json.loads(formatted1)
    assert data1["message"] == "Agent action completed"
    assert data1["level"] == "INFO"
    assert data1["agent_id"] == "user-123"
    assert data1["action"] == "comment"
    assert data1["day"] == 2
    assert "timestamp" in data1

    # Test record that is already a valid JSON string
    json_str = '{"time": "2026-06-25 12:00:00", "agent_name": "bob", "success": true}'
    record2 = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test_path",
        lineno=20,
        msg=json_str,
        args=(),
        exc_info=None,
    )
    formatted2 = formatter.format(record2)
    assert formatted2 == json_str




