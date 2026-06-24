"""
Opinion Calculator for YPhotoSharing.

This module handles the calculation of opinion updates based on interactions.
Supports multiple opinion dynamics models: bounded confidence and LLM evaluation.
"""

from collections import Counter
from typing import Any, Callable, Dict, Optional

import ray

from YPhotoSharing.YClient.opinion_dynamics.confidence_bound import bounded_confidence
from YPhotoSharing.YClient.opinion_dynamics.llm_evaluation import llm_evaluation
from YPhotoSharing.YClient.opinion_dynamics.utils import get_opinion_group


class OpinionCalculator:
    """
    Calculator for opinion updates based on agent interactions.

    This class implements the core opinion dynamics models:
    - Bounded Confidence: Classic model based on confidence bounds
    - LLM Evaluation: LLM-based opinion evaluation for natural reasoning
    """

    def __init__(
        self,
        opinion_config: Dict[str, Any],
        server: Any,
        llm_manager: Any,
        client_id: str,
        logger: Any,
        get_opinion_group_fn: Callable[[float], str],
    ):
        """
        Initialize the opinion calculator.

        Args:
            opinion_config: Opinion dynamics configuration dict
            server: Ray actor handle for orchestrator server
            llm_manager: LLMManager instance for LLM operations
            client_id: Client identifier
            logger: Logger instance
            get_opinion_group_fn: Function to map opinion value to group label
        """
        self.opinion_config = opinion_config
        self.server = server
        self.llm_manager = llm_manager
        self.client_id = client_id
        self.logger = logger
        self.get_opinion_group_fn = get_opinion_group_fn
        self.last_update_events: Dict[str, dict] = {}

    def calculate_updates(
        self,
        agent_id: str,
        parent_post_id: str,
        parent_post_data: dict,
        agent_profiles: list,
    ) -> Optional[dict]:
        """
        Calculate opinion updates when an agent comments on a post.

        Supports two opinion dynamics models based on configuration:
        - "bounded_confidence": Classic bounded confidence model (all agents)
        - "llm_evaluation": LLM-based evaluation (LLM agents only)

        Args:
            agent_id: UUID of the agent making the comment
            parent_post_id: UUID of the post being commented on
            parent_post_data: Dictionary containing post data including user_id
            agent_profiles: List of agent profiles

        Returns:
            dict: Mapping of topic_id to new opinion value, or None if no updates
        """
        try:
            # Check if opinion dynamics config exists
            if not self.opinion_config:
                return None

            self.last_update_events = {}

            # Get model name and parameters
            model_name = self.opinion_config.get("model_name", "bounded_confidence")
            params = self.opinion_config.get("parameters", {})

            # Validate model selection
            if model_name == "llm_evaluation":
                # Check if this is an LLM agent
                agent_profile = next((a for a in agent_profiles if a.id == agent_id), None)
                if not agent_profile or not agent_profile.llm:
                    self.logger.error(
                        f"llm_evaluation model can only be used with LLM agents. "
                        f"Agent {agent_id} is not an LLM agent. Skipping opinion update."
                    )
                    return None

            # Get the parent post author
            parent_author_id = parent_post_data.get("user_id")
            if not parent_author_id:
                return None

            # Get the post topics from server
            topic_ids = ray.get(
                self.server.get_photo_topics.remote(parent_post_id)
            )
            if not topic_ids:
                return None

            # Get post content (needed for LLM evaluation)
            post_content = parent_post_data.get("tweet") or parent_post_data.get("text") or ""

            # Calculate updated opinions for each topic
            updated_opinions = {}
            for topic_id in topic_ids:
                # Get topic name
                topic_name = ray.get(
                    self.server.get_topic_name_from_id.remote(topic_id, client_id=self.client_id)
                )
                if not topic_name:
                    continue

                agent_profile = next((a for a in agent_profiles if a.id == agent_id), None)
                stubborn_topics = getattr(agent_profile, "stubborn_topics", {}) or {}
                if bool(stubborn_topics.get(str(topic_name), False)):
                    continue

                # Get agent's LATEST opinion from database (not cached profile)
                agent_opinion = ray.get(
                    self.server.get_latest_agent_opinion.remote(
                        agent_id, topic_id, client_id=self.client_id
                    )
                )

                # Get author's latest opinion from server
                author_opinion = ray.get(
                    self.server.get_latest_agent_opinion.remote(
                        parent_author_id, topic_id, client_id=self.client_id
                    )
                )

                # Check if author has opinion on topic
                if author_opinion is None:
                    self.logger.debug(
                        f"Author {parent_author_id} has no opinion yet on topic '{topic_name}' "
                        f"(topic_id: {topic_id}) in their post {parent_post_id}. "
                        f"Opinion will be created during this interaction with cold_start strategy. "
                        f"Skipping opinion update calculation for now."
                    )
                    continue

                # Calculate new opinion based on selected model
                if model_name == "llm_evaluation":
                    new_opinion = self._calculate_llm_evaluation(
                        agent_id=agent_id,
                        agent_opinion=agent_opinion,
                        author_opinion=author_opinion,
                        post_content=post_content,
                        topic_id=topic_id,
                        topic_name=topic_name,
                        params=params,
                    )
                else:
                    # Use bounded confidence model (default)
                    new_opinion = self._calculate_bounded_confidence(
                        agent_opinion=agent_opinion,
                        author_opinion=author_opinion,
                        params=params,
                    )

                updated_opinions[topic_id] = new_opinion
                self.last_update_events[topic_id] = {
                    "topic_id": topic_id,
                    "topic_name": topic_name,
                    "model_name": model_name,
                    "evaluation_scope": params.get("evaluation_scope", "interlocutor_only"),
                    "source_score": agent_opinion,
                    "source_label": self.get_opinion_group_fn(agent_opinion)
                    if agent_opinion is not None
                    else None,
                    "target_score": new_opinion,
                    "target_label": self.get_opinion_group_fn(new_opinion),
                    "transition": self._transition_from_scores(agent_opinion, new_opinion),
                    "direction": self._transition_direction(agent_opinion, new_opinion),
                    "author_score": author_opinion,
                    "author_label": self.get_opinion_group_fn(author_opinion)
                    if author_opinion is not None
                    else None,
                    "parent_post_id": parent_post_id,
                    "actor_user_id": agent_id,
                }

                self.logger.info(
                    f"Opinion update calculated (model={model_name}): agent={agent_id}, "
                    f"topic={topic_name}, old={agent_opinion}, author={author_opinion}, new={new_opinion}"
                )

            return updated_opinions if updated_opinions else None

        except Exception as e:
            self.logger.error(
                f"Error calculating opinion updates for agent {agent_id}: {e}",
                extra={"extra_data": {"error": str(e), "agent_id": agent_id}},
            )
            return None

    def _calculate_bounded_confidence(
        self,
        agent_opinion: Optional[float],
        author_opinion: float,
        params: dict,
    ) -> float:
        """
        Calculate opinion update using bounded confidence model.

        Args:
            agent_opinion: Agent's current opinion (None for cold start)
            author_opinion: Author's opinion
            params: Model parameters (epsilon, mu, theta, cold_start)

        Returns:
            float: Updated opinion value
        """
        return bounded_confidence(
            x=agent_opinion,
            y=author_opinion,
            epsilon=params.get("epsilon", 0.25),
            mu=params.get("mu", 0.5),
            theta=params.get("theta", 0.0),
            cold_start=params.get("cold_start", "neutral"),
        )

    def _calculate_llm_evaluation(
        self,
        agent_id: str,
        agent_opinion: Optional[float],
        author_opinion: float,
        post_content: str,
        topic_id: str,
        topic_name: str,
        params: dict,
    ) -> float:
        """
        Calculate opinion update using LLM evaluation model.

        Args:
            agent_id: Agent UUID
            agent_opinion: Agent's current opinion (None for cold start)
            author_opinion: Author's opinion
            post_content: Post text content
            topic_id: Topic ID
            topic_name: Topic name
            params: Model parameters (evaluation_scope, cold_start)

        Returns:
            float: Updated opinion value
        """
        # Get evaluation scope and prepare neighbors' opinions if needed
        evaluation_scope = params.get("evaluation_scope", "interlocutor_only")
        peers_opinions = None

        if evaluation_scope == "neighbors":
            # Get neighbors' opinions from server
                neighbor_opinion_values = ray.get(
                    self.server.get_neighbors_opinions.remote(
                        agent_id, topic_id, client_id=self.client_id
                    )
                )

                if neighbor_opinion_values:
                    # Convert to opinion labels and count occurrences
                    opinion_groups = self.opinion_config.get("opinion_groups", {})
                    neighbor_labels = [
                        get_opinion_group(val, opinion_groups) for val in neighbor_opinion_values
                    ]
                    peers_opinions = list(Counter(neighbor_labels).items())

        # Calculate new opinion using LLM evaluation
        return llm_evaluation(
            x=agent_opinion,
            y=author_opinion,
            text=post_content,
            topic=topic_name,
            author_name=parent_post_data.get("username") or parent_author_id,
            evaluation_scope=evaluation_scope,
            cold_start=params.get("cold_start", "neutral"),
            group_classes=self.opinion_config.get("opinion_groups", {}),
            peers_opinions=peers_opinions,
            llm_manager=self.llm_manager,
            agent_id=agent_id,
        )

    def _transition_from_scores(self, source_score: Optional[float], target_score: Optional[float]) -> str:
        if source_score is None or target_score is None:
            return "cold_start"
        if target_score > source_score:
            return "agree"
        if target_score < source_score:
            return "disagree"
        return "neutral"

    def _transition_direction(self, source_score: Optional[float], target_score: Optional[float]) -> Optional[str]:
        if source_score is None or target_score is None:
            return None
        if target_score > source_score:
            return "toward"
        if target_score < source_score:
            return "away"
        return "stay"
