"""
Barrier synchronization handler for the orchestrator.

Manages dynamic barrier synchronization between active clients.
"""

import logging
from typing import Optional, Set


class BarrierHandler:
    """
    Handles barrier synchronization for simulation advancement.

    Implements dynamic barrier that only waits for active clients,
    not completed ones, preventing deadlocks.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initialize barrier handler.

        Args:
            logger: Logger instance
        """
        self.logger = logger or logging.getLogger(__name__)

    def check_barrier_and_should_advance(
        self, active_clients: Set[str], submitted_clients: Set[str]
    ) -> bool:
        """
        Check if all active clients have submitted and barrier should be released.

        Args:
            active_clients: Set of active client IDs
            submitted_clients: Set of clients that have submitted actions

        Returns:
            bool: True if should advance, False otherwise
        """
        active_count = len(active_clients)

        # Do not advance if no one is active
        if active_count == 0:
            return False

        # Count how many active clients have submitted
        submitted_active_clients = submitted_clients & active_clients
        active_submitted_count = len(submitted_active_clients)

        # If all active clients have submitted, advance
        if active_submitted_count >= active_count:
            self.logger.info(
                f"[Barrier] ✅ All {active_count} active clients submitted. Releasing barrier."
            )
            return True
        else:
            self.logger.debug(
                f"[Barrier] Waiting for {active_count - active_submitted_count}/{active_count}clients"
            )
            return False
