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
import functools
import time
import uuid
import inspect
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import ray

from YPhotoSharing.common_utils import build_json_line_file_logger, setup_logging
from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware
from YPhotoSharing.YServer.services.recommendation_service import RecommendationService
from YPhotoSharing.YServer.services.photo_enrichment_service import PhotoEnrichmentService
from YPhotoSharing.YServer.services.virality_service import ViralityService
from YPhotoSharing.YServer.services.influence_service import InfluenceService
from YPhotoSharing.YServer.services.moderation_service import ModerationService
from YPhotoSharing.YServer.services.analytics_service import AnalyticsService
from YPhotoSharing.YServer.services.media_service import MediaService
from YPhotoSharing.YServer.services.social_action_service import SocialActionService
from YPhotoSharing.YServer.recsys.follow_recsys import FollowRecsys
from YPhotoSharing.YServer.repositories.social_action_repository import SocialActionRepository

logger = logging.getLogger(__name__)


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
        self.current_round_id = None

        global logger
        logger = setup_logging(
            Path(config_path),
            "server",
            self.simulation_config.get("logging", {}),
            instance_name=self.server_name,
        )
        self.logger = logger

        logging_config = self.simulation_config.get("logging", {}) or {}
        self.request_logger = None
        if logging_config.get("enable_request_log", True):
            self.request_logger = build_json_line_file_logger(
                f"YPhotoSharing.Server.Requests.{self.server_name}",
                Path(config_path) / "logs" / "_server.log",
                propagate=False,
            )

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
        self.social_action_repository = SocialActionRepository(self._db)
        self.social_action_service = SocialActionService(
            repository=self.social_action_repository,
            logger=logger,
        )

        # Initialize YSimulator Managers
        from YPhotoSharing.YServer.interests_modeling.interest_manager import InterestManager
        from YPhotoSharing.YServer.opinion_dynamics.opinion_handler import OpinionHandler
        from YPhotoSharing.YServer.coordination.round_manager import RoundManager
        from YPhotoSharing.YServer.coordination.archetype_manager import ArchetypeManager
        from YPhotoSharing.YServer.coordination.client_manager import ClientManager

        self.interest_manager = InterestManager(db_service=self._db)
        self.opinion_handler = OpinionHandler(
            db_adapter=self._db,
            simulation_config=self.simulation_config,
            agent_profiles_cache={},
            current_round_id_getter=lambda: self.current_round_id,
            logger=logger
        )
        self.round_manager = RoundManager(
            db_adapter=self._db,
            interest_manager=self.interest_manager,
            num_slots_per_day=self.simulation_config.get("simulation", {}).get("num_slots_per_day", 24),
            visibility_rounds=self.simulation_config.get("posts", {}).get("visibility_rounds", 36),
            logger=logger
        )
        self.archetype_manager = ArchetypeManager(
            db_adapter=self._db,
            archetypes_enabled=self.simulation_config.get("agent_archetypes", {}).get("enabled", False),
            archetype_transitions=self.simulation_config.get("agent_archetypes", {}).get("transitions", {}),
            logger=logger
        )
        self.client_manager = ClientManager(timeout_seconds=self.timeout_seconds, logger=logger)

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
        self.current_round_id = round_id
        
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
        round_id = self._db.get_or_create_round(day, hour)
        self.current_round_id = round_id
        return round_id

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def create_user(self, user_data: dict) -> str:
        return self._db.create_user(user_data)

    def update_satisfaction(self, user_id: str, delta: float) -> float:
        return self._db.update_satisfaction(user_id, delta)

    def set_churn_state(self, user_id: str, is_churned: bool) -> bool:
        return self._db.set_churn_state(user_id, is_churned)

    def update_last_active_day(self, user_id: str, day: int) -> bool:
        return self._db.update_last_active_day(user_id, day)

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
        return self.social_action_service.post_photo(photo_data)

    def add_photo_emotion(self, photo_id: str, emotion: str) -> bool:
        return self.social_action_service.add_photo_emotion(photo_id, emotion)

    def get_photo(self, photo_id: str) -> Optional[dict]:
        return self.social_action_service.get_photo(photo_id)

    def get_photo_topics(self, photo_id: str) -> list:
        return self.social_action_service.get_photo_topics(photo_id)

    def get_topic_name_from_id(self, topic_id: str, client_id: str = None) -> Optional[str]:
        return self._db.get_topic_name_from_id(topic_id)

    def get_user_photos(self, user_id: str, limit: int = 20, offset: int = 0) -> List[dict]:
        return self.social_action_service.get_user_photos(user_id, limit=limit, offset=offset)

    def delete_photo(self, photo_id: str) -> bool:
        return self.social_action_service.delete_photo(photo_id)

    # ------------------------------------------------------------------
    # Reactions
    # ------------------------------------------------------------------

    def react_to_photo(self, user_id: str, photo_id: str,
                       reaction_type: str, round_id: str) -> str:
        return self.social_action_service.react_to_photo(user_id, photo_id, reaction_type, round_id)

    def remove_reaction(self, user_id: str, photo_id: str) -> bool:
        return self.social_action_service.remove_reaction(user_id, photo_id)

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def post_comment(self, user_id: str, photo_id: str, body: str,
                     round_id: str, parent_comment_id: str = None) -> str:
        return self.social_action_service.post_comment(
            user_id, photo_id, body, round_id, parent_comment_id
        )

    def get_comments(self, photo_id: str, limit: int = 50) -> List[dict]:
        return self.social_action_service.get_comments(photo_id, limit=limit)

    # ------------------------------------------------------------------
    # Stories
    # ------------------------------------------------------------------

    def post_story(self, story_data: dict) -> str:
        return self.social_action_service.post_story(story_data)

    def view_story(self, story_id: str, viewer_id: str) -> bool:
        return self.social_action_service.view_story(story_id, viewer_id)

    def get_recent_stories(self, user_id: str, limit: int = 50) -> List[dict]:
        return self.social_action_service.get_recent_stories(user_id, limit)

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
        return self.social_action_service.add_report(
            reporter_id, content_id, content_type, reason, round_id
        )

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
        return self.social_action_service.save_photo(user_id, photo_id)

    def get_saved_photos(self, user_id: str, limit: int = 30) -> List[dict]:
        return self.social_action_service.get_saved_photos(user_id, limit)

    def send_dm(self, sender_id: str, recipient_id: str, content: str, photo_id: str = None) -> str:
        return self.social_action_service.send_dm(sender_id, recipient_id, content, photo_id)

    def get_dms(self, user_id: str, limit: int = 50) -> List[dict]:
        return self.social_action_service.get_dms(user_id, limit)

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

    def update_user_opinion(
        self,
        user_id: str,
        topic: str,
        opinion_score: float,
        round_id: str,
        topic_id: str = None,
        opinion_label: str = None,
        model_name: str = None,
    ) -> bool:
        return self._db.update_user_opinion(
            user_id,
            topic,
            opinion_score,
            round_id,
            topic_id=topic_id,
            opinion_label=opinion_label,
            model_name=model_name,
        )

    def get_user_opinions(self, user_id: str) -> dict:
        return self._db.get_user_opinions(user_id)

    def get_opinion_paths(self, user_id: str, topic: str = None, limit: int = 100) -> List[dict]:
        return self._db.get_opinion_paths(user_id, topic=topic, limit=limit)

    def get_latest_agent_opinion(self, agent_id: str, topic_id: str, client_id: str = None) -> Optional[float]:
        topic_name = self.get_topic_name_from_id(topic_id, client_id=client_id) or topic_id
        return self._db.get_latest_agent_opinion(agent_id, topic_name)

    def record_opinion_path(
        self,
        user_id: str,
        topic: str,
        round_id: str,
        model_name: str,
        source_score: float,
        source_label: str,
        target_score: float,
        target_label: str,
        transition: str,
        direction: str = None,
        evaluation_scope: str = None,
        topic_id: str = None,
        parent_post_id: str = None,
        actor_user_id: str = None,
        payload_json: str = None,
    ) -> str:
        return self._db.record_opinion_path(
            user_id=user_id,
            topic=topic,
            round_id=round_id,
            model_name=model_name,
            source_score=source_score,
            source_label=source_label,
            target_score=target_score,
            target_label=target_label,
            transition=transition,
            direction=direction,
            evaluation_scope=evaluation_scope,
            topic_id=topic_id,
            parent_post_id=parent_post_id,
            actor_user_id=actor_user_id,
            payload_json=payload_json,
        )

    def get_stress_reward(self, agent_id: str, round_id: str, backward_rounds: int = 24) -> dict:
        return self._db.get_stress_reward(agent_id, round_id, backward_rounds)

    def set_stress_reward_variations(
        self, user_id: str, round_id: str, variations: list, action_name: Optional[str] = None
    ) -> int:
        return self._db.set_stress_reward_variations(user_id, round_id, variations, action_name)


