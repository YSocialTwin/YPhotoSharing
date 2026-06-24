from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from YPhotoSharing.YServer.recsys.base_recsys import BaseRecsys
from YPhotoSharing.YServer.classes.models import Photo, Reaction, Comment

class PopularityRecsys(BaseRecsys):
    """
    Recommendation based on popularity.
    Score = likes + (comments * 2).
    """

    def evaluate(self, user_id: str, round_id: str, db: Session, limit: int = 10) -> List[str]:
        # Query photos with their reaction and comment counts
        photos = db.query(Photo).all()
        
        scores = []
        for p in photos:
            likes = db.query(func.count(Reaction.id)).filter(Reaction.photo_id == p.id).scalar() or 0
            comments = db.query(func.count(Comment.id)).filter(Comment.photo_id == p.id).scalar() or 0
            
            score = likes + (comments * 2)
            scores.append((p.id, score))
            
        scores.sort(key=lambda x: x[1], reverse=True)
        return [pid for pid, score in scores[:limit]]
