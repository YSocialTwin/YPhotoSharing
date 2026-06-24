import json
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


def test_setup_logging_writes_server_log_with_normalized_name():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = setup_logging(Path(tmpdir), "server", enable_console=False, instance_name="orchestrator_server")
        logger.info("server log message")

        log_file = Path(tmpdir) / "logs" / "orchestrator_server.log"
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
