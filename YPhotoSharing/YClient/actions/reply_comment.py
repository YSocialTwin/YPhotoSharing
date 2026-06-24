import logging

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
    opinion_manager=None,
    stress_reward_system=None,
    stress_reward_enabled: bool = False,
    stress_reward_backward_rounds: int = 24,
) -> bool:
    """
    Generate a reply to a specific comment via the LLM and post it.
    """
    try:
        reply_body = await llm_service.generate_comment.remote(
            caption="Replying to comment thread",
            author="another_user",
            cluster_id=cluster_id,
            agent_attrs=None
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
            topic_ids = await server.get_photo_topics.remote(photo_id)
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
                variations = []
                if abs(float(deltas.get("delta_stress", 0.0))) > 1e-9:
                    variations.append({"variable": "stress", "value": float(deltas["delta_stress"])})
                if abs(float(deltas.get("delta_reward", 0.0))) > 1e-9:
                    variations.append({"variable": "reward", "value": float(deltas["delta_reward"])})
                if variations:
                    await server.set_stress_reward_variations.remote(
                        str(photo.get("user_id")),
                        round_id,
                        variations,
                        action_name=f"comment:{tone}",
                    )
            except Exception as e:
                logger.warning(f"Failed to persist stress/reward for reply: {e}")

        if opinion_manager and opinion_manager.is_enabled():
            try:
                updates = opinion_manager.calculate_opinion_updates(
                    agent_id=user_id,
                    parent_post_id=photo_id,
                    parent_post_data=photo,
                )
                if updates:
                    for topic_id, new_val in updates.items():
                        event = getattr(opinion_manager.calculator, "last_update_events", {}).get(topic_id, {})
                        topic_name = event.get("topic_name", topic_id)
                        await server.update_user_opinion.remote(
                            user_id,
                            topic_name,
                            new_val,
                            round_id,
                            topic_id=topic_id,
                            opinion_label=event.get("target_label"),
                            model_name=event.get("model_name"),
                        )
                        if event:
                            await server.record_opinion_path.remote(
                                user_id,
                                topic_name,
                                round_id,
                                event.get("model_name", "bounded_confidence"),
                                event.get("source_score"),
                                event.get("source_label"),
                                event.get("target_score", new_val),
                                event.get("target_label"),
                                event.get("transition", "neutral"),
                                direction=event.get("direction"),
                                evaluation_scope=event.get("evaluation_scope"),
                                topic_id=topic_id,
                                parent_post_id=photo_id,
                                actor_user_id=user_id,
                                payload_json=None,
                            )
            except Exception as e:
                logger.warning(f"Failed to process opinion dynamics in reply_comment: {e}")

        logger.debug(f"User {user_id} replied to comment {parent_comment_id}")
        return True
    except Exception as exc:
        logger.error(f"Failed to reply for user {user_id}: {exc}")
        return False
