"""
Follower Recommendation System.
Recommends users to follow based on mutual followers, shared interests, and influence score.
"""

import logging
from YPhotoSharing.YServer.classes.models import User_mgmt, Follow

logger = logging.getLogger(__name__)

class FollowRecsys:
    def __init__(self, db_middleware):
        self.db = db_middleware

    def get_recommendations(self, user_id: str, limit: int = 5) -> list:
        """
        Returns a list of user_ids recommended for `user_id` to follow.
        Simple heuristic:
        1. Not already following.
        2. High influence score.
        """
        with self.db.session_scope() as session:
            # Get users already followed
            following = session.query(Follow.user_id).filter(Follow.follower_id == user_id).all()
            following_ids = {f[0] for f in following}
            following_ids.add(user_id) # Don't recommend self
            
            # Find users not followed, ordered by influence_score descending
            candidates = session.query(User_mgmt.id, User_mgmt.influence_score)\
                .filter(~User_mgmt.id.in_(following_ids))\
                .order_by(User_mgmt.influence_score.desc())\
                .limit(limit * 2).all()
                
            return [c[0] for c in candidates[:limit]]
