import logging

logger = logging.getLogger(__name__)

async def save_photo(
    server,
    user_id: str,
    photo_id: str
) -> bool:
    """
    Saves a photo to the user's bookmarks.
    """
    try:
        await server.save_photo.remote(user_id, photo_id)
        logger.debug(f"User {user_id} saved photo {photo_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to save photo {photo_id} for user {user_id}: {exc}")
        return False
