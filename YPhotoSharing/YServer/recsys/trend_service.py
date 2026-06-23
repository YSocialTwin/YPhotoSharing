from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

class TrendService:
    """
    Computes hashtag velocity and acceleration to surface trending topics.
    In a real system, this runs constantly. In simulation, we compute lazily.
    """
    def __init__(self, db: Session):
        self.db = db

    def get_trending_multiplier(self, hashtags: List[str]) -> float:
        """
        Given a list of hashtags, return a score multiplier representing 
        current trend momentum.
        """
        if not hashtags:
            return 1.0

        from YPhotoSharing.YServer.classes.models import Photo
        
        # We approximate momentum by querying recent vs older usage
        now = datetime.utcnow()
        recent_window = now - timedelta(hours=24)
        older_window = now - timedelta(hours=48)
        
        total_momentum = 0.0
        
        # We use a naive "LIKE" search for hashtags for simplicity
        for ht in hashtags:
            # recent frequency
            recent_count = self.db.query(Photo).filter(
                Photo.caption.like(f"%{ht}%"),
                Photo.created_at >= recent_window
            ).count()
            
            # older frequency
            older_count = self.db.query(Photo).filter(
                Photo.caption.like(f"%{ht}%"),
                Photo.created_at >= older_window,
                Photo.created_at < recent_window
            ).count()
            
            if older_count == 0:
                if recent_count > 0:
                    velocity = 2.0  # High initial acceleration for brand new trend
                else:
                    velocity = 0.0
            else:
                velocity = (recent_count - older_count) / float(older_count)
            
            # Boost trending, penalize decaying
            # Max boost of 2.0, min penalty of 0.5
            momentum = max(0.5, min(2.0, 1.0 + velocity))
            total_momentum += momentum
            
        # Average momentum across all hashtags on the post
        return total_momentum / len(hashtags)
