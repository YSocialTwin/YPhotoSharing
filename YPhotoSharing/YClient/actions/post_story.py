"""
Story posting action for YPhotoSharing agents.
"""

import json
import logging
import uuid
from typing import Any, Dict, Optional

from YPhotoSharing.YClient.actions.rule_based_actions import (
    generate_rule_based_story_description,
    generate_rule_based_story_title,
)

logger = logging.getLogger(__name__)


def _extract_photo_url(photo: Dict[str, Any]) -> Optional[str]:
    for key in ("image_url", "media_url", "url"):
        value = photo.get(key)
        if value:
            value = str(value).strip()
            if value:
                return value
    return None


async def _load_user_photo_urls(server, user_id: str, limit: int = 12) -> list[str]:
    photos = await server.get_user_photos.remote(user_id, limit=limit, offset=0)
    urls: list[str] = []
    for photo in photos or []:
        url = _extract_photo_url(photo)
        if url and url not in urls:
            urls.append(url)
    return urls


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
    Publish a story made of already existing user images and persist via the server.
    """
    selected_image_urls: list[str] = []
    try:
        selected_image_urls = await _load_user_photo_urls(server, user_id)
        if not selected_image_urls:
            logger.warning(f"Aborting story for {user_id}: no existing photos were available.")
            return None

        image_count = min(len(selected_image_urls), 5)
        selected_image_urls = selected_image_urls[:image_count]

        if agent_attrs and not agent_attrs.get("llm", True):
            description = generate_rule_based_story_description(
                topic=topic,
                username=agent_attrs.get("username", user_id),
                image_count=image_count,
                cluster_id=cluster_id,
            )
        else:
            description = await llm_service.generate_caption.remote(
                topic=topic,
                day=day,
                slot=slot,
                cluster_id=cluster_id,
                agent_attrs=agent_attrs,
            )
            description = str(description).strip()
    except Exception as exc:
        logger.warning(f"Story generation failed for user {user_id}: {exc}")
        if not selected_image_urls:
            return None
        description = generate_rule_based_story_description(
            topic=topic,
            username=(agent_attrs or {}).get("username", user_id),
            image_count=image_count if "image_count" in locals() else 1,
            cluster_id=cluster_id,
        )
    if not selected_image_urls:
        return None

    title = generate_rule_based_story_title(
        topic=topic,
        username=(agent_attrs or {}).get("username", user_id),
        image_count=image_count,
        cluster_id=cluster_id,
    )

    story_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "round": round_id,
        "media_url": selected_image_urls[0],
        "media_type": "carousel" if image_count > 1 else "image",
        "image_urls": json.dumps(selected_image_urls),
        "title": title[:80],
        "description": description[:500],
        "caption": description[:100],
    }

    try:
        story_id = await server.post_story.remote(story_data)
        logger.debug(f"User {user_id} posted story {story_id}")
        return story_id
    except Exception as exc:
        logger.error(f"Failed to persist story for user {user_id}: {exc}")
        return None
