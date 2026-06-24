"""
Story watching action for YPhotoSharing agents.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

async def watch_story(
    server,
    user_id: str,
    round_id: str,
) -> Optional[dict]:
    """
    Fetch a recent story from followed users and watch it.
    """
    try:
        # Get recent stories
        stories = await server.get_recent_stories.remote(user_id, limit=10)
        if not stories:
            return None
            
        import random
        target_story = random.choice(stories)
        
        success = await server.view_story.remote(target_story["id"], user_id)
        if success:
            logger.debug(f"User {user_id} watched story {target_story['id']} by {target_story['user_id']}")
            return {"story_id": target_story["id"], "author_id": target_story["user_id"]}
        return None
    except Exception as exc:
        logger.error(f"Failed to watch story for user {user_id}: {exc}")
        return None
