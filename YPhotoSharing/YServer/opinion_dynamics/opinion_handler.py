"""
Opinion handler for managing agent opinions.

Handles opinion existence checks, updates, and neighbor opinion retrieval.
"""

import logging
from typing import List, Optional


class OpinionHandler:
    """
    Handles opinion dynamics for agents in the simulation.

    Manages opinion creation, updates, and retrieval, supporting
    both bounded confidence models and LLM-based opinion inference.
    """

    def __init__(
        self,
        db_adapter,
        simulation_config: dict,
        agent_profiles_cache: dict,
        current_round_id_getter: callable,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize opinion handler.

        Args:
            db_adapter: Database adapter for opinion storage/retrieval
            simulation_config: Simulation configuration dict
            agent_profiles_cache: Cache of agent profiles for opinion lookup
            current_round_id_getter: Callable that returns current round ID
            logger: Logger instance
        """
        self.db = db_adapter
        self.simulation_config = simulation_config
        self.agent_profiles_cache = agent_profiles_cache
        self._get_current_round_id = current_round_id_getter
        self.logger = logger or logging.getLogger(__name__)

        # Get opinion dynamics configuration
        self.opinion_config = simulation_config.get("opinion_dynamics", {})
        self.enabled = self.opinion_config.get("enabled", False)

    def ensure_agent_opinion_exists(
        self, agent_id: str, topic_id: str, topic_name: str, article_content: str = None
    ) -> None:
        """
        Check if agent has opinion on topic and log status.

        IMPORTANT: This method NO LONGER creates opinions preemptively.
        Opinion creation is deferred to interaction time when the opinion dynamics
        model can properly handle the cold_start parameter.

        The opinion dynamics models have a cold_start parameter that defines
        how to handle interactions where the agent doesn't have an opinion:
        - cold_start="neutral": Initialize with 0.5
        - cold_start="inherited": Adopt the interlocutor's opinion

        Creating opinions preemptively with 0.5 would bypass the cold_start logic
        and break the "inherited" strategy. Therefore, opinions are created ONLY
        during interactions via the opinion dynamics model on the client side.

        Args:
            agent_id: Agent UUID
            topic_id: Topic UUID (from interests table)
            topic_name: Topic name for looking up in cached profile
            article_content: Unused (kept for backwards compatibility)
        """
        # Only check when opinion dynamics is enabled
        if not self.enabled:
            return  # Opinion dynamics disabled

        # Check if agent already has an opinion on this topic
        existing_opinion = self.db.get_latest_agent_opinion(agent_id, topic_id)
        if existing_opinion is not None:
            return  # Opinion already exists

        # Agent doesn't have opinion - this is OK and expected
        # Opinions will be created during interactions via opinion dynamics model
        # with proper cold_start handling (neutral or inherited strategy)
        self.logger.debug(
            f"Agent {agent_id} has no opinion on topic '{topic_name}' yet. "
            f"Opinion will be created during first interaction with cold_start strategy."
        )

    def get_latest_opinion(self, agent_id: str, topic_id: str) -> Optional[float]:
        """
        Get the latest opinion value for an agent on a topic.

        Args:
            agent_id: Agent UUID
            topic_id: Topic UUID

        Returns:
            Latest opinion value or None if not found
        """
        return self.db.get_latest_agent_opinion(agent_id, topic_id)

    def add_opinion(
        self,
        agent_id: str,
        topic_id: str,
        opinion: float,
        id_interacted_with: Optional[str] = None,
        id_post: Optional[str] = None,
    ) -> bool:
        """
        Add an agent opinion record to the database.

        Args:
            agent_id: Agent UUID
            topic_id: Topic UUID
            opinion: Opinion value in [0, 1]
            id_interacted_with: Optional UUID of agent interacted with
            id_post: Optional UUID of post interacted with

        Returns:
            True if successful, False otherwise
        """
        current_round_id = self._get_current_round_id()
        return self.db.add_agent_opinion(
            agent_id, current_round_id, topic_id, opinion, id_interacted_with, id_post
        )

    def get_neighbors_opinions(self, agent_id: str, topic_id: str) -> List[float]:
        """
        Get the opinions of an agent's neighbors (followees) on a specific topic.

        This method retrieves the latest opinions of all users that the agent follows
        on the specified topic. Used for LLM-based opinion dynamics with evaluation_scope="neighbors".

        Args:
            agent_id: Agent UUID
            topic_id: Topic UUID

        Returns:
            List of opinion values (floats in [0, 1]) from the agent's neighbors
        """
        try:
            if self.db.use_redis:
                return self._get_neighbors_opinions_redis(agent_id, topic_id)
            else:
                return self._get_neighbors_opinions_sql(agent_id, topic_id)
        except Exception as e:
            self.logger.error(
                f"Error getting neighbors opinions: {e}",
                extra={"extra_data": {"error": str(e), "agent_id": agent_id, "topic_id": topic_id}},
            )
            return []

    def _get_neighbors_opinions_redis(self, agent_id: str, topic_id: str) -> List[float]:
        """Get neighbors opinions using Redis backend."""
        # Redis implementation: hybrid approach
        # Step 1: Get followees from Redis follow keys
        follow_pattern = self.db.get_redis_key_pattern("follow", "*")
        # Note: Using KEYS here for consistency with follow_recsys_redis.py
        # For large-scale production deployments, consider using SCAN instead
        follow_keys = self.db.redis_client.keys(follow_pattern)

        # Encode agent_id once for efficiency
        agent_id_bytes = agent_id.encode()

        followee_ids = set()
        for key in follow_keys:
            follow_data = self.db.redis_client.hgetall(key)
            # Check if this is a follow relationship for the agent
            if (
                follow_data.get(b"follower_id") == agent_id_bytes
                and follow_data.get(b"action") == b"follow"
            ):
                user_id = follow_data.get(b"user_id")
                if user_id:
                    followee_ids.add(user_id.decode())

        if not followee_ids:
            return []

        # Step 2: Get opinions from Redis for each followee
        opinions = []
        for followee_id in followee_ids:
            opinion = self.db.get_latest_agent_opinion(followee_id, topic_id)
            if opinion is not None:
                opinions.append(opinion)

        return opinions

    def _get_neighbors_opinions_sql(self, agent_id: str, topic_id: str) -> List[float]:
        """Get neighbors opinions using SQL backend."""
        from sqlalchemy.orm import Session

        from YPhotoSharing.YServer.classes.models import Follow

        with Session(self.db.engine) as session:
            # Get list of user_ids that agent follows (where agent is the follower and
            # action='follow')
            followees_query = (
                session.query(Follow.user_id)
                .filter(Follow.follower_id == agent_id, Follow.action == "follow")
                .all()
            )

            followee_ids = [row[0] for row in followees_query]

            if not followee_ids:
                return []

            # Get opinions of each followee on this topic
            opinions = []
            for followee_id in followee_ids:
                opinion = self.db.get_latest_agent_opinion(followee_id, topic_id)
                if opinion is not None:
                    opinions.append(opinion)

            return opinions
