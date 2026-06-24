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
    agent_attrs: Optional[dict] = None,
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

        # Stage 9: Evolve user interests
        try:
            import re
            tags = re.findall(r"#(\w+)", caption)
            topic = tags[0] if tags else photo.get("topic", "general")
            
            # Evolve interest
            tid = await server.get_or_create_interest.remote(topic)
            await server.set_user_interests.remote(user_id, [tid], round_id)
        except Exception as e:
            logger.warning(f"Failed to evolve interest in react: {e}")
            topic = "general"
            
        # Stage 6: Opinion Dynamics
        if agent_attrs and agent_attrs.get("enable_opinion_dynamics") and caption:
            try:
                opinion_options = ["Strongly against", "Against", "Neutral", "In favor", "Strongly in favor"]
                
                # 1. Infer stance of the photo
                stance = await llm_service.infer_article_opinion.remote(caption, topic, opinion_options)
                
                # 2. Get agent's current opinion on this topic
                opinions = await server.get_user_opinions.remote(user_id)
                current_opinion = opinions.get(topic, 0.5)
                
                # 3. Evaluate and evolve opinion
                new_opinion = await llm_service.evaluate_opinion.remote(caption, photo.get("username", "user"), topic, current_opinion)
                
                # 4. Save
                if new_opinion != current_opinion:
                    await server.update_user_opinion.remote(user_id, topic, new_opinion)
            except Exception as e:
                logger.warning(f"Failed to process opinion dynamics in react: {e}")

        return reaction
    except Exception as exc:
        logger.error(f"Failed to persist reaction for user {user_id}: {exc}")
        return None
