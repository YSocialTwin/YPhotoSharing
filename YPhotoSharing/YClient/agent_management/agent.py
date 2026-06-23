"""
Agent class for YPhotoSharing simulation.

Each Agent wraps a user profile and orchestrates LLM-driven actions
(posting photos, reacting, commenting, following) via the Ray server.
"""

import logging
import random
from typing import Any, Dict, List, Optional

import ray

from YPhotoSharing.YClient.actions.comment import post_comment
from YPhotoSharing.YClient.actions.follow import follow_user
from YPhotoSharing.YClient.actions.post_photo import post_photo
from YPhotoSharing.YClient.actions.react import react_to_photo

logger = logging.getLogger(__name__)

# Probability weights for action selection (normalised internally)
DEFAULT_ACTION_WEIGHTS = {
    "post_photo": 0.20,
    "react": 0.40,
    "comment": 0.25,
    "follow": 0.15,
}


class Agent:
    """
    Simulated Instagram user agent.

    Attributes:
        user_id: UUID of the simulated user
        username: Display name
        cluster_id: Persona cluster (maps to LLM persona)
        server: Ray handle to OrchestratorServer
        llm_service: Ray handle to an LLM service actor
    """

    def __init__(
        self,
        user_data: dict,
        server,
        llm_service,
        action_weights: Optional[Dict[str, float]] = None,
    ):
        self.user_id: str = user_data["id"]
        self.username: str = user_data.get("username", "agent")
        self.cluster_id: int = int(user_data.get("recsys_type") or 0)
        self.user_data = user_data
        self.server = server
        self.llm_service = llm_service
        self.action_weights = action_weights or DEFAULT_ACTION_WEIGHTS
        self._round_actions = user_data.get("round_actions", 3)

    # ------------------------------------------------------------------

    async def run_round(self, day: int, hour: int, round_id: str) -> List[dict]:
        """
        Execute up to *round_actions* actions for this simulation round.

        Returns a list of action result dicts for logging.
        """
        results = []
        n_actions = self._round_actions

        for _ in range(n_actions):
            action = self._sample_action()
            try:
                result = await self._execute_action(action, day, hour, round_id)
                if result:
                    results.append({"action": action, **result})
            except Exception as exc:
                logger.warning(f"Agent {self.user_id} action '{action}' failed: {exc}")

        return results

    def _sample_action(self) -> str:
        actions = list(self.action_weights.keys())
        weights = list(self.action_weights.values())
        return random.choices(actions, weights=weights, k=1)[0]

    async def _execute_action(self, action: str, day: int,
                               hour: int, round_id: str) -> Optional[dict]:
        if action == "post_photo":
            return await self._action_post_photo(day, hour, round_id)
        elif action == "react":
            return await self._action_react(round_id)
        elif action == "comment":
            return await self._action_comment(round_id)
        elif action == "follow":
            return await self._action_follow(round_id)
        return None

    # ------------------------------------------------------------------
    # Individual action helpers
    # ------------------------------------------------------------------

    async def _action_post_photo(self, day: int, hour: int, round_id: str) -> Optional[dict]:
        topics = ["travel", "food", "fitness", "art", "nature", "fashion", "technology"]
        topic = random.choice(topics)
        photo_id = await post_photo(
            server=self.server,
            llm_service=self.llm_service,
            user_id=self.user_id,
            cluster_id=self.cluster_id,
            round_id=round_id,
            day=day,
            slot=hour,
            topic=topic,
            agent_attrs=self.user_data,
        )
        if photo_id:
            return {"photo_id": photo_id, "topic": topic}
        return None

    async def _action_react(self, round_id: str) -> Optional[dict]:
        feed: List[dict] = await self.server.get_home_feed.remote(
            user_id=self.user_id, limit=10
        )
        if not feed:
            return None
        photo = random.choice(feed)
        reaction = await react_to_photo(
            server=self.server,
            llm_service=self.llm_service,
            user_id=self.user_id,
            photo=photo,
            round_id=round_id,
        )
        if reaction:
            return {"reaction": reaction, "photo_id": photo.get("id")}
        return None

    async def _action_comment(self, round_id: str) -> Optional[dict]:
        feed: List[dict] = await self.server.get_home_feed.remote(
            user_id=self.user_id, limit=10
        )
        if not feed:
            return None
        photo = random.choice(feed)
        comment_id = await post_comment(
            server=self.server,
            llm_service=self.llm_service,
            user_id=self.user_id,
            photo=photo,
            round_id=round_id,
            cluster_id=self.cluster_id,
            agent_attrs=self.user_data,
        )
        if comment_id:
            return {"comment_id": comment_id, "photo_id": photo.get("id")}
        return None

    async def _action_follow(self, round_id: str) -> Optional[dict]:
        all_users: List[dict] = await self.server.list_users.remote(limit=20)
        candidates = [u for u in all_users if u.get("id") != self.user_id]
        if not candidates:
            return None
        target = random.choice(candidates)
        decision = await follow_user(
            server=self.server,
            llm_service=self.llm_service,
            follower_id=self.user_id,
            target_user=target,
            round_id=round_id,
            cluster_id=self.cluster_id,
        )
        return {"follow_decision": decision, "target_user_id": target.get("id")}
