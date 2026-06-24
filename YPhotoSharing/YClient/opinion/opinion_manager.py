"""
Opinion Dynamics Manager for YPhotoSharing.

This module provides the main interface for managing opinion dynamics in the simulation.
It coordinates opinion calculations, inference, and caching.
"""

from typing import Any, Dict, Optional

import ray


class OpinionManager:
    """
    Main manager for opinion dynamics in the simulation.

    This class provides a unified interface for all opinion-related operations:
    - Checking if opinion dynamics is enabled
    - Mapping opinion values to group labels
    - Getting agent opinions for posts
    - Calculating opinion updates from interactions
    - Inferring page agent opinions from articles

    The manager coordinates between the calculator, inferencer, and cache components.
    """

    def __init__(
        self,
        simulation_config: Dict[str, Any],
        server: Any,
        llm_manager: Any,
        agent_profiles: list,
        client_id: str,
        logger: Any,
    ):
        """
        Initialize the opinion manager.

        Args:
            simulation_config: Simulation configuration dict
            server: Ray actor handle for orchestrator server
            llm_manager: LLMManager instance for LLM operations
            agent_profiles: List of agent profiles
            client_id: Client identifier
            logger: Logger instance
        """
        self.simulation_config = simulation_config
        self.server = server
        self.llm_manager = llm_manager
        self.agent_profiles = agent_profiles
        self.client_id = client_id
        self.logger = logger

        # Get opinion dynamics configuration
        self.opinion_config = simulation_config.get("opinion_dynamics", {})

        # Import sub-components lazily to avoid circular imports
        from YPhotoSharing.YClient.opinion.opinion_cache import OpinionCache
        from YPhotoSharing.YClient.opinion.opinion_calculator import OpinionCalculator
        from YPhotoSharing.YClient.opinion.opinion_inferencer import OpinionInferencer

        # Initialize sub-components
        self.calculator = OpinionCalculator(
            opinion_config=self.opinion_config,
            server=server,
            llm_manager=llm_manager,
            client_id=client_id,
            logger=logger,
            get_opinion_group_fn=self.map_opinion_to_group,
        )

        self.inferencer = OpinionInferencer(
            opinion_config=self.opinion_config,
            llm_manager=llm_manager,
            logger=logger,
        )

        self.cache = OpinionCache(logger=logger)

    def is_enabled(self) -> bool:
        """
        Check if opinion dynamics is enabled in the simulation configuration.

        Returns:
            bool: True if opinion dynamics is enabled, False otherwise
        """
        return self.opinion_config.get("enabled", False)

    def map_opinion_to_group(self, opinion_value: float) -> str:
        """
        Map a numeric opinion value to a discrete opinion group label.

        Args:
            opinion_value: Numeric opinion in [0, 1]

        Returns:
            str: Opinion group label from simulation_config opinion_groups
        """
        opinion_groups = self.opinion_config.get("opinion_groups", {})

        if not opinion_groups:
            # Default mapping if not configured
            if opinion_value < 0.2:
                return "Strongly against"
            elif opinion_value < 0.4:
                return "Against"
            elif opinion_value < 0.6:
                return "Neutral"
            elif opinion_value < 0.8:
                return "In favor"
            else:
                return "Strongly in favor"

        # Find which group the opinion falls into
        for group_name, (lower, upper) in opinion_groups.items():
            if lower <= opinion_value <= upper:
                return group_name

        # Fallback
        return "Neutral"

    def get_opinions_for_post(self, agent_id: str, post_id: str) -> dict:
        """
        Get agent's opinions on the topics discussed in a post.

        Args:
            agent_id: UUID of the agent
            post_id: UUID of the post

        Returns:
            dict: {
                "topics": List of topic names,
                "opinions": Dict mapping topic names to opinion labels,
                "opinion_values": Dict mapping topic names to numeric values
            }
        """
        try:
            # Check if opinion dynamics is enabled
            if not self.is_enabled():
                return {"topics": [], "opinions": {}, "opinion_values": {}}

            # Get agent profile
            agent_profile = next((a for a in self.agent_profiles if a.id == agent_id), None)
            if not agent_profile or not agent_profile.opinions:
                return {"topics": [], "opinions": {}, "opinion_values": {}}

            # Get post topics
            topic_ids = ray.get(
                self.server.get_photo_topics.remote(post_id)
            )
            if not topic_ids:
                return {"topics": [], "opinions": {}, "opinion_values": {}}

            # For each topic, get the agent's opinion
            topics = []
            opinions = {}
            opinion_values = {}

            for topic_id in topic_ids:
                # Get topic name
                topic_name = ray.get(
                    self.server.get_topic_name_from_id.remote(topic_id, client_id=self.client_id)
                )
                if not topic_name:
                    continue

                # Get agent's opinion on this topic
                if topic_name in agent_profile.opinions:
                    opinion_value = agent_profile.opinions[topic_name]
                    opinion_label = self.map_opinion_to_group(opinion_value)

                    topics.append(topic_name)
                    opinions[topic_name] = opinion_label
                    opinion_values[topic_name] = opinion_value

            return {"topics": topics, "opinions": opinions, "opinion_values": opinion_values}
        except Exception as e:
            self.logger.error(
                f"Error getting opinions for post {post_id}: {e}",
                extra={"extra_data": {"error": str(e), "agent_id": agent_id, "post_id": post_id}},
            )
            return {"topics": [], "opinions": {}, "opinion_values": {}}

    def calculate_opinion_updates(
        self, agent_id: str, parent_post_id: str, parent_post_data: dict
    ) -> Optional[dict]:
        """
        Calculate opinion updates when an agent comments on a post.

        This delegates to the OpinionCalculator component.

        Args:
            agent_id: UUID of the agent making the comment
            parent_post_id: UUID of the post being commented on
            parent_post_data: Dictionary containing post data including user_id

        Returns:
            dict: Mapping of topic_id to new opinion value, or None if no updates
        """
        if not self.is_enabled():
            return None

        return self.calculator.calculate_updates(
            agent_id=agent_id,
            parent_post_id=parent_post_id,
            parent_post_data=parent_post_data,
            agent_profiles=self.agent_profiles,
        )

    def infer_photo_agent_opinion(
        self, agent_id: str, photo_content: str, topic_name: str
    ) -> float:
        """
        Infer opinion for a page agent on a topic from photo content.

        This delegates to the OpinionInferencer component.

        Args:
            agent_id: Agent UUID
            photo_content: Photo text to analyze
            topic_name: Topic to infer opinion about

        Returns:
            float: Opinion value in [0, 1] range
        """
        # Get agent profile to determine if LLM or rule-based
        agent_profile = next((a for a in self.agent_profiles if a.id == agent_id), None)

        return self.inferencer.infer_opinion(
            agent_profile=agent_profile,
            photo_content=photo_content,
            topic_name=topic_name,
        )
