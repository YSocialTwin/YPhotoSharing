import logging
from YPhotoSharing.YServer.classes.models import Photo

logger = logging.getLogger(__name__)

class ViralityService:
    """
    Computes and updates virality scores for photos across the platform.
    Run periodically (e.g., each round) to identify cascading content.
    """

    def __init__(self, db_middleware):
        self.db = db_middleware

    def compute_virality_scores(self):
        """
        Calculates viral_score for photos and updates them in the database.
        """
        logger.debug("Computing virality scores for photos...")
        with self.db.session_scope() as session:
            # For a real implementation, we might only update recent photos
            # or calculate actual velocity (delta over time).
            # For this simulation, we use a simple engagement aggregation
            # weighted towards shares.
            photos = session.query(Photo).all()
            updated = 0
            for photo in photos:
                # Basic virality heuristic
                score = float(photo.num_likes + photo.num_comments + (photo.num_shares * 2.0))
                if photo.viral_score != score:
                    photo.viral_score = score
                    updated += 1
            
            if updated > 0:
                logger.info(f"Updated viral_score for {updated} photos.")
