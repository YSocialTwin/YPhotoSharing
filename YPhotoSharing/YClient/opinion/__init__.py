"""
Opinion dynamics module for YPhotoSharing.

This module provides a centralized interface for managing opinion dynamics in the simulation.

Main Components:
- OpinionManager: Main interface for all opinion operations
- OpinionCalculator: Calculates opinion updates based on interactions
- OpinionInferencer: Infers opinions for page agents from articles
- OpinionCache: Caches opinion state for performance

Usage:
    from YPhotoSharing.YClient.opinion import OpinionManager

    opinion_manager = OpinionManager(
        simulation_config=config,
        server=server_handle,
        llm_manager=llm_manager,
        agent_profiles=profiles,
        client_id="client_1",
        logger=logger,
    )

    # Check if enabled
    if opinion_manager.is_enabled():
        # Calculate opinion updates
        updates = opinion_manager.calculate_opinion_updates(
            agent_id="agent_123",
            parent_post_id="post_456",
            parent_post_data=post_data,
        )
"""

from .opinion_cache import OpinionCache
from .opinion_calculator import OpinionCalculator
from .opinion_inferencer import OpinionInferencer
from .opinion_manager import OpinionManager

__all__ = [
    "OpinionManager",
    "OpinionCalculator",
    "OpinionInferencer",
    "OpinionCache",
]
