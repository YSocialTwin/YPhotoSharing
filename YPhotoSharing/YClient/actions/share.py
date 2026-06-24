"""
Share (repost) action for YPhotoSharing agents.

Agents call share_photo() to repost an existing photo to their own followers.
"""

import logging
import random
import uuid
from typing import Optional

from YPhotoSharing.YClient.actions.dynamics_helpers import (
    build_stress_reward_variations,
    persist_stress_reward_variations,
)

logger = logging.getLogger(__name__)


async def share_photo(
    server,
    user_id: str,
    round_id: str,
    stress_reward_system=None,
    stress_reward_enabled: bool = False,
    stress_reward_backward_rounds: int = 24,
) -> Optional[dict]:
    """
    Share a recommended photo.
    
    Args:
        server: Ray handle to OrchestratorServer
        user_id: UUID of the sharing user
        round_id: Current simulation round UUID
        
    Returns:
        Dict with details of the share, or None on failure
    """
    try:
        # Get recommended photos
        recommended_ids = await server.get_recommendation.remote(user_id, round_id)
        if not recommended_ids:
            return None
            
        # Select a photo to share (bias towards the top)
        weights = [1.0 / (i + 1) for i in range(len(recommended_ids))]
        photo_id = random.choices(recommended_ids, weights=weights, k=1)[0]
        
        # We need the parent photo's details to repost it
        parent_photo = await server.get_photo.remote(photo_id)
        if not parent_photo:
            return None

        parent_topic_ids = []
        try:
            parent_topic_ids = await server.get_photo_topics.remote(photo_id)
        except Exception:
            parent_topic_ids = []
            
        photo_data = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "round": round_id,
            "image_url": parent_photo.get("image_url"),
            "caption": f"Shared from {parent_photo.get('user_id')}",
            "parent_photo_id": photo_id,
            "filter_name": parent_photo.get("filter_name"),
            "location_name": parent_photo.get("location_name"),
            "topic_ids": parent_topic_ids,
        }
        
        new_photo_id = await server.post_photo.remote(photo_data)

        if (
            stress_reward_enabled
            and stress_reward_system
            and parent_photo.get("user_id")
            and parent_photo.get("user_id") != user_id
        ):
            try:
                target_state = stress_reward_system.compute_current_stress_reward(
                    server=server,
                    agent_id=str(parent_photo.get("user_id")),
                    current_tid=str(round_id),
                    backward_rounds=stress_reward_backward_rounds,
                )
                deltas = stress_reward_system.compute_share_delta(
                    tone="positive",
                    current_stress=target_state["stress"],
                    current_reward=target_state["reward"],
                    public_exposure=1.0,
                )
                await persist_stress_reward_variations(
                    server,
                    target_user_id=str(parent_photo.get("user_id")),
                    round_id=round_id,
                    variations=build_stress_reward_variations(deltas),
                    action_name="share:positive",
                )
            except Exception as e:
                logger.warning(f"Failed to persist stress/reward for share {photo_id}: {e}")

        logger.debug(f"User {user_id} shared photo {photo_id} as {new_photo_id}")
        return {"shared_photo_id": photo_id, "new_photo_id": new_photo_id}
        
    except Exception as exc:
        logger.error(f"Failed to share photo for user {user_id}: {exc}")
        return None
