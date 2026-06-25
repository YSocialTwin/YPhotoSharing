from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


GOEMOTIONS = [
    "admiration",
    "amusement",
    "anger",
    "annoyance",
    "approval",
    "caring",
    "confusion",
    "curiosity",
    "desire",
    "disappointment",
    "disapproval",
    "disgust",
    "embarrassment",
    "excitement",
    "fear",
    "gratitude",
    "grief",
    "joy",
    "love",
    "nervousness",
    "optimism",
    "pride",
    "realization",
    "relief",
    "remorse",
    "sadness",
    "surprise",
    "trust",
]


@dataclass
class DatabaseMiddleware:
    """In-memory middleware that mirrors YSimulator's annotation persistence APIs."""

    config: Dict[str, Any] = field(default_factory=dict)
    emotions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    posts_sentiment: List[Dict[str, Any]] = field(default_factory=list)
    posts_toxicity: List[Dict[str, Any]] = field(default_factory=list)
    posts_emotions: List[Dict[str, Any]] = field(default_factory=list)
    hashtags: Dict[str, str] = field(default_factory=dict)
    post_hashtags: List[Dict[str, Any]] = field(default_factory=list)

    def initialize_emotions_table(self) -> None:
        for emotion_name in GOEMOTIONS:
            self.emotions.setdefault(
                emotion_name,
                {"id": str(uuid.uuid4()), "emotion": emotion_name},
            )

    def get_emotion_by_name(self, emotion_name: str) -> Optional[Dict[str, Any]]:
        self.initialize_emotions_table()
        return self.emotions.get(emotion_name)

    def add_post_emotion(self, post_id: str, emotion_id: str) -> bool:
        self.posts_emotions.append({"post_id": post_id, "emotion_id": emotion_id})
        return True

    def add_post_sentiment(self, sentiment_data: Dict[str, Any]) -> bool:
        self.posts_sentiment.append(dict(sentiment_data))
        return True

    def add_post_toxicity(self, toxicity_data: Dict[str, Any]) -> bool:
        toxicity_id = str(uuid.uuid4())
        payload = {"id": toxicity_id, **dict(toxicity_data)}
        self.posts_toxicity.append(payload)
        return True

    def add_or_get_hashtag(self, hashtag_text: str) -> str:
        if hashtag_text not in self.hashtags:
            self.hashtags[hashtag_text] = str(uuid.uuid4())
        return self.hashtags[hashtag_text]

    def add_post_hashtag(self, post_id: str, hashtag_id: str) -> bool:
        self.post_hashtags.append({"post_id": post_id, "hashtag_id": hashtag_id})
        return True
