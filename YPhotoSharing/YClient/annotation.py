from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .text_support.text_annotator import annotate_text


@dataclass(frozen=True)
class AnnotationFlags:
    enable_sentiment: bool = False
    enable_emotion_annotation: bool = False
    enable_toxicity: bool = False
    perspective_api_key: Optional[str] = None


def normalize_annotation_flags(config: Optional[Dict[str, Any]]) -> AnnotationFlags:
    config = config or {}
    simulation = config.get("simulation") if isinstance(config.get("simulation"), dict) else {}
    return AnnotationFlags(
        enable_sentiment=bool(simulation.get("enable_sentiment", config.get("enable_sentiment", False))),
        enable_emotion_annotation=bool(
            simulation.get("enable_emotion_annotation", config.get("enable_emotion_annotation", False))
        ),
        enable_toxicity=bool(simulation.get("enable_toxicity", config.get("enable_toxicity", False))),
        perspective_api_key=simulation.get("perspective_api_key", config.get("perspective_api_key")),
    )


def build_annotation_config_from_json(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    flags = normalize_annotation_flags(config)
    return {
        "enable_sentiment": flags.enable_sentiment,
        "enable_emotion_annotation": flags.enable_emotion_annotation,
        "enable_toxicity": flags.enable_toxicity,
        "perspective_api_key": flags.perspective_api_key,
    }
