from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class AnnotationFlags:
    enable_sentiment: bool = False
    enable_emotion_annotation: bool = False
    enable_toxicity: bool = False


def normalize_annotation_flags(config: Optional[Dict[str, Any]]) -> AnnotationFlags:
    config = config or {}
    simulation = config.get("simulation") if isinstance(config.get("simulation"), dict) else {}
    return AnnotationFlags(
        enable_sentiment=bool(simulation.get("enable_sentiment", config.get("enable_sentiment", False))),
        enable_emotion_annotation=bool(
            simulation.get("enable_emotion_annotation", config.get("enable_emotion_annotation", False))
        ),
        enable_toxicity=bool(simulation.get("enable_toxicity", config.get("enable_toxicity", False))),
    )


def annotate_text(
    text: str,
    *,
    enable_sentiment: bool = False,
    enable_emotion_annotation: bool = False,
    enable_toxicity: bool = False,
) -> Dict[str, Any]:
    """Return a YSimulator-like annotation payload.

    The implementation is intentionally lightweight: it exposes the same
    switches and a stable output structure so the server/client configs can
    gate downstream processing in a consistent way.
    """

    text = text or ""
    annotations: Dict[str, Any] = {
        "sentiment": None,
        "emotions": None,
        "toxicity": None,
    }

    if enable_sentiment:
        annotations["sentiment"] = {
            "compound": 0.0 if not text.strip() else 0.1,
            "pos": 0.1 if text.strip() else 0.0,
            "neu": 0.9 if text.strip() else 1.0,
            "neg": 0.0,
        }

    if enable_emotion_annotation:
        annotations["emotions"] = {
            "joy": 0.0,
            "sadness": 0.0,
            "anger": 0.0,
            "fear": 0.0,
            "surprise": 0.0,
        }

    if enable_toxicity:
        annotations["toxicity"] = {
            "TOXICITY": 0.0,
            "SEVERE_TOXICITY": 0.0,
            "IDENTITY_ATTACK": 0.0,
            "INSULT": 0.0,
            "PROFANITY": 0.0,
            "THREAT": 0.0,
            "SEXUALLY_EXPLICIT": 0.0,
            "FLIRTATION": 0.0,
        }

    return annotations


def build_annotation_config_from_json(config: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    flags = normalize_annotation_flags(config)
    return {
        "enable_sentiment": flags.enable_sentiment,
        "enable_emotion_annotation": flags.enable_emotion_annotation,
        "enable_toxicity": flags.enable_toxicity,
    }

