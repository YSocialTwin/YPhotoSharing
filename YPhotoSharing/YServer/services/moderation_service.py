import logging
import uuid
from typing import List, Dict, Optional
from YPhotoSharing.YServer.classes.models import ModerationEvent, Reported, Photo, Comment, User_mgmt

logger = logging.getLogger(__name__)

class ModerationService:
    """
    Moderation & Safety system for YPhotoSharing.
    Evaluates reported content and runs periodic toxicity checks.
    """

    def __init__(self, db_middleware):
        self.db = db_middleware
        self.banned_keywords = {"hate", "kill", "die", "stupid", "idiot", "spam"}

    def _toxicity_check_stub(self, text: str) -> float:
        """
        Stub for an LLM-based toxicity classification model.
        Returns a score from 0.0 to 1.0.
        """
        if not text:
            return 0.0
        text_lower = text.lower()
        score = 0.0
        for word in self.banned_keywords:
            if word in text_lower:
                score += 0.3
        return min(score, 1.0)

    def process_round_moderation(self, round_id: str):
        """
        Runs the moderation loop for the current round:
        1. Process pending reports.
        2. Proactively scan recent photos/comments (stub).
        """
        logger.info(f"Running moderation for round {round_id}...")
        
        with self.db.session_scope() as session:
            # 1. Process pending reports
            pending_reports = session.query(Reported).filter_by(round_id=round_id).all()
            for report in pending_reports:
                self._evaluate_content(session, report.content_id, report.content_type, round_id, reported_reason=report.reason)

            # 2. Proactively scan recent photos
            recent_photos = session.query(Photo).filter_by(round=round_id, is_removed=0).all()
            for photo in recent_photos:
                tox_score = self._toxicity_check_stub(photo.caption)
                if tox_score > 0.5:
                    self._take_action(session, photo.id, "photo", "remove", f"High toxicity: {tox_score}", tox_score, round_id)
                    # Warn or shadow-ban user
                    if tox_score >= 0.8:
                        self._penalize_user(session, photo.user_id, "shadow-ban")
                    else:
                        self._penalize_user(session, photo.user_id, "warn")

            # 3. Proactively scan recent comments
            recent_comments = session.query(Comment).filter_by(round=round_id, is_removed=0).all()
            for comment in recent_comments:
                tox_score = self._toxicity_check_stub(comment.text)
                if tox_score > 0.5:
                    self._take_action(session, comment.id, "comment", "remove", f"High toxicity: {tox_score}", tox_score, round_id)
                    self._penalize_user(session, comment.user_id, "warn")

    def _evaluate_content(self, session, content_id: str, content_type: str, round_id: str, reported_reason: str = ""):
        """Evaluate reported content."""
        if content_type == "photo":
            item = session.query(Photo).filter_by(id=content_id).first()
            if not item or item.is_removed: return
            text_to_check = item.caption
            user_id = item.user_id
        elif content_type == "comment":
            item = session.query(Comment).filter_by(id=content_id).first()
            if not item or item.is_removed: return
            text_to_check = item.text
            user_id = item.user_id
        else:
            return

        tox_score = self._toxicity_check_stub(text_to_check)
        
        # If it's reported, we might have a lower threshold
        if tox_score > 0.3 or "spam" in reported_reason.lower():
            self._take_action(session, content_id, content_type, "remove", f"Reported: {reported_reason} (Tox: {tox_score})", tox_score, round_id)
            self._penalize_user(session, user_id, "warn")

    def _take_action(self, session, content_id: str, content_type: str, action: str, reason: str, confidence: float, round_id: str):
        """Records a moderation event and applies the content action."""
        event_id = str(uuid.uuid4())
        mod_event = ModerationEvent(
            id=event_id,
            content_id=content_id,
            content_type=content_type,
            action_taken=action,
            reason=reason,
            confidence=confidence,
            round_id=round_id
        )
        session.add(mod_event)
        
        if action == "remove":
            if content_type == "photo":
                session.query(Photo).filter_by(id=content_id).update({"is_removed": 1})
            elif content_type == "comment":
                session.query(Comment).filter_by(id=content_id).update({"is_removed": 1})

        logger.info(f"Moderation applied {action} to {content_type} {content_id}. Reason: {reason}")

    def _penalize_user(self, session, user_id: str, penalty: str):
        """Applies a penalty to a user (warn -> increase stress, shadow-ban)."""
        user = session.query(User_mgmt).filter_by(id=user_id).first()
        if not user:
            return
            
        if penalty == "warn":
            user.stress_level += 0.2
        elif penalty == "shadow-ban":
            user.is_shadow_banned = 1
            user.stress_level += 0.5
            
        # Cap stress
        user.stress_level = min(user.stress_level, 1.0)
