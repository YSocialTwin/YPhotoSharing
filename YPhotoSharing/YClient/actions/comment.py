"""
Comment action for YPhotoSharing agents.

Agents call post_comment() to leave a comment on a photo.
The LLM generates the comment text; the server persists it.
"""

import logging
from typing import Optional

from YPhotoSharing.YClient.actions.dynamics_helpers import (
    build_memory_context,
    build_stress_reward_variations,
    infer_comment_tone,
    persist_opinion_updates,
    persist_stress_reward_variations,
    record_memory_event,
    resolve_photo_topic_ids,
)
from YPhotoSharing.YClient.actions.rule_based_actions import generate_rule_based_comment

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
    opinion_manager = None,
    stress_reward_system=None,
    stress_reward_enabled: bool = False,
    stress_reward_backward_rounds: int = 24,
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

    if agent_attrs is None:
        agent_attrs = {}
    is_llm_agent = bool(agent_attrs.get("llm", True))

    try:
        following_ids = await server.get_following.remote(user_id)
        if following_ids:
            import random
            sample_ids = random.sample(following_ids, min(3, len(following_ids)))
            following_usernames = []
            for fid in sample_ids:
                u = await server.get_user.remote(fid)
                if u and u.get("username"):
                    following_usernames.append(u["username"])
            agent_attrs["following_usernames"] = following_usernames
    except Exception as e:
        logger.warning(f"Could not fetch following usernames for comment mentions: {e}")

    photo_author_id = photo.get("user_id")
    if photo_author_id and agent_attrs.get("enable_memory_annotations", True):
        try:
            memory_context = await build_memory_context(
                server,
                run_id="default",
                agent_user_id=user_id,
                other_user_id=photo_author_id,
                label="Past interactions with photo author",
            )
            if memory_context:
                agent_attrs["memory_context"] = memory_context
        except Exception as e:
            logger.warning(f"Could not retrieve memories for comment: {e}")

    if is_llm_agent:
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
    else:
        body = generate_rule_based_comment(
            caption=caption,
            author=author,
            username=agent_attrs.get("username", user_id),
            cluster_id=cluster_id,
        )

    if not body or not body.strip():
        return None

    try:
        sentiment_score = None
        comment_id = await server.post_comment.remote(
            user_id=user_id,
            photo_id=photo_id,
            body=body.strip(),
            round_id=round_id,
            parent_comment_id=parent_comment_id,
        )
        
        # YSimulator Stage 4: Store post-interaction summary
        if photo_author_id and photo_author_id != user_id and agent_attrs.get("enable_memory_annotations", True):
            try:
                event_data = {
                    "run_id": "default",
                    "agent_user_id": user_id,
                    "other_user_id": photo_author_id,
                    "event_type": "commented",
                    "description": f"Commented: {body[:50]}...",
                    "round_id": 0 # We don't have day/hour easily here, so 0 is fine
                }
                await record_memory_event(server, enabled=True, event_data=event_data)
            except Exception as e:
                logger.warning(f"Could not save memory event for comment: {e}")

        # Stage 5: Sentiment Annotation
        if agent_attrs and agent_attrs.get("enable_sentiment"):
            try:
                sentiment_score = await llm_service.extract_sentiment.remote(body.strip())
                await server.update_comment_sentiment.remote(comment_id, sentiment_score)
            except Exception as e:
                logger.warning(f"Failed to extract sentiment for comment {comment_id}: {e}")

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
            logger.warning(f"Failed to evolve interest in comment: {e}")

        if (
            stress_reward_enabled
            and stress_reward_system
            and photo_author_id
            and photo_author_id != user_id
        ):
            try:
                tone = infer_comment_tone(body, sentiment_score)

                target_state = stress_reward_system.compute_current_stress_reward(
                    server=server,
                    agent_id=str(photo_author_id),
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
                    target_user_id=str(photo_author_id),
                    round_id=round_id,
                    variations=build_stress_reward_variations(deltas),
                    action_name=f"comment:{tone}",
                )
            except Exception as e:
                logger.warning(f"Failed to persist stress/reward for comment: {e}")

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
                logger.warning(f"Failed to process opinion dynamics in comment: {e}")

        logger.debug(f"User {user_id} commented on photo {photo_id}")
        return comment_id
    except Exception as exc:
        logger.error(f"Failed to persist comment for user {user_id}: {exc}")
        return None
