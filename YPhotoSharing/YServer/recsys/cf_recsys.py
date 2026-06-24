from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func

from YPhotoSharing.YServer.recsys.base_recsys import BaseRecsys
from YPhotoSharing.YServer.classes.models import Photo, Reaction, Comment, Follow

class CollaborativeFilteringRecsys(BaseRecsys):
    """
    Collaborative filtering based on the follow graph.
    Suggests posts liked/commented by the accounts the user follows.
    """

    def evaluate(self, user_id: str, round_id: str, db: Session, limit: int = 10) -> List[str]:
        # Get users that the current user follows
        following = db.query(Follow.user_id).filter(Follow.follower_id == user_id).all()
        following_ids = [f[0] for f in following]

        if not following_ids:
            return []

        # Get photos that these followed users have reacted to
        reactions = db.query(Reaction.photo_id).filter(Reaction.user_id.in_(following_ids)).all()
        # Get photos that these followed users have commented on
        comments = db.query(Comment.photo_id).filter(Comment.user_id.in_(following_ids)).all()
        
        photo_ids = [r[0] for r in reactions] + [c[0] for c in comments]
        
        # Count frequency of photo_ids
        freq = {}
        for pid in photo_ids:
            freq[pid] = freq.get(pid, 0) + 1
            
        # Sort by frequency descending
        sorted_pids = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [pid for pid, count in sorted_pids[:limit]]
