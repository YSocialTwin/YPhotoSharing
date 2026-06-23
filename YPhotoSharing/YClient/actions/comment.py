"""
Comment action for YPhotoSharing agents.

Agents call post_comment() to leave a comment on a photo.
The LLM generates the comment text; the server persists it.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def post_comment(
    server,
    llm_service,
    user_id: str,
    photo: dict,
    round_id: str,
    cluster_id: int = 0,
    parent_comment_id: Optional[str] = None,
    agent_attrs: Optional[dict] = None,
) -> Optional[str]:
    """
    Generate and persist a comment on *photo*.

    Args:
        server: Ray handle to OrchestratorServer
        llm_service: Ray handle to an LLM service actor
        user_id: UUID of the commenting user
        photo: Photo dict (must include 'id', 'caption', optionally 'username')
        round_id: Current simulation round UUID
        cluster_id: Agent persona cluster
        parent_comment_id: UUID of parent comment for threaded replies
        agent_attrs: Extra agent attributes forwarded to the LLM

    Returns:
        UUID of the created comment, or None on failure
    """
    caption = photo.get("caption", "")
    photo_id = photo.get("id", "")
    author = photo.get("username", "user")
    image_url = photo.get("media_url") or photo.get("image_url")

    try:
        body = await llm_service.generate_comment.remote(
            caption=caption,
            author=author,
            cluster_id=cluster_id,
            agent_attrs=agent_attrs,
            image_url=image_url,
        )
    except Exception as exc:
        logger.warning(f"Comment generation failed for user {user_id}: {exc}")
        return None

    if not body or not body.strip():
        return None

    try:
        comment_id = await server.post_comment.remote(
            user_id=user_id,
            photo_id=photo_id,
            body=body.strip(),
            round_id=round_id,
            parent_comment_id=parent_comment_id,
        )
        logger.debug(f"User {user_id} commented on photo {photo_id}")
        return comment_id
    except Exception as exc:
        logger.error(f"Failed to persist comment for user {user_id}: {exc}")
        return None
