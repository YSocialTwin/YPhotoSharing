from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AnnotationProcessor:
    """Persist enabled annotations with the same on/off behavior as YSimulator."""

    enable_sentiment: bool = False
    enable_emotion_annotation: bool = False
    enable_toxicity: bool = False
    stored_posts: List[Dict[str, Any]] = field(default_factory=list)

    def process_post(self, post_id: str, annotations: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"post_id": post_id}
        if self.enable_sentiment and annotations.get("sentiment") is not None:
            payload["sentiment"] = annotations["sentiment"]
        if self.enable_emotion_annotation and annotations.get("emotions") is not None:
            payload["emotions"] = annotations["emotions"]
        if self.enable_toxicity and annotations.get("toxicity") is not None:
            payload["toxicity"] = annotations["toxicity"]
        self.stored_posts.append(payload)
        return payload

