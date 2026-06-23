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
from YPhotoSharing.YClient.actions.share import share_photo
from YPhotoSharing.YClient.actions.report import report_content

# Phase 8 Extended Actions
from YPhotoSharing.YClient.actions.save_photo import save_photo
from YPhotoSharing.YClient.actions.reply_comment import reply_comment
from YPhotoSharing.YClient.actions.unfollow import unfollow_user
from YPhotoSharing.YClient.actions.send_dm import send_dm
from YPhotoSharing.YClient.actions.request_follow import request_follow
from YPhotoSharing.YClient.actions.review_follow_requests import review_follow_requests

logger = logging.getLogger(__name__)

# Probability weights for action selection (normalised internally)
DEFAULT_ACTION_WEIGHTS = {
    "post_photo": 0.15,
    "react": 0.20,
    "comment": 0.15,
    "follow": 0.10,
    "share": 0.05,
    "report": 0.05,
    "save": 0.10,
    "reply_comment": 0.10,
    "unfollow": 0.05,
    "send_dm": 0.05
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
        image_gen_service = None,
    ):
        self.user_id: str = user_data["id"]
        self.username: str = user_data.get("username", "agent")
        self.cluster_id: int = int(user_data.get("recsys_type") or 0)
        self.user_data = user_data
        self.server = server
        self.llm_service = llm_service
        self.image_gen_service = image_gen_service
        self.action_weights = action_weights or DEFAULT_ACTION_WEIGHTS
        self._round_actions = user_data.get("round_actions", 3)

    # ------------------------------------------------------------------

    async def run_round(self, day: int, hour: int, round_id: str) -> List[dict]:
        """
        Execute up to *round_actions* actions for this simulation round.

        Returns a list of action result dicts for logging.
        """
        # Phase 8: Active agents should process their follow requests (if private) once a day
        if self.user_data.get("is_private") and hour == 0:
            await review_follow_requests(
                self.server,
                self.llm_service,
                self.user_id,
                round_id,
                self.cluster_id
            )

        results = []
        # Phase 10: Churn Check
        if self.user_data.get("is_churned"):
            return [{"action": "churned", "status": "inactive"}]

        # Sync user_data from server to get updated stats
        import ray
        try:
            updated_user = ray.get(self.server.get_user.remote(self.user_id))
            if updated_user:
                self.user_data = updated_user
        except Exception as e:
            logger.warning(f"Could not sync user_data for {self.user_id}: {e}")

        # If user is churned after sync, stop
        if self.user_data.get("is_churned"):
            return [{"action": "churned", "status": "inactive"}]

        # Phase 10: Evaluate Satisfaction
        await self._update_satisfaction()

        # Phase 10: Attention Budget
        # Replace fixed number of actions with an attention budget
        attention_budget = self.user_data.get("attention_budget", 100)
        
        # Action Costs
        costs = {
            "post_photo": 40,
            "comment": 20,
            "reply_comment": 20,
            "send_dm": 25,
            "react": 5,
            "save": 5,
            "follow": 10,
            "share": 15,
            "report": 10,
            "unfollow": 5
        }

        while attention_budget > 0:
            action = self._sample_action()
            cost = costs.get(action, 10)
            
            if attention_budget < cost:
                break # Not enough attention for this action, end session
                
            attention_budget -= cost
            
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

    async def _update_satisfaction(self):
        """Update the agent's satisfaction score algorithmically based on simulation state."""
        # Simple heuristic: if the agent hasn't received new followers, lower satisfaction.
        import ray
        try:
            stats = ray.get(self.server.get_user.remote(self.user_id))
            if not stats: return
            
            followers_count = len(stats.get("follower_ids", []))
            last_followers = getattr(self, "_last_followers_count", followers_count)
            
            delta = 0.0
            if followers_count > last_followers:
                delta = 5.0 * (followers_count - last_followers)
            else:
                delta = -1.0 # Slight decay over time
                
            self._last_followers_count = followers_count
            
            new_score = await self.server.update_satisfaction.remote(self.user_id, delta)
            if new_score <= 10.0:
                logger.info(f"Agent {self.user_id} has churned due to low satisfaction.")
                self.user_data["is_churned"] = True
                
        except Exception as e:
            logger.warning(f"Failed to update satisfaction for {self.user_id}: {e}")

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
        elif action == "share":
            return await self._action_share(round_id)
        elif action == "report":
            return await self._action_report(round_id)
        elif action == "save":
            return await self._action_save(round_id)
        elif action == "reply_comment":
            return await self._action_reply_comment(day, hour, round_id)
        elif action == "unfollow":
            return await self._action_unfollow(round_id)
        elif action == "send_dm":
            return await self._action_send_dm(day, hour, round_id)
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
            image_gen_service=self.image_gen_service,
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
        decision = await request_follow(
            server=self.server,
            follower_id=self.user_id,
            user_id=target.get("id"),
            round_id=round_id
        )
        return {"follow_decision": decision, "target_user_id": target.get("id")}

    async def _action_share(self, round_id: str) -> Optional[dict]:
        return await share_photo(
            self.server,
            user_id=self.user_id,
            round_id=round_id,
        )

    async def _action_report(self, round_id: str) -> Optional[dict]:
        return await report_content(
            server=self.server,
            llm_service=self.llm_service,
            user_id=self.user_id,
            round_id=round_id,
            agent_attrs=self.user_data,
        )

    # ------------------------------------------------------------------
    # Phase 8 Helpers
    # ------------------------------------------------------------------

    async def _action_save(self, round_id: str) -> Optional[dict]:
        feed: List[dict] = await self.server.get_explore_feed.remote(
            user_id=self.user_id, limit=10
        )
        if not feed:
            return None
        photo = random.choice(feed)
        success = await save_photo(self.server, self.user_id, photo["id"])
        if success:
            return {"photo_id": photo["id"]}
        return None

    async def _action_reply_comment(self, day: int, hour: int, round_id: str) -> Optional[dict]:
        feed: List[dict] = await self.server.get_home_feed.remote(
            user_id=self.user_id, limit=10
        )
        if not feed:
            return None
        photo = random.choice(feed)
        comments = await self.server.get_comments.remote(photo["id"])
        if not comments:
            return None
        parent_comment = random.choice(comments)
        
        success = await reply_comment(
            server=self.server,
            llm_service=self.llm_service,
            user_id=self.user_id,
            photo_id=photo["id"],
            parent_comment_id=parent_comment["id"],
            round_id=round_id,
            day=day,
            slot=hour,
            cluster_id=self.cluster_id
        )
        if success:
            return {"photo_id": photo["id"], "parent_comment_id": parent_comment["id"]}
        return None

    async def _action_unfollow(self, round_id: str) -> Optional[dict]:
        import ray
        user = ray.get(self.server.get_user.remote(self.user_id))
        if not user or not user.get("following_ids"):
            return None
        target = random.choice(user["following_ids"])
        success = await unfollow_user(self.server, self.user_id, target, round_id)
        if success:
            return {"target_user_id": target}
        return None

    async def _action_send_dm(self, day: int, hour: int, round_id: str) -> Optional[dict]:
        import ray
        user = ray.get(self.server.get_user.remote(self.user_id))
        if not user or not user.get("following_ids"):
            return None
        target = random.choice(user["following_ids"])
        
        feed = await self.server.get_home_feed.remote(self.user_id, limit=5)
        photo_id = random.choice(feed)["id"] if feed else None
        
        success = await send_dm(
            server=self.server,
            llm_service=self.llm_service,
            sender_id=self.user_id,
            recipient_id=target,
            photo_id=photo_id,
            day=day,
            slot=hour,
            cluster_id=self.cluster_id
        )
        if success:
            return {"target_user_id": target, "photo_id": photo_id}
        return None
