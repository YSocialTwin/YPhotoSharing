from __future__ import annotations

import functools
import inspect
import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .annotation_processor import AnnotationProcessor
from .classes.db_middleware import DatabaseMiddleware


def log_server_request(func):
    """Log a server request in the same JSON-line shape used by YSimulator tests."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        started = time.time()
        status_code = 200
        result = None
        error_message = None

        try:
            result = func(self, *args, **kwargs)
            return result
        except Exception as exc:
            status_code = 500
            error_message = str(exc)
            raise
        finally:
            request_logger = getattr(self, "request_logger", None)
            if request_logger is None:
                return

            duration = max(0.0, time.time() - started)
            client_name = kwargs.get("client_id")
            if client_name is None and args:
                signature = inspect.signature(func)
                param_names = [p.name for p in signature.parameters.values() if p.name != "self"]
                if param_names:
                    bound = dict(zip(param_names, args))
                    client_name = bound.get("client_id")

            payload = {
                "request_id": str(uuid.uuid4()),
                "time": datetime.now(timezone.utc).isoformat(),
                "path": func.__name__,
                "client_name": client_name,
                "status_code": status_code,
                "tid": getattr(self, "current_round_id", None),
                "day": getattr(self, "_current_day", None),
                "hour": getattr(self, "_current_hour", None),
                "duration": duration,
            }
            if error_message is not None:
                payload["error"] = error_message
            request_logger.info(json.dumps(payload))

    return wrapper


@dataclass
class OrchestratorServer:
    """Minimal server facade that persists annotations using YSimulator semantics."""

    config: Dict[str, Any] = field(default_factory=dict)
    metadata_service: DatabaseMiddleware = field(default_factory=DatabaseMiddleware)

    def __post_init__(self) -> None:
        simulation = self.config.get("simulation") if isinstance(self.config.get("simulation"), dict) else {}
        self.processor = AnnotationProcessor(
            metadata_service=self.metadata_service,
            enable_sentiment=bool(simulation.get("enable_sentiment", False)),
            enable_emotion_annotation=bool(simulation.get("enable_emotion_annotation", False)),
            enable_toxicity=bool(simulation.get("enable_toxicity", False)),
            perspective_api_key=simulation.get("perspective_api_key"),
        )
        self.metadata_service.initialize_emotions_table()

    def process_annotations(
        self,
        post_id: str,
        user_id: str,
        annotations: Dict[str, Any],
        *,
        is_post: bool = False,
        is_comment: bool = False,
        parent_post_id: Optional[str] = None,
        parent_sentiment: Optional[float] = None,
    ) -> None:
        self.processor._process_annotations(
            post_id=post_id,
            user_id=user_id,
            annotations=annotations,
            is_post=is_post,
            is_comment=is_comment,
            parent_post_id=parent_post_id,
            parent_sentiment=parent_sentiment,
        )
