"""
Report action for YPhotoSharing agents.
Agents can report content they find offensive or counter to their preferences.
"""

import logging
import random
from typing import Optional

logger = logging.getLogger(__name__)

async def report_content(
    server,
    llm_service,
    user_id: str,
    round_id: str,
    agent_attrs: dict,
) -> Optional[dict]:
    """
    Decide whether to report content from the home feed.
    """
    try:
        # Get home feed
        feed = await server.get_home_feed.remote(user_id, limit=10)
        if not feed:
            return None
            
        # Select a candidate photo
        photo = random.choice(feed)
        
        # Decide without LLM for this simulation to avoid interface changes
        reply_lower = "no"
        reason = ""
        caption_lower = str(photo.get('caption', '')).lower()
        if "spam" in caption_lower or "stupid" in caption_lower:
            reply_lower = "yes"
            reason = "spam"
        elif random.random() < 0.05: # Random noise reports
            reply_lower = "yes"
            reason = "I don't like this"
            
        if reply_lower.startswith("yes"):
            # Submit report
            report_id = await server.report_content.remote(
                reporter_id=user_id,
                content_id=photo.get("id"),
                content_type="photo",
                reason=reason,
                round_id=round_id
            )
            logger.debug(f"User {user_id} reported photo {photo.get('id')} for: {reason}")
            return {"reported_photo_id": photo.get("id"), "reason": reason}
            
        return None
        
    except Exception as exc:
        logger.error(f"Failed to run report action for {user_id}: {exc}")
        return None
