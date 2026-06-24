"""
Opinion Inferencer for YPhotoSharing.

This module handles inference of opinions for page agents based on article content.
"""

import random
from typing import Any, Dict, Optional

import ray


class OpinionInferencer:
    """
    Inferencer for page agent opinions from article content.

    This class handles opinion inference for page agents:
    - LLM page agents: Use LLM service to infer opinion from article
    - Rule-based page agents: Generate random opinion
    """

    def __init__(
        self,
        opinion_config: Dict[str, Any],
        llm_manager: Any,
        logger: Any,
    ):
        """
        Initialize the opinion inferencer.

        Args:
            opinion_config: Opinion dynamics configuration dict
            llm_manager: LLMManager instance for LLM operations
            logger: Logger instance
        """
        self.opinion_config = opinion_config
        self.llm_manager = llm_manager
        self.logger = logger

    def infer_opinion(
        self,
        agent_profile: Optional[Any],
        photo_content: str,
        topic_name: str,
    ) -> float:
        """
        Infer opinion for a page agent on a topic from article content.

        This method is called CLIENT-SIDE before submitting article posts.
        - LLM page agents: Use LLM service to infer opinion from article
        - Rule-based page agents: Generate random opinion

        Args:
            agent_profile: Agent profile (or None if not found)
            article_content: Article text to analyze
            topic_name: Topic to infer opinion about

        Returns:
            float: Opinion value in [0, 1] range
        """
        try:
            # Check if agent profile exists
            if not agent_profile:
                self.logger.warning("Agent profile not found, using random opinion")
                return random.random()

            # Check if this is an LLM agent
            if agent_profile.llm:
                return self._infer_llm_opinion(
                    agent_id=agent_profile.id,
                    photo_content=photo_content,
                    topic_name=topic_name,
                )
            else:
                return self._generate_random_opinion(
                    agent_id=agent_profile.id, topic_name=topic_name
                )

        except Exception as e:
            self.logger.error(
                f"Error inferring opinion for agent {agent_profile.id if agent_profile else 'unknown'}: {e}. "
                f"Using random value."
            )
            return random.random()

    def _infer_llm_opinion(self, agent_id: str, photo_content: str, topic_name: str) -> float:
        """
        Infer opinion using LLM service.

        Args:
            agent_id: Agent UUID
            photo_content: Photo text/caption to analyze
            topic_name: Topic to infer opinion about

        Returns:
            float: Opinion value in [0, 1] range
        """
        opinion_groups = self.opinion_config.get("opinion_groups", {})

        if not opinion_groups:
            self.logger.warning("No opinion_groups configured, using random opinion")
            return random.random()

        # Call LLM service to infer opinion
        opinion_value = ray.get(
            self.llm_manager.infer_photo_opinion.remote(
                photo_content, topic_name, opinion_groups, agent_id
            )
        )

        self.logger.info(
            f"LLM page agent {agent_id}: inferred opinion {opinion_value} "
            f"on topic '{topic_name}' from photo content"
        )

        return opinion_value

    def _generate_random_opinion(self, agent_id: str, topic_name: str) -> float:
        """
        Generate random opinion for rule-based agents.

        Args:
            agent_id: Agent UUID
            topic_name: Topic name

        Returns:
            float: Random opinion value in [0, 1] range
        """
        opinion_value = random.random()

        self.logger.info(
            f"Rule-based page agent {agent_id}: assigned random opinion {opinion_value} "
            f"on topic '{topic_name}'"
        )

        return opinion_value
