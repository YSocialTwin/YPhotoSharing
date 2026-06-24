"""
Round and time management for the orchestrator.

Handles round creation, advancement, and day/slot transitions.
"""

import logging
import time
from typing import Callable, Optional


class RoundManager:
    """
    Manages simulation rounds and time progression.

    Handles day/slot advancement, round creation, and end-of-day processing.
    """

    def __init__(
        self,
        db_adapter,
        interest_manager,
        visibility_rounds: int,
        num_slots_per_day: int = 24,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize round manager.

        Args:
            db_adapter: Database adapter
            interest_manager: Interest manager for attention window updates
            visibility_rounds: Number of rounds posts remain visible
            num_slots_per_day: Number of slots (hours) per day
            logger: Logger instance
        """
        self.db = db_adapter
        self.interest_manager = interest_manager
        self.visibility_rounds = visibility_rounds
        self.num_slots_per_day = num_slots_per_day
        self.logger = logger or logging.getLogger(__name__)

        # Current simulation state
        self.day = 1
        self.slot = 1
        self.current_round_id = None

    def initialize_first_round(self) -> str:
        """
        Initialize the first round of the simulation.

        Returns:
            str: Round ID for the first round
        """
        self.current_round_id = self.db.get_or_create_round(self.day, self.slot)
        self.interest_manager.set_current_round(self.current_round_id)
        return self.current_round_id

    def advance_simulation(self, recompute_interests_callback: Optional[Callable] = None) -> dict:
        """
        Advance simulation to the next slot/day.

        Args:
            recompute_interests_callback: Optional callback to recompute interests at day end

        Returns:
            dict: {"day": int, "slot": int, "round_id": str, "day_completed": bool}
        """
        execution_start = time.time()

        self.logger.info(f"[Server] ✅ Day {self.day} Slot {self.slot} complete. Advancing...")

        self.slot += 1
        day_completed = False

        # Check if day is complete
        if self.slot > self.num_slots_per_day:
            day_completed = True
            completed_day = self.day
            self.slot = 1
            self.day += 1

            # Consolidate Redis data to SQLite at end of day
            consolidation_result = self.db.consolidate_redis_to_sqlite(completed_day)
            if (
                consolidation_result.get("posts", 0) > 0
                or consolidation_result.get("interactions", 0) > 0
                or consolidation_result.get("removed_posts", 0) > 0
            ):
                self.logger.info(
                    f"Day {completed_day} complete - data consolidated to SQLite",
                    extra={
                        "extra_data": {
                            "completed_day": completed_day,
                            "posts_consolidated": consolidation_result.get("posts", 0),
                            "interactions_consolidated": consolidation_result.get(
                                "interactions", 0
                            ),
                            "posts_removed_from_redis": consolidation_result.get(
                                "removed_posts", 0
                            ),
                            "interactions_removed_from_redis": consolidation_result.get(
                                "removed_interactions", 0
                            ),
                        }
                    },
                )
                self.logger.info(
                    f"[Server] 💾 Day {completed_day} complete - "
                    f"Consolidated {consolidation_result.get('posts', 0)} posts, "
                    f"{consolidation_result.get('interactions', 0)} interactions to SQLite. "
                    f"Removed {consolidation_result.get('removed_posts', 0)} old posts, "
                    f"{consolidation_result.get('removed_interactions', 0)} old interactions from Redis"
                )

            # Recompute all agent interests based on sliding attention window
            if recompute_interests_callback:
                recompute_interests_callback()

            # Clean up old posts from Redis based on visibility_rounds
            cleanup_result = self.db.cleanup_old_posts_from_redis(self.day, self.slot)
            if (
                cleanup_result.get("removed_posts", 0) > 0
                or cleanup_result.get("removed_interactions", 0) > 0
            ):
                self.logger.info(
                    "Redis temporal cleanup complete - removed posts older than visibility_rounds",
                    extra={
                        "extra_data": {
                            "day": self.day,
                            "slot": self.slot,
                            "removed_posts": cleanup_result.get("removed_posts", 0),
                            "removed_interactions": cleanup_result.get("removed_interactions", 0),
                            "remaining_posts": cleanup_result.get("remaining_posts", 0),
                        }
                    },
                )
                self.logger.info(
                    f"[Server] 🧹 Redis cleanup - "
                    f"Removed {cleanup_result.get('removed_posts', 0)} old posts, "
                    f"{cleanup_result.get('removed_interactions', 0)} old interactions. "
                    f"Remaining: {cleanup_result.get('remaining_posts', 0)} posts in Redis"
                )

        # Update Round table with new time
        self.current_round_id = self.db.get_or_create_round(self.day, self.slot)
        self.interest_manager.set_current_round(self.current_round_id)

        execution_time = (time.time() - execution_start) * 1000

        self.logger.info(
            "Simulation advanced",
            extra={
                "extra_data": {
                    "new_day": self.day,
                    "new_slot": self.slot,
                    "round_id": self.current_round_id,
                    "day_completed": day_completed,
                    "execution_time_ms": execution_time,
                }
            },
        )

        return {
            "day": self.day,
            "slot": self.slot,
            "round_id": self.current_round_id,
            "day_completed": day_completed,
        }

    def get_current_state(self) -> dict:
        """
        Get current simulation state.

        Returns:
            dict: {"day": int, "slot": int, "round_id": str}
        """
        return {
            "day": self.day,
            "slot": self.slot,
            "round_id": self.current_round_id,
        }
