"""
Reaction action for YPhotoSharing agents.

Agents call react_to_photo() to like / love / etc. a photo.
The LLM decides the reaction type; the server records it.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

VALID_REACTIONS = {"LIKE", "LOVE", "LAUGH", "WOW", "SAD", "ANGRY", "IGNORE"}


async def react_to_photo(
    server,
    llm_service,
    user_id: str,
    photo: dict,
    round_id: str,
) -> Optional[str]:
    """
    Have the agent decide how to react to *photo* and persist the decision.

    Args:
        server: Ray handle to OrchestratorServer
        llm_service: Ray handle to an LLM service actor
        user_id: UUID of the reacting user
        photo: Photo dict (must include 'id' and 'caption')
        round_id: Current simulation round UUID

    Returns:
        Reaction type string, or None if the agent ignores the photo
    """
    caption = photo.get("caption", "")
    photo_id = photo.get("id", "")

    try:
        reaction = await llm_service.decide_reaction.remote(caption=caption)
    except Exception as exc:
        logger.warning(f"Reaction decision failed for user {user_id}: {exc}")
        reaction = "IGNORE"

    if reaction == "IGNORE":
        logger.debug(f"User {user_id} ignored photo {photo_id}")
        return None

    try:
        await server.react_to_photo.remote(
            user_id=user_id,
            photo_id=photo_id,
            reaction_type=reaction,
            round_id=round_id,
        )
        logger.debug(f"User {user_id} reacted {reaction} to photo {photo_id}")
        return reaction
    except Exception as exc:
        logger.error(f"Failed to persist reaction for user {user_id}: {exc}")
        return None
