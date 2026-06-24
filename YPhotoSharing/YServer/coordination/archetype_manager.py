"""
Archetype transition manager for the orchestrator.

Handles periodic archetype transitions based on probability matrices.
"""

import logging
import random
import time
from typing import Dict, Optional


class ArchetypeManager:
    """
    Manages archetype transitions for agents in the simulation.

    Performs periodic transitions based on configured probability matrices.
    """

    # Tolerance for probability sum validation
    PROBABILITY_TOLERANCE = 0.01

    def __init__(
        self,
        db_adapter,
        archetypes_enabled: bool,
        archetype_transitions: Optional[Dict] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize archetype manager.

        Args:
            db_adapter: Database adapter
            archetypes_enabled: Whether archetype transitions are enabled
            archetype_transitions: Dict mapping archetype to transition probabilities
            logger: Logger instance
        """
        self.db = db_adapter
        self.archetypes_enabled = archetypes_enabled
        self.archetype_transitions = archetype_transitions or {}
        self.logger = logger or logging.getLogger(__name__)

        # Track last transition day
        self.last_transition_day = 0

    def should_perform_transitions(self, current_day: int, transition_interval: int = 7) -> bool:
        """
        Check if it's time to perform archetype transitions.

        Args:
            current_day: Current simulation day
            transition_interval: Days between transitions (default: 7)

        Returns:
            bool: True if transitions should be performed
        """
        if not self.archetypes_enabled:
            return False

        if current_day - self.last_transition_day >= transition_interval:
            return True

        return False

    def perform_transitions(self, current_day: int) -> dict:
        """
        Perform archetype transitions for all registered agents.

        Each agent has a probability of transitioning to a different archetype
        based on the transition matrix.

        Args:
            current_day: Current simulation day

        Returns:
            dict: {"transitioned_count": int, "error_count": int, "total_agents": int}
        """
        if not self.archetypes_enabled or not self.archetype_transitions:
            return {"transitioned_count": 0, "error_count": 0, "total_agents": 0}

        transition_start = time.time()
        transitioned_count = 0
        error_count = 0

        try:
            # Get all registered agents from database
            agents = self.db.get_all_users()

            for agent in agents:
                agent_id = agent.get("id")
                current_archetype = agent.get("archetype")

                # Skip if agent has no archetype
                if not current_archetype:
                    continue

                # Normalize archetype to lowercase for comparison
                current_archetype_lower = current_archetype.lower()

                # Skip if archetype not in transitions
                if current_archetype_lower not in self.archetype_transitions:
                    continue

                # Get transition probabilities for current archetype
                transitions = self.archetype_transitions.get(current_archetype_lower, {})

                if not transitions:
                    continue

                # Sample new archetype based on transition probabilities
                archetypes = list(transitions.keys())
                probabilities = list(transitions.values())

                # Validate probabilities sum to approximately 1.0
                total_prob = sum(probabilities)
                if abs(total_prob - 1.0) > self.PROBABILITY_TOLERANCE:
                    self.logger.warning(
                        f"Archetype transition probabilities for '{current_archetype}' "
                        f"sum to {total_prob}, expected 1.0"
                    )
                    # Normalize probabilities
                    probabilities = [p / total_prob for p in probabilities]

                # Select new archetype using weighted random choice
                new_archetype = random.choices(archetypes, weights=probabilities)[0]

                # Update agent archetype in database if it changed
                if new_archetype != current_archetype_lower:
                    # Capitalize first letter to match format
                    new_archetype_formatted = new_archetype.capitalize()

                    if self.db.update_user_archetype(agent_id, new_archetype_formatted):
                        transitioned_count += 1
                        self.logger.debug(
                            f"Agent {agent_id} transitioned from {current_archetype} "
                            f"to {new_archetype_formatted}"
                        )
                    else:
                        error_count += 1

            # Update last transition day
            self.last_transition_day = current_day

            transition_time = (time.time() - transition_start) * 1000

            self.logger.info(
                f"Archetype transitions complete at day {current_day}",
                extra={
                    "extra_data": {
                        "day": current_day,
                        "transitioned_count": transitioned_count,
                        "error_count": error_count,
                        "total_agents": len(agents),
                        "execution_time_ms": transition_time,
                    }
                },
            )

            self.logger.info(
                f"[Server] 🔄 Archetype transitions complete - "
                f"{transitioned_count} agents changed archetypes (day {current_day})"
            )

            return {
                "transitioned_count": transitioned_count,
                "error_count": error_count,
                "total_agents": len(agents),
            }

        except Exception as e:
            self.logger.error(
                f"Error during archetype transitions: {e}", extra={"extra_data": {"error": str(e)}}
            )
            self.logger.error(f"Archetype transition error: {e}")
            return {
                "transitioned_count": 0,
                "error_count": error_count + 1,
                "total_agents": 0,
            }
