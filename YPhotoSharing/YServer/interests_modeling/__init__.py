"""
Interest Modeling Module

This module provides interest tracking and management functionality for agents,
including sliding window attention mechanism for realistic interest forgetting.
"""

from .interest_manager import InterestManager

__all__ = ["InterestManager"]
