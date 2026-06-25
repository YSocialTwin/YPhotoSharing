from __future__ import annotations

from typing import Any, Dict, Optional

from .annotation import annotate_text, normalize_annotation_flags


def annotate_content(text: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Annotate text using the same config switches exposed by YSimulator."""
    flags = normalize_annotation_flags(config)
    return annotate_text(
        text,
        enable_sentiment=flags.enable_sentiment,
        enable_emotion_annotation=flags.enable_emotion_annotation,
        enable_toxicity=flags.enable_toxicity,
    )

