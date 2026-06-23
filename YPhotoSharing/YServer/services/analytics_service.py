import logging
import uuid
from sqlalchemy import func
from YPhotoSharing.YServer.classes.models import AnalyticsSnapshot, Photo, Reaction, Comment, Follow, User_mgmt

logger = logging.getLogger(__name__)

class AnalyticsService:
    """
    Analytics & Observability system for YPhotoSharing.
    Computes system-wide telemetry at the end of each simulated round.
    """

    def __init__(self, db_middleware):
        self.db = db_middleware

    def compute_round_statistics(self, round_id: str):
        """
        Calculates and stores aggregated metrics for the current round.
        """
        logger.info(f"Computing analytics snapshot for round {round_id}...")
        
        with self.db.session_scope() as session:
            # We want metrics for the whole platform up to this point, or just this round?
            # Usually we snapshot the total states, or the deltas.
            # Let's snapshot the total states so time-series charts look like cumulative growth.
            
            # Active users (for simulation, everyone not shadow-banned/deleted is "active", but let's just count total)
            active_users = session.query(User_mgmt).filter_by(is_shadow_banned=0).count()
            
            # Total photos
            total_photos = session.query(Photo).filter_by(is_removed=0).count()
            
            # Total reactions
            total_reactions = session.query(Reaction).count()
            
            # Total comments
            total_comments = session.query(Comment).filter_by(is_removed=0).count()
            
            # Total follows (active)
            total_follows = session.query(Follow).filter_by(action="follow").count()
            
            snapshot_id = str(uuid.uuid4())
            snapshot = AnalyticsSnapshot(
                id=snapshot_id,
                round_id=round_id,
                active_users=active_users,
                total_photos=total_photos,
                total_reactions=total_reactions,
                total_comments=total_comments,
                total_follows=total_follows
            )
            
            session.add(snapshot)
            logger.debug(f"Analytics saved: {active_users} users, {total_photos} photos, {total_follows} edges.")
