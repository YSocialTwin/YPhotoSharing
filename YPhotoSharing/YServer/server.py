"""
Ray Orchestrator Server actor for YPhotoSharing.

Responsibilities
----------------
- Maintain exclusive access to the database (via DatabaseMiddleware).
- Register simulation clients and coordinate simulation rounds.
- Expose a rich remote API that clients call via ray.get_actor().
- Serve home feeds, explore feeds, recommendations and user/photo lookups.
- Persist all social interactions (photos, reactions, comments, follows, DMs).

Only this module (and DatabaseMiddleware) touches the database directly.
"""

import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import ray

from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware
from YPhotoSharing.YServer.services.recommendation_service import RecommendationService
from YPhotoSharing.YServer.services.photo_enrichment_service import PhotoEnrichmentService
from YPhotoSharing.YServer.services.virality_service import ViralityService
from YPhotoSharing.YServer.services.influence_service import InfluenceService
from YPhotoSharing.YServer.services.moderation_service import ModerationService
from YPhotoSharing.YServer.services.analytics_service import AnalyticsService
from YPhotoSharing.YServer.services.media_service import MediaService
from YPhotoSharing.YServer.recsys.follow_recsys import FollowRecsys

logger = logging.getLogger(__name__)


@ray.remote
class OrchestratorServer:
    """
    Ray remote actor – the sole DB-facing component.

    Clients connect by calling::

        server = ray.get_actor("Orchestrator", namespace=namespace)

    All public methods return JSON-serialisable plain Python values.
    """

    def __init__(
        self,
        db_config: dict,
        config_path: str = ".",
        min_to_start: int = 1,
        server_name: str = "orchestrator_server",
        timeout_seconds: int = 60,
        simulation_config: Optional[dict] = None,
    ):
        self.server_name = server_name
        self.min_to_start = min_to_start
        self.timeout_seconds = timeout_seconds
        self.simulation_config = simulation_config or {}
        self._registered_clients: Dict[str, dict] = {}
        self._round_ready: Dict[str, bool] = {}
        self._current_day = 0
        self._current_hour = 0
        self._run_id = str(uuid.uuid4())
        self._start_time = time.time()

        # Database – server-exclusive
        self._db = DatabaseMiddleware(db_config, config_path)
        namespace = ray.get_runtime_context().namespace
        # Services
        self.recommendation_service = RecommendationService()
        self.photo_enrichment_service = PhotoEnrichmentService(self._db, namespace)
        self.virality_service = ViralityService(self._db)
        self.influence_service = InfluenceService(self._db)
        self.follow_recsys = FollowRecsys(self._db)
        self.moderation_service = ModerationService(self._db)
        self.analytics_service = AnalyticsService(self._db)
        self.media_service = MediaService()
        logger.info(f"OrchestratorServer '{server_name}' ready (run_id={self._run_id})")

    # ------------------------------------------------------------------
    # Client registration / coordination
    # ------------------------------------------------------------------

    def register_client(self, client_id: str, client_info: dict) -> dict:
        """Register a simulation client and return server metadata."""
        self._registered_clients[client_id] = {
            **client_info,
            "registered_at": time.time(),
            "last_heartbeat": time.time(),
        }
        logger.info(f"Client registered: {client_id}")
        return {
            "run_id": self._run_id,
            "server_name": self.server_name,
            "simulation_config": self.simulation_config,
            "current_day": self._current_day,
            "current_hour": self._current_hour,
        }

    def heartbeat(self, client_id: str) -> dict:
        """Update client last-seen timestamp and return current round info."""
        if client_id in self._registered_clients:
            self._registered_clients[client_id]["last_heartbeat"] = time.time()
        return {
            "current_day": self._current_day,
            "current_hour": self._current_hour,
            "run_id": self._run_id,
        }

    def ready_for_next_round(self, client_id: str) -> bool:
        """Signal that a client has finished processing the current round."""
        self._round_ready[client_id] = True
        all_ready = all(
            self._round_ready.get(cid, False) for cid in self._registered_clients
        )
        if all_ready and len(self._registered_clients) >= self.min_to_start:
            self._advance_round()
            self._round_ready = {}
        return all_ready

    def _advance_round(self):
        self._current_hour += 1
        if self._current_hour >= 24:
            self._current_hour = 0
            self._current_day += 1
        round_id = self._db.get_or_create_round(self._current_day, self._current_hour)
        
        # Phase 3: Enrich photos missing alt_text and embeddings
        self.photo_enrichment_service.enrich_photos()
        
        # Phase 2: Compute recommendations and trending hashtags at end of round
        with self._db.session_scope() as session:
            self.recommendation_service.compute_recommendations_for_round(round_id, session)
            self.recommendation_service.compute_trending_hashtags(round_id, session)
            
        try:
            self.virality_service.compute_virality_scores()
            self.influence_service.compute_influence_metrics()
            self.moderation_service.process_round_moderation(round_id)
            self.analytics_service.compute_round_statistics(round_id)
        except Exception as e:
            logger.error(f"Error computing background metrics: {e}")
            
        logger.info(f"Round advanced → day={self._current_day} hour={self._current_hour}")

    def get_simulation_status(self) -> dict:
        return {
            "run_id": self._run_id,
            "server_name": self.server_name,
            "current_day": self._current_day,
            "current_hour": self._current_hour,
            "registered_clients": len(self._registered_clients),
            "uptime_seconds": time.time() - self._start_time,
        }

    # ------------------------------------------------------------------
    # Round helpers
    # ------------------------------------------------------------------

    def get_or_create_round(self, day: int, hour: int) -> str:
        return self._db.get_or_create_round(day, hour)

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def create_user(self, user_data: dict) -> str:
        return self._db.create_user(user_data)

    def update_satisfaction(self, user_id: str, delta: float) -> float:
        return self._db.update_satisfaction(user_id, delta)

    def set_churn_state(self, user_id: str, is_churned: bool) -> bool:
        return self._db.set_churn_state(user_id, is_churned)

    def get_user(self, user_id: str) -> Optional[dict]:
        return self._db.get_user(user_id)

    def get_user_by_username(self, username: str) -> Optional[dict]:
        return self._db.get_user_by_username(username)

    def list_users(self, limit: int = 100, offset: int = 0) -> List[dict]:
        return self._db.list_users(limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Follow / social graph
    # ------------------------------------------------------------------

    def follow_user(self, follower_id: str, user_id: str, round_id: str) -> str:
        return self._db.add_follow(user_id=user_id, follower_id=follower_id, round_id=round_id)

    def unfollow_user(self, follower_id: str, user_id: str, round_id: str) -> bool:
        return self._db.remove_follow(user_id=user_id, follower_id=follower_id, round_id=round_id)

    def get_followers(self, user_id: str) -> List[str]:
        return self._db.get_followers(user_id)

    def get_following(self, user_id: str) -> List[str]:
        return self._db.get_following(user_id)

    # ------------------------------------------------------------------
    # Photos
    # ------------------------------------------------------------------

    def post_photo(self, photo_data: dict) -> str:
        return self._db.create_photo(photo_data)

    def add_photo_emotion(self, photo_id: str, emotion: str) -> bool:
        return self._db.add_photo_emotion(photo_id, emotion)

    def get_photo(self, photo_id: str) -> Optional[dict]:
        return self._db.get_photo(photo_id)

    def get_user_photos(self, user_id: str, limit: int = 20, offset: int = 0) -> List[dict]:
        return self._db.get_user_photos(user_id, limit=limit, offset=offset)

    def delete_photo(self, photo_id: str) -> bool:
        return self._db.delete_photo(photo_id)

    # ------------------------------------------------------------------
    # Reactions
    # ------------------------------------------------------------------

    def react_to_photo(self, user_id: str, photo_id: str,
                       reaction_type: str, round_id: str) -> str:
        return self._db.add_reaction(user_id, photo_id, reaction_type, round_id)

    def remove_reaction(self, user_id: str, photo_id: str) -> bool:
        return self._db.remove_reaction(user_id, photo_id)

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def post_comment(self, user_id: str, photo_id: str, body: str,
                     round_id: str, parent_comment_id: str = None) -> str:
        return self._db.add_comment(user_id, photo_id, body, round_id, parent_comment_id)

    def get_comments(self, photo_id: str, limit: int = 50) -> List[dict]:
        return self._db.get_comments(photo_id, limit=limit)

    # ------------------------------------------------------------------
    # Stories
    # ------------------------------------------------------------------

    def post_story(self, story_data: dict) -> str:
        return self._db.create_story(story_data)

    def view_story(self, story_id: str, viewer_id: str) -> bool:
        return self._db.record_story_view(story_id, viewer_id)

    def get_recent_stories(self, user_id: str, limit: int = 50) -> List[dict]:
        return self._db.get_recent_stories(user_id, limit)

    # ------------------------------------------------------------------
    # Feeds & recommendations
    # ------------------------------------------------------------------

    def get_home_feed(self, user_id: str, limit: int = 30) -> List[dict]:
        return self._db.get_home_feed(user_id, limit=limit)

    def set_recommendation(self, user_id: str, photo_ids: List[str], round_id: str) -> str:
        return self._db.add_recommendation(user_id, photo_ids, round_id)

    def get_recommendation(self, user_id: str, round_id: str) -> Optional[List[str]]:
        return self._db.get_recommendation(user_id, round_id)

    def get_follow_recommendations(self, user_id: str, limit: int = 5) -> List[str]:
        return self.follow_recsys.recommend_users_to_follow(user_id, limit)

    def report_content(self, reporter_id: str, content_id: str, content_type: str, reason: str, round_id: str):
        return self._db.add_report(reporter_id, content_id, content_type, reason, round_id)

    # ------------------------------------------------------------------
    # Phase 8 Extended Mechanics
    # ------------------------------------------------------------------

    def add_follow_request(self, follower_id: str, user_id: str) -> str:
        return self._db.add_follow_request(follower_id, user_id)

    def review_follow_request(self, follower_id: str, user_id: str, action: str, round_id: str) -> bool:
        return self._db.review_follow_request(follower_id, user_id, action, round_id)

    def get_pending_follow_requests(self, user_id: str) -> List[dict]:
        return self._db.get_pending_follow_requests(user_id)

    def save_photo(self, user_id: str, photo_id: str) -> str:
        return self._db.save_photo(user_id, photo_id)

    def get_saved_photos(self, user_id: str, limit: int = 30) -> List[dict]:
        return self._db.get_saved_photos(user_id, limit)

    def send_dm(self, sender_id: str, recipient_id: str, content: str, photo_id: str = None) -> str:
        return self._db.send_dm(sender_id, recipient_id, content, photo_id)

    def get_dms(self, user_id: str, limit: int = 50) -> List[dict]:
        return self._db.get_dms(user_id, limit)

    def get_explore_feed(self, user_id: str, limit: int = 30) -> List[dict]:
        return self._db.get_explore_feed(user_id, limit)

    def get_hashtag_feed(self, hashtag: str, limit: int = 30) -> List[dict]:
        return self._db.get_hashtag_feed(hashtag, limit)

    # ------------------------------------------------------------------
    # Media Services
    # ------------------------------------------------------------------

    def save_media(self, content_base64: str, extension: str = "jpg") -> str:
        return self.media_service.save_media(content_base64, extension)

    # ------------------------------------------------------------------
    # Hashtags
    # ------------------------------------------------------------------

    def get_or_create_hashtag(self, tag: str) -> str:
        return self._db.get_or_create_hashtag(tag)

    def tag_photo(self, photo_id: str, hashtag_id: str) -> None:
        self._db.tag_photo(photo_id, hashtag_id)

    # ------------------------------------------------------------------
    # Interests
    # ------------------------------------------------------------------

    def get_or_create_interest(self, name: str) -> str:
        return self._db.get_or_create_interest(name)
        
    def get_user_interests(self, user_id: str) -> List[str]:
        return self._db.get_user_interests(user_id)

    def set_user_interests(self, user_id: str, interest_ids: List[str], round_id: str) -> None:
        self._db.set_user_interests(user_id, interest_ids, round_id)

    # ------------------------------------------------------------------
    # Memory persistence
    # ------------------------------------------------------------------

    def add_memory_event(self, event_data: dict) -> int:
        return self._db.add_memory_event(event_data)

    def get_memory_events(self, run_id: str, agent_user_id: str,
                          limit: int = 100) -> List[dict]:
        return self._db.get_memory_events(run_id, agent_user_id, limit=limit)

    # ------------------------------------------------------------------
    # Stage 5 & 6 (Sentiment and Opinion)
    # ------------------------------------------------------------------

    def update_photo_sentiment(self, photo_id: str, sentiment_score: float) -> bool:
        return self._db.update_photo_sentiment(photo_id, sentiment_score)

    def update_comment_sentiment(self, comment_id: str, sentiment_score: float) -> bool:
        return self._db.update_comment_sentiment(comment_id, sentiment_score)

    def update_user_opinion(self, user_id: str, topic: str, opinion_score: float) -> bool:
        return self._db.update_user_opinion(user_id, topic, opinion_score)

    def get_user_opinions(self, user_id: str) -> dict:
        return self._db.get_user_opinions(user_id)
