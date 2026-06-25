from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict

from detoxify import Detoxify
from nltk.sentiment import SentimentIntensityAnalyzer
from perspective import PerspectiveAPI

logger = logging.getLogger(__name__)

_detoxify_model = None
_sentiment_analyzer = None


def _configure_model_cache_env() -> None:
    root = Path(os.environ.get("YPHOTO_MODEL_CACHE_DIR", "~/.cache/yphoto_models")).expanduser()
    hf_home = root / "huggingface"
    transformers_cache = hf_home / "transformers"
    hub_cache = hf_home / "hub"
    torch_home = root / "torch"

    for path in (root, hf_home, transformers_cache, hub_cache, torch_home):
        path.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("YPHOTO_MODEL_CACHE_DIR", str(root))
    os.environ.setdefault("HF_HOME", str(hf_home))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(transformers_cache))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(hub_cache))
    os.environ.setdefault("TORCH_HOME", str(torch_home))


def _get_detoxify_model() -> Detoxify:
    global _detoxify_model
    if _detoxify_model is None:
        _configure_model_cache_env()
        logger.info("Initializing Detoxify model for toxicity scoring")
        _detoxify_model = Detoxify("original")
    return _detoxify_model


def _get_sentiment_analyzer() -> SentimentIntensityAnalyzer:
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        try:
            _sentiment_analyzer = SentimentIntensityAnalyzer()
        except LookupError:
            import nltk

            nltk.download("vader_lexicon", quiet=True)
            _sentiment_analyzer = SentimentIntensityAnalyzer()
    return _sentiment_analyzer


def vader_sentiment(text: str) -> dict:
    """Return VADER sentiment scores in the same structure as YSimulator."""
    return _get_sentiment_analyzer().polarity_scores(text or "")


def detoxify_toxicity(text: str) -> dict:
    """Return toxicity scores mapped to the Perspective API taxonomy."""
    try:
        scores = _get_detoxify_model().predict(text or "")
        return {
            "TOXICITY": scores.get("toxicity", 0.0),
            "SEVERE_TOXICITY": scores.get("severe_toxicity", 0.0),
            "IDENTITY_ATTACK": scores.get("identity_attack", 0.0),
            "INSULT": scores.get("insult", 0.0),
            "PROFANITY": scores.get("obscene", 0.0),
            "THREAT": scores.get("threat", 0.0),
            "SEXUALLY_EXPLICIT": scores.get("sexual_explicit", 0.0),
            "FLIRTATION": 0.0,
        }
    except Exception as exc:
        logger.warning("detoxify_toxicity failed: %s", exc)
        return {}


def toxicity(text: str, api_key: str | None) -> dict:
    """Return toxicity scores using Perspective API or local Detoxify fallback."""
    if api_key:
        try:
            perspective = PerspectiveAPI(api_key)
            toxicity_score = perspective.score(
                text or "",
                tests=[
                    "TOXICITY",
                    "SEVERE_TOXICITY",
                    "IDENTITY_ATTACK",
                    "INSULT",
                    "PROFANITY",
                    "THREAT",
                    "SEXUALLY_EXPLICIT",
                    "FLIRTATION",
                ],
            )
            return {
                "TOXICITY": toxicity_score["TOXICITY"],
                "SEVERE_TOXICITY": toxicity_score["SEVERE_TOXICITY"],
                "IDENTITY_ATTACK": toxicity_score["IDENTITY_ATTACK"],
                "INSULT": toxicity_score["INSULT"],
                "PROFANITY": toxicity_score["PROFANITY"],
                "THREAT": toxicity_score["THREAT"],
                "SEXUALLY_EXPLICIT": toxicity_score["SEXUALLY_EXPLICIT"],
                "FLIRTATION": toxicity_score["FLIRTATION"],
            }
        except Exception as exc:
            logger.warning("Perspective API toxicity scoring failed: %s", exc)
            return {}

    return detoxify_toxicity(text)

