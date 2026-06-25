from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .classes.db_middleware import DatabaseMiddleware
from YPhotoSharing.YClient.text_support.text_annotator import prepare_sentiment_data, prepare_toxicity_data


@dataclass
class AnnotationProcessor:
    """Process and persist annotations using YSimulator-compatible semantics."""

    metadata_service: DatabaseMiddleware
    enable_sentiment: bool = False
    enable_emotion_annotation: bool = False
    enable_toxicity: bool = False
    perspective_api_key: Optional[str] = None

    def _process_annotations(
        self,
        post_id: str,
        user_id: str,
        annotations: Dict[str, Any],
        is_post: bool = False,
        is_comment: bool = False,
        parent_post_id: Optional[str] = None,
        parent_sentiment: Optional[float] = None,
    ) -> None:
        hashtags = annotations.get("hashtags", [])
        for hashtag_text in hashtags:
            hashtag_id = self.metadata_service.add_or_get_hashtag(hashtag_text)
            self.metadata_service.add_post_hashtag(post_id, hashtag_id)

        sentiment_scores = annotations.get("sentiment")
        if self.enable_sentiment and sentiment_scores:
            topic_ids = annotations.get("topic_ids") or annotations.get("topics") or ["default-topic"]
            sentiment_entries = prepare_sentiment_data(
                post_id=post_id,
                user_id=user_id,
                topic_ids=topic_ids,
                round_id=str(annotations.get("round", "0")),
                sentiment_scores=sentiment_scores,
                sentiment_parent=parent_sentiment,
                is_post=is_post,
                is_comment=is_comment,
                is_reaction=False,
            )
            for sentiment_data in sentiment_entries:
                self.metadata_service.add_post_sentiment(sentiment_data)

        toxicity_scores = annotations.get("toxicity")
        if self.enable_toxicity and toxicity_scores:
            toxicity_data = prepare_toxicity_data(post_id, toxicity_scores)
            self.metadata_service.add_post_toxicity(toxicity_data)

        emotions = annotations.get("emotions")
        if self.enable_emotion_annotation and emotions:
            for emotion_name in emotions:
                emotion = self.metadata_service.get_emotion_by_name(emotion_name)
                if emotion:
                    self.metadata_service.add_post_emotion(post_id, emotion["id"])
