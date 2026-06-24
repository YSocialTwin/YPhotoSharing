from pathlib import Path
import tempfile

from YPhotoSharing.common_utils import setup_logging


def test_setup_logging_writes_execution_log():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = setup_logging(Path(tmpdir), "client", enable_console=False)
        logger.info("client log message")

        log_file = Path(tmpdir) / "logs" / "execution_client.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "client log message" in content


def test_setup_logging_supports_server_log_name():
    with tempfile.TemporaryDirectory() as tmpdir:
        logger = setup_logging(Path(tmpdir), "server", enable_console=False)
        logger.info("server log message")

        log_file = Path(tmpdir) / "logs" / "execution_server.log"
        assert log_file.exists()
        content = log_file.read_text()
        assert "server log message" in content

