from __future__ import annotations

from typing import Any, Dict, Optional

from .annotation import normalize_annotation_flags
from .text_support.text_annotator import annotate_text


def annotate_content(text: str, config: Optional[Dict[str, Any]] = None, llm_handle=None) -> Dict[str, Any]:
    """Annotate text using the same config switches exposed by YSimulator."""
    flags = normalize_annotation_flags(config)
    return annotate_text(
        text,
        enable_sentiment=flags.enable_sentiment,
        enable_toxicity=flags.enable_toxicity,
        perspective_api_key=flags.perspective_api_key,
        enable_emotions=flags.enable_emotion_annotation,
        llm_handle=llm_handle,
    )
