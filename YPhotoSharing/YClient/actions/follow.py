"""
Follow action for YPhotoSharing agents.

Agents call follow_user() to follow or unfollow another user.
The LLM decides whether to follow; the server records the relationship.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def follow_user(
    server,
    llm_service,
    follower_id: str,
    target_user: dict,
    round_id: str,
    cluster_id: int = 0,
) -> Optional[str]:
    """
    Decide whether to follow *target_user* and persist if positive.

    Args:
        server: Ray handle to OrchestratorServer
        llm_service: Ray handle to an LLM service actor
        follower_id: UUID of the following agent
        target_user: User dict (must include 'id', 'username'; optionally 'bio', 'topics')
        round_id: Current simulation round UUID
        cluster_id: Agent persona cluster

    Returns:
        'FOLLOW' if followed, 'SKIP' otherwise
    """
    target_id = target_user.get("id", "")
    username = target_user.get("username", "user")
    bio = target_user.get("bio", "")
    topics = target_user.get("topics", "")

    try:
        decision = await llm_service.decide_follow.remote(
            username=username,
            bio=bio,
            topics=topics,
            cluster_id=cluster_id,
        )
    except Exception as exc:
        logger.warning(f"Follow decision failed for user {follower_id}: {exc}")
        decision = "SKIP"

    if decision == "FOLLOW":
        try:
            await server.follow_user.remote(
                follower_id=follower_id,
                user_id=target_id,
                round_id=round_id,
            )
            logger.debug(f"User {follower_id} followed {target_id}")
        except Exception as exc:
            logger.error(f"Failed to persist follow for user {follower_id}: {exc}")

    return decision
