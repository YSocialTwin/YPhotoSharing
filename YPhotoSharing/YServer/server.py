from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .annotation_processor import AnnotationProcessor
from .classes.db_middleware import DatabaseMiddleware


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

