"""
Interest Manager

Handles all interest tracking, topic management, and sliding window attention mechanism
for agent interest modeling in YSimulator.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from YPhotoSharing.YServer.classes.models import Interest


class InterestManager:
    """
    Manages agent interests with sliding window attention mechanism.

    This class handles:
    - Interest validation and extraction
    - Topic-to-ID mapping
    - Sliding window recomputation (forgetting mechanism)
    - Article topic storage
    - Agent interest state management
    """

    def __init__(self, db_service: Any, attention_window: int = 336):
        """
        Initialize the Interest Manager.

        Args:
            db_service: Database service adapter or middleware instance for database operations
            attention_window: Number of rounds to consider for interest decay (default: 336 = 14 days)
        """
        self.db = db_service
        self.attention_window = attention_window
        self.logger = logging.getLogger(__name__)

        # Agent interests tracking - maintain in-memory state
        # Format: {agent_id: {"topics": [topic_names], "counts": [interaction_counts]}}
        self.agent_interests = {}

        # Current round ID for windowing calculations
        self.current_round_id = None

    def set_current_round(self, round_id: str):
        """
        Set the current round ID for temporal windowing.

        Args:
            round_id: Current round UUID
        """
        self.current_round_id = round_id

    def validate_and_extract_interests(
        self, interests
    ) -> Tuple[Optional[List[str]], Optional[List[int]]]:
        """
        Validate interests structure and extract topics and counts.

        Args:
            interests: Interest data in format [["Topic1", "Topic2"], [1, 2]]
                      Can also accept [["Topic1", "Topic2"], 1] - single count for all topics

        Returns:
            tuple: (topics, counts) or (None, None) if invalid
        """
        if not interests or not isinstance(interests, (list, tuple)) or len(interests) != 2:
            return None, None

        topics = interests[0]
        counts = interests[1]

        # Validate topics is a list
        if not topics or not isinstance(topics, list):
            return None, None

        if len(topics) == 0:
            return None, None

        # Handle counts as either a list or a single integer
        if isinstance(counts, int):
            # Single count for all topics - expand to list
            counts = [counts] * len(topics)
        elif isinstance(counts, list):
            # Counts is already a list - validate it
            if len(counts) == 0:
                return None, None
            # Validate counts list length matches topics length
            if len(counts) != len(topics):
                return None, None
        else:
            # Counts is neither int nor list - invalid
            return None, None

        return topics, counts

    def get_topic_name_from_id(self, topic_id: str) -> Optional[str]:
        """
        Get topic name from topic UUID.

        Args:
            topic_id: Topic UUID (iid)

        Returns:
            str: Topic name or None if not found
        """
        session = Session(self.db.engine)
        try:
            interest = session.query(Interest).filter(Interest.iid == topic_id).first()
            if interest:
                return interest.interest
            return None
        finally:
            session.close()

    def recompute_agent_interests_from_window(self, agent_id: str):
        """
        Recompute agent interests based on the sliding attention window.
        This replaces the incremental counter approach with a query-based approach.

        Args:
            agent_id: Agent UUID
        """
        agent_id = str(agent_id)

        if not self.current_round_id:
            self.logger.warning(
                f"Cannot recompute interests for agent {agent_id}: current_round_id not set"
            )
            return

        # Get interest counts within the attention window
        interest_counts_by_id = self.db.compute_interest_counts_in_window(
            agent_id, self.current_round_id, self.attention_window
        )

        # Convert interest IDs to names
        topics = []
        counts = []

        for interest_id, count in interest_counts_by_id.items():
            if count > 0:  # Only include topics with count > 0
                topic_name = self.get_topic_name_from_id(interest_id)
                if topic_name:
                    topics.append(topic_name)
                    counts.append(count)

        # Update in-memory state
        if topics:
            self.agent_interests[agent_id] = {"topics": topics, "counts": counts}
        elif agent_id in self.agent_interests:
            # Remove agent from interests if no topics remain
            del self.agent_interests[agent_id]

    def update_agent_interest_counter(self, agent_id: str, topic_name: str, increment: int = 1):
        """
        DEPRECATED: This method is replaced by recompute_agent_interests_from_window.
        Kept for backward compatibility during transition.

        Update the interest counter for an agent in memory.

        Args:
            agent_id: Agent UUID
            topic_name: Name of the topic
            increment: Amount to increment the counter (default: 1)
        """
        # Now we just recompute from the database instead of incrementing
        self.recompute_agent_interests_from_window(agent_id)

    def recompute_all_agent_interests(self, agent_ids: List[str]):
        """
        Recompute interests for all registered agents based on the sliding attention window.
        This implements the forgetting mechanism - as user_interest entries fall outside
        the attention window, their counts decrease and topics with count 0 are removed.

        Args:
            agent_ids: List of agent IDs to recompute interests for
        """
        self.logger.info(
            f"Recomputing interests for {len(agent_ids)}agents using attention window of {self.attention_window}rounds"
        )

        for agent_id in agent_ids:
            self.recompute_agent_interests_from_window(agent_id)

        # Log summary
        agents_with_interests = len(self.agent_interests)
        total_topics = sum(len(data["topics"]) for data in self.agent_interests.values())
        self.logger.info(
            f"Interest recomputation complete: {agents_with_interests} agents have interests, "
            f"{total_topics} total topics"
        )

    def get_agent_interests(self) -> Dict[str, Dict[str, list]]:
        """
        Get the current agent interests dictionary.

        Returns:
            Dict: agent_interests dictionary with format {agent_id: {"topics": [...], "counts": [...]}}
        """
        return dict(self.agent_interests)

    def set_agent_interests(self, agent_id: str, topics: List[str], counts: List[int]):
        """
        Set interests for a specific agent in memory.

        Args:
            agent_id: Agent UUID
            topics: List of topic names
            counts: List of interaction counts
        """
        if topics and counts:
            self.agent_interests[str(agent_id)] = {"topics": list(topics), "counts": list(counts)}

    def get_photo_topics(self, photo_id: str) -> List[str]:
        """
        Get topic IDs for a photo.

        Args:
            photo_id: Photo UUID

        Returns:
            List[str]: List of topic IDs (uuids)
        """
        return self.db.get_photo_topics(photo_id)

    def extract_and_store_topics(self, photo_id: str, payload: Dict[str, Any]) -> List[str]:
        """
        Extract topics from a photo payload and store them in the database.

        Args:
            photo_id: The ID of the photo
            payload: The content payload from the LLM or client

        Returns:
            List of extracted topic names
        """
        # Try to get existing topics first (in case we're reprocessing)
        existing_topics = self.db.get_photo_topics(photo_id)
        if existing_topics:
            return existing_topics

        # Get the photo to analyze its content
        photo_data = self.db.get_photo(photo_id)
        if not photo_data:
            self.logger.warning(f"Photo {photo_id} not found in database, cannot store topics")
            return []

        # Assuming the payload contains a 'topics' key
        topic_names = payload.get("topics", [])
        topic_ids = []
        for topic_name in topic_names:
            # Add or get topic in interests table
            topic_id = self.db.add_or_get_interest(topic_name)
            self.logger.info(f"Interest topic_id for '{topic_name}': {topic_id}")

            if topic_id:
                # Add to photo_topics table
                success = self.db.add_photo_topic(photo_id, topic_id)
                self.logger.info(f"add_photo_topic({photo_id}, {topic_id}) returned: {success}")

                if success:
                    topic_ids.append(topic_id)
                    self.logger.info(
                        f"Successfully added topic '{topic_name}' (ID: {topic_id}) to photo {photo_id}"
                    )
                else:
                    self.logger.error(f"Failed to add topic '{topic_name}' to photo {photo_id}")

        self.logger.info(f"Final topic_ids for photo {photo_id}: {topic_ids}")
        return topic_ids

    def initialize_agent_interests(self, agent_id: str, interests, round_id: str) -> bool:
        """
        Initialize agent interests during registration.
        Validates, stores in memory, and persists to database.

        Args:
            agent_id: Agent UUID
            interests: Interest data in format [["Topic1", "Topic2"], [1, 2]]
            round_id: Current round UUID

        Returns:
            bool: True if interests were initialized successfully
        """
        topics, counts = self.validate_and_extract_interests(interests)
        if not topics or not counts:
            return False

        # Store in memory
        self.set_agent_interests(agent_id, topics, counts)

        # Save to database
        # Note: We create multiple user_interest entries (one per interaction count)
        # This maintains temporal granularity - each entry represents an interaction.
        # The sliding window mechanism will naturally handle interest decay.
        # Multiple entries for the same topic preserve interaction frequency in the
        # user_interest table, which tracks interests per round for temporal analysis.
        for i, topic in enumerate(topics):
            # Get or create the interest in the interests table
            interest_id = self.db.add_or_get_interest(topic)
            if interest_id:
                # Add user_interest entries based on interaction count
                count = counts[i] if i < len(counts) else 1
                for _ in range(count):
                    self.db.add_user_interest(
                        user_id=agent_id, interest_id=interest_id, round_id=round_id
                    )

        return True

    def initialize_agent_interests_batch(
        self, agents_interests_data: List[Dict], round_id: str
    ) -> Dict[str, bool]:
        """
        Initialize interests for multiple agents in batch for improved performance.

        This method is optimized for bulk insertion during agent registration.
        It processes all agents' interests together using batch database operations.

        Args:
            agents_interests_data: List of dicts with keys:
                - agent_id: Agent UUID
                - interests: Interest data in format [["Topic1", "Topic2"], [1, 2]]
            round_id: Current round UUID

        Returns:
            Dict mapping agent_id to success status (True/False)
        """
        results = {}

        # Validate and prepare data
        valid_agents = []
        for agent_data in agents_interests_data:
            agent_id = agent_data.get("agent_id")
            interests = agent_data.get("interests")

            topics, counts = self.validate_and_extract_interests(interests)
            if not topics or not counts:
                results[agent_id] = False
                continue

            # Store in memory
            self.set_agent_interests(agent_id, topics, counts)

            valid_agents.append({"agent_id": agent_id, "topics": topics, "counts": counts})
            results[agent_id] = True

        if not valid_agents:
            return results

        # Collect all unique topic names
        all_topic_names = set()
        for agent_data in valid_agents:
            all_topic_names.update(agent_data["topics"])

        # Batch get or create all interests
        topic_name_to_id = self.db.add_or_get_interests_batch(list(all_topic_names))

        if not topic_name_to_id:
            # If batch operation failed, mark all as failed
            for agent_data in valid_agents:
                results[agent_data["agent_id"]] = False
            return results

        # Prepare user_interest entries for all agents
        user_interests_data = []
        for agent_data in valid_agents:
            agent_id = agent_data["agent_id"]
            topics = agent_data["topics"]
            counts = agent_data["counts"]

            for i, topic in enumerate(topics):
                interest_id = topic_name_to_id.get(topic)
                if interest_id:
                    # Add multiple entries based on interaction count
                    count = counts[i] if i < len(counts) else 1
                    for _ in range(count):
                        user_interests_data.append(
                            {
                                "user_id": agent_id,
                                "interest_id": interest_id,
                                "round_id": round_id,
                            }
                        )

        # Batch insert all user_interest entries
        if user_interests_data:
            added_count = self.db.add_user_interests_batch(user_interests_data)
            self.logger.info(
                f"Batch initialized {added_count} user interest entries for "
                f"{len(valid_agents)} agents"
            )

        return results
