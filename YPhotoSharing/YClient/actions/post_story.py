"""
Story posting action for YPhotoSharing agents.
"""

import logging
import uuid
from typing import Any, Dict, Optional

from YPhotoSharing.YClient.actions.rule_based_actions import generate_rule_based_story

logger = logging.getLogger(__name__)

async def post_story(
    server,
    llm_service,
    user_id: str,
    cluster_id: int,
    round_id: str,
    day: int,
    slot: int,
    topic: str = "general",
    agent_attrs: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Generate a short ephemeral story with the LLM and persist via the server.
    """
    try:
        if agent_attrs and not agent_attrs.get("llm", True):
            content = generate_rule_based_story(
                topic=topic,
                username=agent_attrs.get("username", user_id),
                cluster_id=cluster_id,
            )
        else:
            content = await llm_service.generate_caption.remote(
                topic=topic,
                day=day,
                slot=slot,
                cluster_id=cluster_id,
                agent_attrs=agent_attrs,
            )
    except Exception as exc:
        logger.warning(f"Story generation failed for user {user_id}: {exc}")
        content = f"Feeling {topic} today! #story"

    story_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "round": round_id,
        "media_url": f"https://placeholder.stories/{uuid.uuid4().hex[:8]}",
        "caption": content[:100], # stories have shorter text
    }

    try:
        story_id = await server.post_story.remote(story_data)
        logger.debug(f"User {user_id} posted story {story_id}")
        return story_id
    except Exception as exc:
        logger.error(f"Failed to persist story for user {user_id}: {exc}")
        return None
