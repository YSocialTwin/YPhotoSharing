from typing import List, Dict
import math
from datetime import datetime

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

    def compute_edge_weight(self, user_id: str, author_id: str) -> float:
        """
        Calculate an affinity score based on how many times user_id interacted
        (liked/commented/saved) with author_id's past content.
        This represents P(engagement).
        """
        from YPhotoSharing.YServer.classes.models import Reaction, Comment, Photo
        
        # Fast heuristic: how many reactions + comments this user made on this author's photos
        reactions_count = self.db.query(Reaction).join(Photo).filter(
            Reaction.user_id == user_id,
            Photo.user_id == author_id
        ).count()
        
        comments_count = self.db.query(Comment).join(Photo).filter(
            Comment.user_id == user_id,
            Photo.user_id == author_id
        ).count()
        
        # Edge weight is log-scaled so hyper-active pairs don't dominate infinitely
        total_interactions = reactions_count + (comments_count * 2) # comments weighted 2x
        return math.log1p(total_interactions)

    def rank_feed(self, user_id: str, candidates: List[Dict]) -> List[Dict]:
        """
        Takes a list of candidate photos (dicts from DB) and ranks them.
        """
        ranked_candidates = []
        now = datetime.utcnow()
        
        # Cache edge weights to avoid N DB queries for the same author
        edge_weights = {}

        for photo in candidates:
            author_id = photo["user_id"]
            if author_id not in edge_weights:
                edge_weights[author_id] = self.compute_edge_weight(user_id, author_id)
            
            ew = edge_weights[author_id]
            
            # Content quality base score
            viral_score = photo.get("viral_score", 1.0)
            
            # Decay (hours since posted)
            created_at = photo.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)
            
            hours_old = 0
            if created_at:
                delta = now - created_at
                hours_old = max(0, delta.total_seconds() / 3600.0)
            
            # The ML surrogate function: 
            # Score = (w1 * EdgeWeight) + (w2 * ViralScore) / (1 + decay_rate * hours_old)
            # This perfectly emulates a multi-objective ranking output without the compute cost.
            
            decay_factor = 1.0 / (1.0 + 0.1 * hours_old)
            final_score = (2.0 * ew + 1.0 * math.log1p(viral_score)) * decay_factor
            
            ranked_candidates.append((final_score, photo))
            
        # Sort by score descending
        ranked_candidates.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in ranked_candidates]