def log_server_request(func):
    """Log public server method calls to the dedicated request log."""

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        request_id = f"{time.time()}-{uuid.uuid4().hex[:10]}"
        client_name = kwargs.get("client_id")
        if not client_name and args:
            try:
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                if len(param_names) > 1 and param_names[1] == "client_id" and isinstance(args[0], str):
                    client_name = args[0]
            except (TypeError, ValueError):
                pass
        if not client_name:
            client_name = "unknown"

        start_time = time.time()
        status_code = 200
        error = None
        try:
            return func(self, *args, **kwargs)
        except Exception as exc:
            status_code = 500
            error = str(exc)
            raise
        finally:
            duration = time.time() - start_time
            log_entry = {
                "request_id": request_id,
                "client_name": client_name,
                "path": func.__name__,
                "status_code": status_code,
                "duration": duration,
                "time": datetime.now(timezone.utc).isoformat(),
                "tid": getattr(self, "current_round_id", None),
                "day": getattr(self, "_current_day", None),
                "hour": getattr(self, "_current_hour", None),
            }
            if error:
                log_entry["error"] = error

            try:
                request_logger = getattr(self, "request_logger", None)
                if request_logger:
                    request_logger.info(json.dumps(log_entry))
                    for handler in request_logger.handlers:
                        handler.flush()
            except Exception as log_error:
                getattr(self, "logger", logger).error(f"Server request logging failed: {log_error}")

    return wrapper


def _wrap_server_methods(cls):
    for name, attr in list(vars(cls).items()):
        if name.startswith("_") or name == "__init__":
            continue
        if callable(attr):
            setattr(cls, name, log_server_request(attr))
    return cls


OrchestratorServer = ray.remote(_wrap_server_methods(OrchestratorServer))
