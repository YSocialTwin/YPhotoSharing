import json
import numpy as np
from typing import List
from sqlalchemy.orm import Session

from YPhotoSharing.YServer.recsys.base_recsys import BaseRecsys
from YPhotoSharing.YServer.classes.models import Photo, PhotoTopic, Round, UserInterest, Reaction

class ContentBasedRecsys(BaseRecsys):
    """
    Content-based recommendation utilizing dense visual embeddings (CLIP)
    and aesthetic scoring, falling back to declared interests.
    """

    def evaluate(self, user_id: str, round_id: str, db: Session, limit: int = 10) -> List[str]:
        # 1. Fetch user's historically liked photos
        liked_reactions = db.query(Reaction.photo_id).filter(
            Reaction.user_id == user_id,
            Reaction.reaction_type.in_(["LIKE", "LOVE"])
        ).limit(50).all()
        liked_photo_ids = [r[0] for r in liked_reactions]

        user_profile_vec = None
        if liked_photo_ids:
            # Fetch embeddings for these photos
            liked_photos = db.query(Photo.embedding).filter(
                Photo.id.in_(liked_photo_ids),
                Photo.embedding.isnot(None)
            ).all()
            
            embeddings = []
            for p in liked_photos:
                try:
                    vec = np.array(json.loads(p[0]))
                    embeddings.append(vec)
                except Exception:
                    continue
                    
            if embeddings:
                # Average them to get the user's "taste vector"
                user_profile_vec = np.mean(embeddings, axis=0)
                user_profile_vec = user_profile_vec / np.linalg.norm(user_profile_vec)

        # 2. Candidate generation
        # We fetch recent photos not created by the user
        candidates = (
            db.query(Photo)
            .join(Round, Round.id == Photo.round)
            .filter(Photo.user_id != user_id)
            .order_by(Round.day.desc(), Round.hour.desc(), Photo.created_at.desc())
            .limit(200)
            .all()
        )

        if not candidates:
            return []

        # 3. Scoring
        scores = []
        for photo in candidates:
            score = 0.0
            
            # Base aesthetic score (normalized to 0-1)
            aesthetic = photo.aesthetic_score if photo.aesthetic_score else 0.5
            
            # Visual similarity score
            sim = 0.0
            if user_profile_vec is not None and photo.embedding:
                try:
                    photo_vec = np.array(json.loads(photo.embedding))
                    sim = float(np.dot(user_profile_vec, photo_vec))
                except Exception:
                    pass
            
            # Combine scores
            score = (sim * 0.7) + (aesthetic * 0.3)
            scores.append((photo.id, score))

        # Sort by score descending
        sorted_pids = sorted(scores, key=lambda x: x[1], reverse=True)
        return [pid for pid, score in sorted_pids[:limit]]
