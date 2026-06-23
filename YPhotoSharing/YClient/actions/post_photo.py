"""
Photo posting action for YPhotoSharing agents.

Agents call post_photo() to publish a new image on the simulated platform.
The LLM generates the caption; the server persists the record.
"""

import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def post_photo(
    server,
    llm_service,
    user_id: str,
    cluster_id: int,
    round_id: str,
    day: int,
    slot: int,
    topic: str = "general",
    image_url: Optional[str] = None,
    filter_name: Optional[str] = None,
    location_name: Optional[str] = None,
    agent_attrs: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Generate a caption with the LLM and persist a new photo via the server.

    Args:
        server: Ray handle to OrchestratorServer
        llm_service: Ray handle to an LLM service actor
        user_id: UUID of the posting user
        cluster_id: Agent persona cluster
        round_id: Current simulation round UUID
        day: Simulation day
        slot: Hour slot within the day
        topic: Topic used to generate the caption
        image_url: URL of the photo (simulated or real)
        filter_name: Instagram-style filter name
        location_name: Optional location tag
        agent_attrs: Extra agent attributes forwarded to the LLM

    Returns:
        UUID of the created photo, or None on failure
    """
    try:
        caption = await llm_service.generate_caption.remote(
            topic=topic,
            day=day,
            slot=slot,
            cluster_id=cluster_id,
            agent_attrs=agent_attrs,
        )
    except Exception as exc:
        logger.warning(f"Caption generation failed for user {user_id}: {exc}")
        caption = f"#{topic}"

    photo_data = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "round": round_id,
        "image_url": image_url or f"https://placeholder.photos/{uuid.uuid4().hex[:8]}",
        "caption": caption,
        "filter_name": filter_name,
        "location_name": location_name,
    }

    try:
        photo_id = await server.post_photo.remote(photo_data)
        logger.debug(f"User {user_id} posted photo {photo_id}")
        return photo_id
    except Exception as exc:
        logger.error(f"Failed to persist photo for user {user_id}: {exc}")
        return None
