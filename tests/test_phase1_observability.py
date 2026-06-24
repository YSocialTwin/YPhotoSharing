import json
import tempfile
from pathlib import Path

from YPhotoSharing.common_utils import build_structured_file_logger
from YPhotoSharing.YClient.LLM_interactions.llm_service import LLMService


def _read_last_json_line(path: Path) -> dict:
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_structured_action_logger_writes_json_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "logs" / "client_001_actions.log"
        logger = build_structured_file_logger("YPhotoSharing.ClientActions.client_001", log_file)
        logger.info(
            "Agent action completed",
            extra={"extra_data": {"agent_id": "u1", "action": "comment"}},
        )

        assert log_file.exists()
        payload = _read_last_json_line(log_file)
        assert payload["message"] == "Agent action completed"
        assert payload["agent_id"] == "u1"
        assert payload["action"] == "comment"
        assert payload["module"] == "test_phase1_observability"


def test_prompt_logger_records_prompt_metadata():
    with tempfile.TemporaryDirectory() as tmpdir:
        service_cls = LLMService.__ray_metadata__.modified_class
        service = object.__new__(service_cls)
        service.prompt_logger = build_structured_file_logger(
            "YPhotoSharing.ClientPrompts.client_001",
            Path(tmpdir) / "logs" / "client_001_prompts.log",
            level=10,
            backup_count=3,
            max_bytes=50 * 1024 * 1024,
            indent=2,
            include_module=False,
            propagate=False,
        )

        service._log_prompt(
            "generate_comment",
            {
                "caption": "A day at the beach",
                "author": "alice",
                "image_url": "https://example.com/image.jpg",
                "agent_attrs": {"memory_context": "past interactions"},
                "peers_opinions": [0.2, 0.6],
            },
            "Nice photo!",
            backend="vision",
        )

        log_file = Path(tmpdir) / "logs" / "client_001_prompts.log"
        assert log_file.exists()
        payload = json.loads(log_file.read_text())
        assert payload["template"] == "generate_comment"
        assert payload["backend"] == "vision"
        assert payload["response"] == "Nice photo!"
        assert payload["input_keys"] == ["agent_attrs", "author", "caption", "image_url", "peers_opinions"]
        assert payload["inputs"]["image_url"] == "<redacted>"
        assert payload["inputs"]["agent_attrs"] == ["memory_context"]
        assert payload["inputs"]["peers_opinions"] == 2
