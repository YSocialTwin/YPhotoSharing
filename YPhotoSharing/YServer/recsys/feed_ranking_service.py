from typing import Dict, List, Optional, Set
import math

class FeedRankingService:
    """
    Simulates a predictive ML ranking system for the Home Feed.
    Instead of chronological sorting, it scores posts based on:
    - P(Like) / P(Comment) modeled via Edge Weight (historical interactions with author)
    - Content Quality (viral_score)
    - Freshness (time decay)
    """

    def __init__(self, db_session):
        self.db = db_session

    def _get_user_interest_terms(self, user_id: str) -> Set[str]:
        from YPhotoSharing.YServer.classes.models import Interest, UserInterest

        rows = (
            self.db.query(Interest.interest)
            .join(UserInterest)
            .filter(UserInterest.user_id == user_id)
            .all()
        )
        return {row[0].lower() for row in rows if row and row[0]}

    def _get_photo_topic_terms(self, photo_id: str) -> Set[str]:
        from YPhotoSharing.YServer.classes.models import Interest, PhotoTopic

        rows = (
            self.db.query(Interest.interest)
            .join(PhotoTopic, PhotoTopic.topic_id == Interest.iid)
            .filter(PhotoTopic.photo_id == photo_id)
            .all()
        )
        return {row[0].lower() for row in rows if row and row[0]}

    def _get_photo_emotion_terms(self, photo_id: str) -> Set[str]:
        from YPhotoSharing.YServer.classes.models import Emotion, PhotoEmotion

        rows = (
            self.db.query(Emotion.emotion)
            .join(PhotoEmotion, PhotoEmotion.emotion_id == Emotion.id)
            .filter(PhotoEmotion.photo_id == photo_id)
            .all()
        )
        return {row[0].lower() for row in rows if row and row[0]}

    def compute_edge_weight(self, user_id: str, author_id: str) -> float:
        """
        Calculate an affinity score based on how many times user_id interacted
        (liked/commented/saved) with author_id's past content.
        This represents P(engagement).
        """
        from YPhotoSharing.YServer.classes.models import Reaction, Comment, Photo, SavedPhoto
        
        # Fast heuristic: how many reactions + comments this user made on this author's photos
        reactions_count = self.db.query(Reaction).join(Photo).filter(
            Reaction.user_id == user_id,
            Photo.user_id == author_id
        ).count()
        
        comments_count = self.db.query(Comment).join(Photo).filter(
            Comment.user_id == user_id,
            Photo.user_id == author_id
        ).count()

        saved_count = self.db.query(SavedPhoto).join(Photo).filter(
            SavedPhoto.user_id == user_id,
            Photo.user_id == author_id,
        ).count()
        
        # Edge weight is log-scaled so hyper-active pairs don't dominate infinitely
        total_interactions = reactions_count + (comments_count * 2) + (saved_count * 2)
        return math.log1p(total_interactions)

    def _round_index(self, round_row) -> int:
        if round_row is None:
            return 0
        try:
            return int(round_row.day or 0) * 24 + int(round_row.hour or 0)
        except Exception:
            return 0

    def rank_feed(self, user_id: str, candidates: List[Dict]) -> List[Dict]:
        """
        Takes a list of candidate photos (dicts from DB) and ranks them.
        """
        ranked_candidates = []
        from YPhotoSharing.YServer.classes.models import Round

        current_round = (
            self.db.query(Round)
            .order_by(Round.day.desc(), Round.hour.desc(), Round.id.desc())
            .first()
        )
        current_round_index = self._round_index(current_round)
        user_interests = self._get_user_interest_terms(user_id)

        # Cache edge weights to avoid N DB queries for the same author
        edge_weights = {}
        photo_topics_cache: Dict[str, Set[str]] = {}
        photo_emotions_cache: Dict[str, Set[str]] = {}
        round_cache: Dict[str, int] = {}

        for photo in candidates:
            author_id = photo["user_id"]
            if author_id not in edge_weights:
                edge_weights[author_id] = self.compute_edge_weight(user_id, author_id)
            
            ew = edge_weights[author_id]
            
            # Content quality base score
            viral_score = photo.get("viral_score", 1.0)
            
            # Decay by simulation age, not wall-clock age.
            round_id = str(photo.get("round") or "").strip()
            hours_old = 0
            if round_id:
                if round_id not in round_cache:
                    round_row = self.db.query(Round).filter(Round.id == round_id).first()
                    round_cache[round_id] = self._round_index(round_row)
                hours_old = max(0, current_round_index - round_cache[round_id])

            photo_id = photo.get("id")
            topic_overlap = 0.0
            emotion_bonus = 0.0
            if photo_id:
                if photo_id not in photo_topics_cache:
                    photo_topics_cache[photo_id] = self._get_photo_topic_terms(photo_id)
                if photo_id not in photo_emotions_cache:
                    photo_emotions_cache[photo_id] = self._get_photo_emotion_terms(photo_id)
                if user_interests and photo_topics_cache[photo_id]:
                    overlap = user_interests.intersection(photo_topics_cache[photo_id])
                    if overlap:
                        topic_overlap = len(overlap) / float(max(1, len(photo_topics_cache[photo_id])))
                if photo_emotions_cache[photo_id].intersection({"joy", "awe", "calm", "nostalgia", "excitement"}):
                    emotion_bonus = 0.15

            # The ML surrogate function: 
            # Score = (w1 * EdgeWeight) + (w2 * ViralScore) / (1 + decay_rate * hours_old)
            # This perfectly emulates a multi-objective ranking output without the compute cost.

            decay_factor = 1.0 / (1.0 + 0.1 * hours_old)
            engagement_signal = (2.0 * ew + 1.0 * math.log1p(viral_score))
            popularity_signal = math.log1p(
                (photo.get("num_likes") or 0)
                + (photo.get("num_comments") or 0) * 2
                + (photo.get("num_shares") or 0) * 1.5
            )
            quality_signal = float(photo.get("aesthetic_score") or 0.5)
            sentiment_signal = 0.0
            sentiment_score = photo.get("sentiment_score")
            if sentiment_score is not None:
                try:
                    sentiment_signal = max(-0.2, min(0.2, float(sentiment_score) * 0.1))
                except Exception:
                    sentiment_signal = 0.0

            final_score = (
                (1.6 * engagement_signal)
                + (1.2 * popularity_signal)
                + (0.8 * topic_overlap)
                + (0.4 * quality_signal)
                + emotion_bonus
                + sentiment_signal
            ) * decay_factor

            ranked_candidates.append((final_score, photo))
            
        # Sort by score descending
        ranked_candidates.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in ranked_candidates]
