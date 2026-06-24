from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


def infer_comment_tone(body: str, sentiment_score: Optional[float] = None) -> str:
    body_lower = (body or "").strip().lower()
    if sentiment_score == 1.0:
        return "positive"
    if sentiment_score == -1.0:
        if any(k in body_lower for k in ("hate", "stupid", "idiot", "trash", "awful")):
            return "hostile"
        return "critical"
    if any(k in body_lower for k in ("great", "love", "nice", "support", "awesome")):
        return "supportive"
    return "neutral"


def build_stress_reward_variations(deltas: Dict[str, float], epsilon: float = 1e-9) -> List[dict]:
    variations = []
    for variable in ("stress", "reward"):
        value = float(deltas.get(f"delta_{variable}", 0.0))
        if abs(value) > epsilon:
            variations.append({"variable": variable, "value": value})
    return variations


async def persist_stress_reward_variations(
    server,
    *,
    target_user_id: str,
    round_id: str,
    variations: List[dict],
    action_name: str,
) -> None:
    if not variations:
        return
    await server.set_stress_reward_variations.remote(
        str(target_user_id),
        round_id,
        variations,
        action_name=action_name,
    )


async def build_memory_context(
    server,
    *,
    run_id: str,
    agent_user_id: str,
    other_user_id: str,
    label: str,
    limit: int = 50,
    max_entries: int = 5,
) -> Optional[str]:
    memories = await server.get_memory_events.remote(
        run_id=run_id, agent_user_id=agent_user_id, limit=limit
    )
    related_mems = [m for m in memories if m.get("other_user_id") == other_user_id]
    if not related_mems:
        return None
    mem_texts = [m.get("event_type", "interaction") for m in related_mems[:max_entries]]
    return f"{label}: {', '.join(mem_texts)}"


async def record_memory_event(
    server,
    *,
    enabled: bool,
    event_data: Dict[str, Any],
) -> None:
    if not enabled:
        return
    await server.add_memory_event.remote(event_data)


async def persist_opinion_updates(
    *,
    opinion_manager,
    server,
    user_id: str,
    parent_post_id: str,
    parent_post_data: dict,
    round_id: str,
) -> int:
    if not opinion_manager or not opinion_manager.is_enabled():
        return 0

    updates = opinion_manager.calculate_opinion_updates(
        agent_id=user_id,
        parent_post_id=parent_post_id,
        parent_post_data=parent_post_data,
    )
    if not updates:
        return 0

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
                parent_post_id=parent_post_id,
                actor_user_id=user_id,
                payload_json=None,
            )
    return len(updates)


async def resolve_photo_topic_ids(
    server,
    photo_id: str,
    *,
    caption: str = "",
    fallback_topic: str = "general",
) -> List[str]:
    topic_ids = await server.get_photo_topics.remote(photo_id)
    if topic_ids:
        return list(topic_ids)

    tags = re.findall(r"#(\w+)", caption or "")
    topic_name = tags[0] if tags else fallback_topic
    topic_id = await server.get_or_create_interest.remote(topic_name)
    return [topic_id]
