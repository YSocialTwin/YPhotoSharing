"""
Client lifecycle manager for the orchestrator.

Handles client registration, completion tracking, heartbeats, and stale client detection.
"""

import logging
import time
from typing import Dict, Optional, Set


class ClientManager:
    """
    Manages client lifecycle and tracking for the simulation orchestrator.

    Handles client registration, completion, heartbeat tracking, and stale
    client detection to ensure proper synchronization.
    """

    def __init__(self, timeout_seconds: int, logger: Optional[logging.Logger] = None):
        """
        Initialize client manager.

        Args:
            timeout_seconds: Seconds before a client is considered stale
            logger: Logger instance
        """
        self.timeout_seconds = timeout_seconds
        self.logger = logger or logging.getLogger(__name__)

        # Client tracking
        self.registered_clients: Set[str] = set()
        self.completed_clients: Set[str] = set()
        self.submitted_clients: Set[str] = set()
        self.last_heartbeat: Dict[str, float] = {}

    def register_client(
        self, client_id: str, num_days: int, current_day: int, current_slot: int
    ) -> dict:
        """
        Register a new client with the server.

        If a client was previously completed, it will be re-registered and removed
        from the completed clients list, allowing it to run again.

        Args:
            client_id: Unique identifier for the client
            num_days: Number of days this client plans to simulate
            current_day: Current simulation day
            current_slot: Current simulation slot

        Returns:
            dict: {"registered": bool, "start_day": int, "start_slot": int}
        """
        start_time = time.time()

        # If this client was previously completed, remove it from completed set
        was_completed = client_id in self.completed_clients
        if was_completed:
            self.completed_clients.remove(client_id)
            self.logger.info(f"Re-registering previously completed client {client_id}")

        if client_id not in self.registered_clients:
            self.registered_clients.add(client_id)
            self.last_heartbeat[client_id] = time.time()

            execution_time = (time.time() - start_time) * 1000

            self.logger.info(
                "Client registered",
                extra={
                    "extra_data": {
                        "client_id": client_id,
                        "start_day": current_day,
                        "start_slot": current_slot,
                        "num_days": num_days,
                        "total_clients": len(self.registered_clients),
                        "active_clients": len(self.get_active_clients()),
                        "execution_time_ms": execution_time,
                        "was_completed": was_completed,
                    }
                },
            )
            self.logger.info(
                f"[Server] 🟢 Client {client_id} joined at day {current_day}, slot {current_slot}. "
                f"Will run for {num_days if num_days > 0 else '∞'} days. "
                f"Total: {len(self.registered_clients)}, Active: {len(self.get_active_clients())}"
            )
        else:
            # Client already registered, just update heartbeat
            self.last_heartbeat[client_id] = time.time()

        return {
            "registered": True,
            "start_day": current_day,
            "start_slot": current_slot,
        }

    def complete_client(self, client_id: str) -> bool:
        """
        Mark a client as completed (finished all planned activities).

        Completed clients no longer block barrier advancement.

        Args:
            client_id: Unique identifier for the client

        Returns:
            bool: True if successfully marked as complete
        """
        if client_id in self.registered_clients:
            self.mark_as_completed(client_id)

            self.logger.info(
                "Client completed all activities",
                extra={
                    "extra_data": {
                        "client_id": client_id,
                        "remaining_active": len(self.get_active_clients()),
                        "total_completed": len(self.completed_clients),
                    }
                },
            )
            self.logger.info(
                f"[Server] 🏁 Client {client_id} completed. "
                f"Active: {len(self.get_active_clients())}, "
                f"Completed: {len(self.completed_clients)}"
            )
        return True

    def heartbeat(self, client_id: str) -> bool:
        """
        Record a heartbeat from a client to indicate it's still alive.

        Args:
            client_id: Unique identifier for the client

        Returns:
            bool: True if heartbeat recorded, False if client not registered
        """
        if client_id in self.registered_clients:
            self.last_heartbeat[client_id] = time.time()
            return True
        return False

    def deregister_client(self, client_id: str) -> bool:
        """
        Remove a client from the server.

        Args:
            client_id: Unique identifier for the client

        Returns:
            bool: True if deregistration successful
        """
        if client_id in self.registered_clients:
            self.registered_clients.remove(client_id)
            # Clean up all tracking data for this client
            self.submitted_clients.discard(client_id)
            self.completed_clients.discard(client_id)
            self.last_heartbeat.pop(client_id, None)

            self.logger.info(
                "Client deregistered",
                extra={
                    "extra_data": {
                        "client_id": client_id,
                        "remaining_clients": len(self.registered_clients),
                    }
                },
            )
            self.logger.info(f"Client {client_id} left. Total: {len(self.registered_clients)}")
        return True

    def get_active_clients(self) -> Set[str]:
        """
        Get the set of active clients (registered but not completed).

        Returns:
            set: Set of active client IDs
        """
        return self.registered_clients - self.completed_clients

    def mark_as_completed(self, client_id: str) -> None:
        """
        Mark a client as completed internally.

        Args:
            client_id: Unique identifier for the client
        """
        self.completed_clients.add(client_id)
        self.submitted_clients.discard(client_id)

    def check_for_stale_clients(self) -> None:
        """
        Check for clients that haven't sent a heartbeat recently and remove them.

        Heartbeat-based liveness: Clients are only considered stale if they stop
        sending heartbeats.
        """
        current_time = time.time()
        stale_clients = []
        stale_clients_info = {}

        for client_id in self.get_active_clients():
            # Check if heartbeat was ever received
            if client_id not in self.last_heartbeat:
                self.logger.warning(
                    f"Active client {client_id} has no heartbeat entry, initializing",
                    extra={"extra_data": {"client_id": client_id}},
                )
                self.last_heartbeat[client_id] = current_time
                continue

            last_hb = self.last_heartbeat[client_id]
            time_since_heartbeat = current_time - last_hb

            if time_since_heartbeat > self.timeout_seconds:
                stale_clients.append(client_id)
                stale_clients_info[client_id] = time_since_heartbeat

        for client_id in stale_clients:
            time_since_heartbeat = stale_clients_info[client_id]
            self.logger.warning(
                "Removing stale client (no heartbeat)",
                extra={
                    "extra_data": {
                        "client_id": client_id,
                        "timeout_seconds": self.timeout_seconds,
                        "last_heartbeat_ago": time_since_heartbeat,
                    }
                },
            )
            self.logger.info(
                f"[Server] ⚠️  Removing stale client {client_id} "
                f"(no heartbeat for {time_since_heartbeat:.1f}s)"
            )
            self.mark_as_completed(client_id)

    def mark_client_submitted(self, client_id: str) -> None:
        """
        Mark that a client has submitted actions for the current round.

        Args:
            client_id: Unique identifier for the client
        """
        self.submitted_clients.add(client_id)

    def clear_submitted_clients(self) -> None:
        """Clear the submitted clients set for the next round."""
        self.submitted_clients.clear()
