import logging

from YPhotoSharing.YClient.actions.dynamics_helpers import (
    build_stress_reward_variations,
    persist_opinion_updates,
    persist_stress_reward_variations,
    resolve_photo_topic_ids,
)
from YPhotoSharing.YClient.actions.rule_based_actions import generate_rule_based_reply

logger = logging.getLogger(__name__)

async def reply_comment(
    server,
    llm_service,
    user_id: str,
    photo_id: str,
    parent_comment_id: str,
    round_id: str,
    day: int,
    slot: int,
    cluster_id: int,
    agent_attrs: dict = None,
    opinion_manager=None,
    stress_reward_system=None,
    stress_reward_enabled: bool = False,
    stress_reward_backward_rounds: int = 24,
) -> bool:
    """
    Generate a reply to a specific comment via the LLM and post it.
    """
    try:
        is_llm_agent = bool((agent_attrs or {}).get("llm", True))
        if is_llm_agent and llm_service and hasattr(llm_service, "generate_comment"):
            reply_body = await llm_service.generate_comment.remote(
                caption="Replying to comment thread",
                author="another_user",
                cluster_id=cluster_id,
                agent_attrs=None
            )
        else:
            reply_body = generate_rule_based_reply(
                caption="Replying to comment thread",
                author="another_user",
                username=(agent_attrs or {}).get("username", str(user_id)),
                cluster_id=cluster_id,
            )

        photo = await server.get_photo.remote(photo_id)
        if not photo:
            return False

        await server.post_comment.remote(
            user_id=user_id,
            photo_id=photo_id,
            body=reply_body,
            round_id=round_id,
            parent_comment_id=parent_comment_id
        )

        try:
            topic_ids = await resolve_photo_topic_ids(
                server,
                photo_id,
                caption=photo.get("caption", ""),
                fallback_topic=photo.get("topic", "general"),
            )
            if topic_ids:
                await server.set_user_interests.remote(user_id, topic_ids, round_id)
        except Exception as e:
            logger.warning(f"Failed to evolve interest in reply_comment: {e}")

        if stress_reward_enabled and stress_reward_system and photo.get("user_id") and photo.get("user_id") != user_id:
            try:
                body_lower = reply_body.strip().lower()
                tone = "neutral"
                if any(k in body_lower for k in ("great", "love", "nice", "support", "awesome")):
                    tone = "supportive"
                elif any(k in body_lower for k in ("hate", "stupid", "idiot", "trash", "awful")):
                    tone = "hostile"

                target_state = stress_reward_system.compute_current_stress_reward(
                    server=server,
                    agent_id=str(photo.get("user_id")),
                    current_tid=str(round_id),
                    backward_rounds=stress_reward_backward_rounds,
                )
                deltas = stress_reward_system.compute_comment_delta(
                    tone=tone,
                    current_stress=target_state["stress"],
                    current_reward=target_state["reward"],
                    directness=1.0,
                    support_strength=1.0 if tone == "supportive" else 0.0,
                )
                await persist_stress_reward_variations(
                    server,
                    target_user_id=str(photo.get("user_id")),
                    round_id=round_id,
                    variations=build_stress_reward_variations(deltas),
                    action_name=f"comment:{tone}",
                )
            except Exception as e:
                logger.warning(f"Failed to persist stress/reward for reply: {e}")

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
                logger.warning(f"Failed to process opinion dynamics in reply_comment: {e}")

        logger.debug(f"User {user_id} replied to comment {parent_comment_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to reply for user {user_id}: {exc}")
        return False
