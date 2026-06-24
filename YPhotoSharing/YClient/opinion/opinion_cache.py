"""
Opinion Cache for YPhotoSharing.

This module provides caching for opinion state to improve performance.
"""

from typing import Any, Dict, Optional


class OpinionCache:
    """
    Cache for opinion state to improve performance.

    This class provides caching for frequently accessed opinion data:
    - Agent opinions
    - Topic mappings
    - Opinion group classifications

    The cache can be extended in the future to include:
    - Recent opinion updates
    - Frequently queried opinions
    - Opinion update history
    """

    def __init__(self, logger: Any):
        """
        Initialize the opinion cache.

        Args:
            logger: Logger instance
        """
        self.logger = logger

        # Initialize cache structures
        self._agent_opinions: Dict[str, Dict[str, float]] = {}
        self._topic_names: Dict[str, str] = {}
        self._opinion_groups: Dict[float, str] = {}

    def get_agent_opinion(self, agent_id: str, topic_id: str) -> Optional[float]:
        """
        Get cached agent opinion for a topic.

        Args:
            agent_id: Agent UUID
            topic_id: Topic ID

        Returns:
            Optional[float]: Cached opinion value, or None if not cached
        """
        if agent_id in self._agent_opinions:
            return self._agent_opinions[agent_id].get(topic_id)
        return None

    def set_agent_opinion(self, agent_id: str, topic_id: str, opinion: float) -> None:
        """
        Cache agent opinion for a topic.

        Args:
            agent_id: Agent UUID
            topic_id: Topic ID
            opinion: Opinion value to cache
        """
        if agent_id not in self._agent_opinions:
            self._agent_opinions[agent_id] = {}
        self._agent_opinions[agent_id][topic_id] = opinion

    def get_topic_name(self, topic_id: str) -> Optional[str]:
        """
        Get cached topic name.

        Args:
            topic_id: Topic ID

        Returns:
            Optional[str]: Cached topic name, or None if not cached
        """
        return self._topic_names.get(topic_id)

    def set_topic_name(self, topic_id: str, topic_name: str) -> None:
        """
        Cache topic name.

        Args:
            topic_id: Topic ID
            topic_name: Topic name to cache
        """
        self._topic_names[topic_id] = topic_name

    def get_opinion_group(self, opinion: float) -> Optional[str]:
        """
        Get cached opinion group label.

        Args:
            opinion: Opinion value

        Returns:
            Optional[str]: Cached opinion group label, or None if not cached
        """
        return self._opinion_groups.get(opinion)

    def set_opinion_group(self, opinion: float, group: str) -> None:
        """
        Cache opinion group label.

        Args:
            opinion: Opinion value
            group: Opinion group label to cache
        """
        self._opinion_groups[opinion] = group

    def clear(self) -> None:
        """Clear all cached data."""
        self._agent_opinions.clear()
        self._topic_names.clear()
        self._opinion_groups.clear()
        self.logger.debug("Opinion cache cleared")

    def clear_agent(self, agent_id: str) -> None:
        """
        Clear cached data for a specific agent.

        Args:
            agent_id: Agent UUID
        """
        if agent_id in self._agent_opinions:
            del self._agent_opinions[agent_id]
            self.logger.debug(f"Opinion cache cleared for agent {agent_id}")

    def get_stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dict[str, int]: Cache statistics including size of each cache
        """
        return {
            "agent_opinions_count": len(self._agent_opinions),
            "topic_names_count": len(self._topic_names),
            "opinion_groups_count": len(self._opinion_groups),
        }
