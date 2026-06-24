"""
Reaction action for YPhotoSharing agents.

Agents call react_to_photo() to like / love / etc. a photo.
The LLM decides the reaction type; the server records it.
"""

import logging
from typing import Optional

from YPhotoSharing.YClient.actions.dynamics_helpers import (
    build_stress_reward_variations,
    persist_opinion_updates,
    persist_stress_reward_variations,
    resolve_photo_topic_ids,
)
from YPhotoSharing.YClient.actions.rule_based_actions import generate_rule_based_reaction

logger = logging.getLogger(__name__)

VALID_REACTIONS = {"LIKE", "LOVE", "LAUGH", "WOW", "SAD", "ANGRY", "IGNORE"}


async def react_to_photo(
    server,
    llm_service,
    user_id: str,
    photo: dict,
    round_id: str,
    agent_attrs: Optional[dict] = None,
    opinion_manager = None,
    stress_reward_system=None,
    stress_reward_enabled: bool = False,
    stress_reward_backward_rounds: int = 24,
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
    cluster_id = int((agent_attrs or {}).get("recsys_type") or 0)
    is_llm_agent = bool((agent_attrs or {}).get("llm", True))

    if is_llm_agent:
        try:
            reaction = await llm_service.decide_reaction.remote(caption=caption)
        except Exception as exc:
            logger.warning(f"Reaction decision failed for user {user_id}: {exc}")
            reaction = "IGNORE"
    else:
        reaction = generate_rule_based_reaction(
            caption=caption,
            username=(agent_attrs or {}).get("username", user_id),
            interests=(agent_attrs or {}).get("interests", []),
            cluster_id=cluster_id,
        )

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
            topic_ids = await resolve_photo_topic_ids(
                server,
                photo_id,
                caption=caption,
                fallback_topic=photo.get("topic", "general"),
            )
            if topic_ids:
                await server.set_user_interests.remote(user_id, topic_ids, round_id)
        except Exception as e:
            logger.warning(f"Failed to evolve interest in react: {e}")

        if (
            stress_reward_enabled
            and stress_reward_system
            and photo.get("user_id")
            and photo.get("user_id") != user_id
        ):
            try:
                target_state = stress_reward_system.compute_current_stress_reward(
                    server=server,
                    agent_id=str(photo.get("user_id")),
                    current_tid=str(round_id),
                    backward_rounds=stress_reward_backward_rounds,
                )
                event_name = "like" if reaction in {"LIKE", "LOVE", "LAUGH"} else "dislike"
                deltas = stress_reward_system.compute_reaction_delta(
                    reaction=event_name,
                    current_stress=target_state["stress"],
                    current_reward=target_state["reward"],
                )
                await persist_stress_reward_variations(
                    server,
                    target_user_id=str(photo.get("user_id")),
                    round_id=round_id,
                    variations=build_stress_reward_variations(deltas),
                    action_name=f"reaction:{reaction.lower()}",
                )
            except Exception as e:
                logger.warning(f"Failed to persist stress/reward for reaction: {e}")
            
        # Stage 6: Opinion Dynamics
        if opinion_manager and opinion_manager.is_enabled():
            try:
                await persist_opinion_updates(
                    opinion_manager=opinion_manager,
                    server=server,
                    user_id=user_id,
                    parent_post_id=photo_id,
                    parent_post_data=photo,
                    round_id=round_id,
                )
            except Exception as e:
                logger.warning(f"Failed to process opinion dynamics in react: {e}")

        return reaction
    except Exception as exc:
        logger.error(f"Failed to persist reaction for user {user_id}: {exc}")
        return None
