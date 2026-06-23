import logging

logger = logging.getLogger(__name__)

async def request_follow(
    server,
    follower_id: str,
    user_id: str,
    round_id: str
) -> bool:
    """
    Attempt to follow a user. If the user is private, it sends a follow request instead.
    """
    try:
        # Check if user is private
        user_data = await server.get_user.remote(user_id)
        if not user_data:
            return False
            
        if user_data.get("is_private"):
            await server.add_follow_request.remote(follower_id, user_id)
            logger.debug(f"User {follower_id} requested to follow private user {user_id}")
        else:
            await server.follow_user.remote(follower_id, user_id, round_id)
            logger.debug(f"User {follower_id} followed {user_id}")
            
        return True
    except Exception as exc:
        logger.error(f"Failed follow action for {follower_id} to {user_id}: {exc}")
        return False
