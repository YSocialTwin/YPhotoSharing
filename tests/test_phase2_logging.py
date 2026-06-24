import json
import tempfile
from pathlib import Path

from YPhotoSharing.common_utils import setup_logging


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
