"""
Server-side job that queries photos missing visual enrichment and processes them via VisionService.
"""

import logging
import ray
from YPhotoSharing.YServer.classes.models import Photo, PhotoEmotion

logger = logging.getLogger(__name__)

class PhotoEnrichmentService:
    def __init__(self, db_middleware, namespace: str = "yphotosharing"):
        self.db = db_middleware
        self.namespace = namespace
        self.vision_actor = None

    def _get_vision_actor(self):
        if self.vision_actor is None:
            try:
                self.vision_actor = ray.get_actor("VisionService", namespace=self.namespace)
            except ValueError:
                logger.warning("VisionService actor not found. Skipping photo enrichment.")
                self.vision_actor = None
        return self.vision_actor

    def enrich_photos(self):
        """
        Query unenriched photos, fetch metadata from VisionService, and persist to DB.
        Called per round.
        """
        vision_actor = self._get_vision_actor()
        if not vision_actor:
            return

        with self.db.session_scope() as session:
            # Get unenriched photos
            unenriched = session.query(Photo).filter(
                (Photo.embedding == None) | (Photo.alt_text == None)
            ).limit(100).all()

            if not unenriched:
                logger.debug("No unenriched photos found.")
                return

            # Prepare batch for VisionService
            batch = [{"id": p.id, "image_url": p.image_url, "caption": p.caption} for p in unenriched]
            
            logger.info(f"Dispatching {len(batch)} photos to VisionService for enrichment.")
            
            # This runs synchronously in the server actor, so we can use ray.get
            try:
                results = ray.get(vision_actor.process_photos_batch.remote(batch))
            except Exception as e:
                logger.error(f"Failed to get results from VisionService: {e}")
                return

            # Update DB with results
            for res in results:
                photo_id = res["photo_id"]
                photo_obj = session.query(Photo).filter_by(id=photo_id).first()
                if photo_obj:
                    photo_obj.alt_text = res.get("alt_text")
                    photo_obj.aesthetic_score = res.get("aesthetic_score")
                    photo_obj.embedding = res.get("embedding")
                    
                    # Store emotions
                    for emotion_str in res.get("emotions", []):
                        # Find or create Emotion
                        from YPhotoSharing.YServer.classes.models import Emotion
                        import uuid
                        emotion_obj = session.query(Emotion).filter_by(emotion=emotion_str).first()
                        if not emotion_obj:
                            emotion_obj = Emotion(id=str(uuid.uuid4()), emotion=emotion_str)
                            session.add(emotion_obj)
                            session.flush()
                        
                        # Avoid duplicates
                        existing = session.query(PhotoEmotion).filter_by(photo_id=photo_id, emotion_id=emotion_obj.id).first()
                        if not existing:
                            pe = PhotoEmotion(id=str(uuid.uuid4()), photo_id=photo_id, emotion_id=emotion_obj.id)
                            session.add(pe)
                            
            logger.info(f"Successfully enriched {len(results)} photos.")
