import logging

logger = logging.getLogger(__name__)

async def unfollow_user(
    server,
    follower_id: str,
    user_id: str,
    round_id: str
) -> bool:
    """
    Remove an existing follow edge.
    """
    try:
        await server.unfollow_user.remote(follower_id, user_id, round_id)
        logger.debug(f"User {follower_id} unfollowed {user_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to unfollow {user_id} for user {follower_id}: {exc}")
        return False
