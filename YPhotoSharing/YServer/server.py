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
        self._db.get_or_create_round(self._current_day, self._current_hour)
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

    # ------------------------------------------------------------------
    # Feeds & recommendations
    # ------------------------------------------------------------------

    def get_home_feed(self, user_id: str, limit: int = 30) -> List[dict]:
        return self._db.get_home_feed(user_id, limit=limit)

    def set_recommendation(self, user_id: str, photo_ids: List[str], round_id: str) -> str:
        return self._db.add_recommendation(user_id, photo_ids, round_id)

    def get_recommendation(self, user_id: str, round_id: str) -> Optional[List[str]]:
        return self._db.get_recommendation(user_id, round_id)

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
