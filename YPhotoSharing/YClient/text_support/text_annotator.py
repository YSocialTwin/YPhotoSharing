from __future__ import annotations

from typing import Dict, List, Optional

import ray

from .annotations import toxicity, vader_sentiment
from .cleaning import extract_components


def _normalize_emotions(result) -> List[str]:
    if result is None:
        return []
    if isinstance(result, list):
        return [str(item).strip() for item in result if str(item).strip()]
    if isinstance(result, str):
        cleaned = result.replace("[", "").replace("]", "")
        parts = [part.strip().strip("'\"") for part in cleaned.split(",")]
        return [part for part in parts if part]
    return []


def annotate_text(
    text: str,
    enable_sentiment: bool = True,
    enable_toxicity: bool = False,
    perspective_api_key: Optional[str] = None,
    enable_emotions: bool = False,
    enable_emotion_annotation: Optional[bool] = None,
    llm_handle=None,
    defer_emotions: bool = False,
) -> Dict:
    if enable_emotion_annotation is not None:
        enable_emotions = enable_emotion_annotation

    annotations: Dict[str, object] = {}
    annotations["hashtags"] = [h[1:] for h in extract_components(text, c_type="hashtags")]
    annotations["mentions"] = [m[1:] for m in extract_components(text, c_type="mentions")]

    annotations["sentiment"] = vader_sentiment(text) if enable_sentiment else None
    annotations["toxicity"] = toxicity(text, perspective_api_key) if enable_toxicity else None

    if enable_emotions and llm_handle is not None:
        try:
            if defer_emotions:
                annotations["emotions"] = llm_handle.extract_emotions.remote(text)
            else:
                emotions = ray.get(llm_handle.extract_emotions.remote(text))
                annotations["emotions"] = _normalize_emotions(emotions)
        except Exception:
            annotations["emotions"] = [] if not defer_emotions else None
    else:
        annotations["emotions"] = None

    return annotations


def prepare_sentiment_data(
    post_id: str,
    user_id: str,
    topic_ids: List[str],
    round_id: str,
    sentiment_scores: Dict[str, float],
    sentiment_parent: Optional[str] = None,
    is_post: bool = False,
    is_comment: bool = False,
    is_reaction: bool = False,
) -> List[Dict]:
    entries = []
    for topic_id in topic_ids:
        entries.append(
            {
                "post_id": post_id,
                "user_id": user_id,
                "topic_id": topic_id,
                "round": round_id,
                "neg": sentiment_scores.get("neg"),
                "pos": sentiment_scores.get("pos"),
                "neu": sentiment_scores.get("neu"),
                "compound": sentiment_scores.get("compound"),
                "sentiment_parent": sentiment_parent,
                "is_post": 1 if is_post else 0,
                "is_comment": 1 if is_comment else 0,
                "is_reaction": 1 if is_reaction else 0,
            }
        )
    return entries


def prepare_toxicity_data(post_id: str, toxicity_scores: Dict[str, float]) -> Dict:
    return {
        "post_id": post_id,
        "toxicity": toxicity_scores.get("TOXICITY", 0.0),
        "severe_toxicity": toxicity_scores.get("SEVERE_TOXICITY", 0.0),
        "identity_attack": toxicity_scores.get("IDENTITY_ATTACK", 0.0),
        "insult": toxicity_scores.get("INSULT", 0.0),
        "profanity": toxicity_scores.get("PROFANITY", 0.0),
        "threat": toxicity_scores.get("THREAT", 0.0),
        "sexually_explicit": toxicity_scores.get("SEXUALLY_EXPLICIT", 0.0),
        "flirtation": toxicity_scores.get("FLIRTATION", 0.0),
    }
