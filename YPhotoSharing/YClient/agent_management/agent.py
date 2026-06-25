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

# Story actions
from YPhotoSharing.YClient.actions.post_story import post_story
from YPhotoSharing.YClient.actions.watch_story import watch_story

logger = logging.getLogger(__name__)

# Probability weights for action selection (dynamic from config)
# DEFAULT_ACTION_WEIGHTS removed in favor of YSimulator config


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
        action_logger=None,
        action_weights: Optional[Dict[str, float]] = None,
        image_gen_service = None,
        opinion_manager = None,
        stress_reward_system = None,
        stress_reward_enabled: bool = False,
        stress_reward_backward_rounds: int = 24,
    ):
        self.user_id: str = user_data["id"]
        self.username: str = user_data.get("username", "agent")
        self.opinion_manager = opinion_manager
        self.cluster_id: int = int(user_data.get("recsys_type") or 0)
        self.user_data = user_data
        self.server = server
        self.llm_service = llm_service
        self.action_logger = action_logger or logger
        self.image_gen_service = image_gen_service
        self.action_weights = action_weights or {}
        self.stress_reward_system = stress_reward_system
        self.stress_reward_enabled = stress_reward_enabled
        self.stress_reward_backward_rounds = stress_reward_backward_rounds
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
                self.cluster_id,
                agent_attrs=self.user_data,
            )

        results = []
        # Phase 10: Churn Check
        if self.user_data.get("is_churned"):
            return [{"action": "churned", "status": "inactive"}]

        # Sync user_data from server to get updated stats
        try:
            updated_user = await self.server.get_user.remote(self.user_id)
            if updated_user:
                self.user_data = updated_user
        except Exception as e:
            logger.warning(f"Could not sync user_data for {self.user_id}: {e}")

        # If user is churned after sync, stop
        if self.user_data.get("is_churned"):
            return [{"action": "churned", "status": "inactive"}]

        try:
            await self.server.update_last_active_day.remote(self.user_id, day)
        except Exception as exc:
            logger.warning(f"Could not update last_active_day for {self.user_id}: {exc}")

        # Phase 10: Evaluate Satisfaction
        await self._update_satisfaction()

        # Phase 10: Attention Budget
        # round_actions limits how many actions the agent can attempt in the slot;
        # attention_budget can stop the session earlier when costs are exhausted.
        attention_budget = self.user_data.get("attention_budget", 100)
        round_actions = int(self.user_data.get("round_actions", self._round_actions) or self._round_actions)
        if self.user_data.get("is_page"):
            round_actions = 1
        else:
            round_actions = max(1, round_actions)
            lower = max(round_actions - 2, 1)
            round_actions = random.randint(lower, round_actions)

        self.interacted_users = set()
        
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

        for _ in range(round_actions):
            if attention_budget <= 0:
                break
            action = self._sample_action()
            cost = costs.get(action, 10)

            if attention_budget < cost:
                break # Not enough attention for this action, end session
                
            attention_budget -= cost
            
            try:
                result = await self._execute_action(action, day, hour, round_id)
                if result:
                    results.append({"action": action, **result})
                    self.action_logger.info(
                        "Agent action completed",
                        extra={
                            "extra_data": {
                                "agent_id": self.user_id,
                                "username": self.username,
                                "round_id": round_id,
                                "day": day,
                                "hour": hour,
                                "action": action,
                                "result": result,
                            }
                        },
                    )
            except Exception as exc:
                logger.warning(f"Agent {self.user_id} action '{action}' failed: {exc}")
                self.action_logger.warning(
                    "Agent action failed",
                    extra={
                        "extra_data": {
                            "agent_id": self.user_id,
                            "username": self.username,
                            "round_id": round_id,
                            "day": day,
                            "hour": hour,
                            "action": action,
                            "error": str(exc),
                        }
                    },
                )

        # Stage 7: Secondary Follows
        prob_sec = self.user_data.get("probability_of_secondary_follow", 0.0)
        if prob_sec > 0:
            for target_id in self.interacted_users:
                if target_id and target_id != self.user_id and random.random() < prob_sec:
                    from YPhotoSharing.YClient.actions.request_follow import request_follow
                    try:
                        decision = await request_follow(self.server, self.user_id, target_id, round_id)
                        if decision == "FOLLOW":
                            results.append({"action": "secondary_follow", "target_user_id": target_id})
                            self.action_logger.info(
                                "Secondary follow completed",
                                extra={
                                    "extra_data": {
                                        "agent_id": self.user_id,
                                        "round_id": round_id,
                                        "target_user_id": target_id,
                                    }
                                },
                            )
                    except Exception as e:
                        logger.warning(f"Secondary follow failed for {self.user_id}: {e}")
                        self.action_logger.warning(
                            "Secondary follow failed",
                            extra={
                                "extra_data": {
                                    "agent_id": self.user_id,
                                    "round_id": round_id,
                                    "target_user_id": target_id,
                                    "error": str(e),
                                }
                            },
                        )

        return results

    def _sample_action(self) -> str:
        actions = list(self.action_weights.keys())
        weights = list(self.action_weights.values())
        return random.choices(actions, weights=weights, k=1)[0]

    async def _update_satisfaction(self):
        """Update the agent's satisfaction score algorithmically based on simulation state."""
        # Simple heuristic: if the agent hasn't received new followers, lower satisfaction.
        try:
            stats = await self.server.get_user.remote(self.user_id)
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
        elif action == "post_story":
            return await self._action_post_story(day, hour, round_id)
        elif action == "watch_story":
            return await self._action_watch_story(round_id)
        return None

    # ------------------------------------------------------------------
    # Individual action helpers
    # ------------------------------------------------------------------

    async def _action_post_photo(self, day: int, hour: int, round_id: str) -> Optional[dict]:
        user_interests = await self.server.get_user_interests.remote(self.user_id)
        if user_interests:
            topic = random.choice(user_interests)
        else:
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
            self.action_logger.info(
                "Post photo completed",
                extra={
                    "extra_data": {
                        "agent_id": self.user_id,
                        "round_id": round_id,
                        "day": day,
                        "hour": hour,
                        "topic": topic,
                        "photo_id": photo_id,
                    }
                },
            )
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
            agent_attrs=self.user_data,
            opinion_manager=self.opinion_manager,
            stress_reward_system=self.stress_reward_system,
            stress_reward_enabled=self.stress_reward_enabled,
            stress_reward_backward_rounds=self.stress_reward_backward_rounds,
        )
        if reaction:
            if hasattr(self, "interacted_users") and "user_id" in photo:
                self.interacted_users.add(photo["user_id"])
            self.action_logger.info(
                "React action completed",
                extra={
                    "extra_data": {
                        "agent_id": self.user_id,
                        "round_id": round_id,
                        "photo_id": photo.get("id"),
                        "reaction": reaction,
                    }
                },
            )
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
            opinion_manager=self.opinion_manager,
            stress_reward_system=self.stress_reward_system,
            stress_reward_enabled=self.stress_reward_enabled,
            stress_reward_backward_rounds=self.stress_reward_backward_rounds,
        )
        if comment_id:
            if hasattr(self, "interacted_users") and "user_id" in photo:
                self.interacted_users.add(photo["user_id"])
            self.action_logger.info(
                "Comment action completed",
                extra={
                    "extra_data": {
                        "agent_id": self.user_id,
                        "round_id": round_id,
                        "photo_id": photo.get("id"),
                        "comment_id": comment_id,
                    }
                },
            )
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
        self.action_logger.info(
            "Follow action completed",
            extra={
                "extra_data": {
                    "agent_id": self.user_id,
                    "round_id": round_id,
                    "target_user_id": target.get("id"),
                    "decision": decision,
                }
            },
        )
        return {"follow_decision": decision, "target_user_id": target.get("id")}

    async def _action_share(self, round_id: str) -> Optional[dict]:
        return await share_photo(
            self.server,
            user_id=self.user_id,
            round_id=round_id,
            stress_reward_system=self.stress_reward_system,
            stress_reward_enabled=self.stress_reward_enabled,
            stress_reward_backward_rounds=self.stress_reward_backward_rounds,
        )

    async def _action_report(self, round_id: str) -> Optional[dict]:
        return await report_content(
            server=self.server,
            llm_service=self.llm_service,
            user_id=self.user_id,
            round_id=round_id,
            agent_attrs=self.user_data,
            stress_reward_system=self.stress_reward_system,
            stress_reward_enabled=self.stress_reward_enabled,
            stress_reward_backward_rounds=self.stress_reward_backward_rounds,
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
            self.action_logger.info(
                "Save action completed",
                extra={
                    "extra_data": {
                        "agent_id": self.user_id,
                        "round_id": round_id,
                        "photo_id": photo["id"],
                    }
                },
            )
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
            cluster_id=self.cluster_id,
            agent_attrs=self.user_data,
            opinion_manager=self.opinion_manager,
            stress_reward_system=self.stress_reward_system,
            stress_reward_enabled=self.stress_reward_enabled,
            stress_reward_backward_rounds=self.stress_reward_backward_rounds,
        )
        if success:
            self.action_logger.info(
                "Reply comment completed",
                extra={
                    "extra_data": {
                        "agent_id": self.user_id,
                        "round_id": round_id,
                        "photo_id": photo["id"],
                        "parent_comment_id": parent_comment["id"],
                    }
                },
            )
            return {"photo_id": photo["id"], "parent_comment_id": parent_comment["id"]}
        return None

    async def _action_unfollow(self, round_id: str) -> Optional[dict]:
        following = await self.server.get_following.remote(self.user_id)
        if not following:
            return None
        target = random.choice(following)
        success = await unfollow_user(self.server, self.user_id, target, round_id)
        if success:
            self.action_logger.info(
                "Unfollow action completed",
                extra={
                    "extra_data": {
                        "agent_id": self.user_id,
                        "round_id": round_id,
                        "target_user_id": target,
                    }
                },
            )
            return {"target_user_id": target}
        return None

    async def _action_send_dm(self, day: int, hour: int, round_id: str) -> Optional[dict]:
        following = await self.server.get_following.remote(self.user_id)
        if not following:
            return None
        target = random.choice(following)
        
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
            cluster_id=self.cluster_id,
            agent_attrs=self.user_data,
        )
        if success:
            self.action_logger.info(
                "DM action completed",
                extra={
                    "extra_data": {
                        "agent_id": self.user_id,
                        "round_id": round_id,
                        "target_user_id": target,
                        "photo_id": photo_id,
                    }
                },
            )
            return {"target_user_id": target, "photo_id": photo_id}
        return None

    async def _action_post_story(self, day: int, hour: int, round_id: str) -> Optional[dict]:
        topic = getattr(self, "_current_topic", "general")
        agent_attrs = self.user_data.copy()
        
        story_id = await post_story(
            server=self.server,
            llm_service=self.llm_service,
            user_id=self.user_id,
            cluster_id=self.cluster_id,
            round_id=round_id,
            day=day,
            slot=hour,
            topic=topic,
            agent_attrs=agent_attrs,
        )
        if story_id:
            self.action_logger.info(
                "Post story completed",
                extra={
                    "extra_data": {
                        "agent_id": self.user_id,
                        "round_id": round_id,
                        "day": day,
                        "hour": hour,
                        "story_id": story_id,
                    }
                },
            )
            return {"story_id": story_id}
        return None

    async def _action_watch_story(self, round_id: str) -> Optional[dict]:
        story_id = await watch_story(
            server=self.server,
            user_id=self.user_id,
            round_id=round_id,
        )
        if story_id:
            self.action_logger.info(
                "Watch story completed",
                extra={
                    "extra_data": {
                        "agent_id": self.user_id,
                        "round_id": round_id,
                        "story_id": story_id,
                    }
                },
            )
            return {"story_id": story_id}
        return None
