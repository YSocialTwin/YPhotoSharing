from __future__ import annotations

import random
from typing import Dict, List, Optional


def normalize_agent_config(user_config: dict, simulation_config: Optional[dict]) -> dict:
    """Return a simulation-ready agent config without mutating the input."""
    simulation_config = simulation_config or {}
    enriched = dict(user_config)

    if "is_private" not in enriched:
        enriched["is_private"] = random.random() < 0.20

    if "activity_profile" not in enriched:
        profiles = list(simulation_config.get("activity_profiles", {"Always On": ""}).keys())
        enriched["activity_profile"] = random.choice(profiles) if profiles else None

    if "archetype" not in enriched:
        archetype_cfg = simulation_config.get("agent_archetypes", {})
        if archetype_cfg.get("enabled", False):
            dist = archetype_cfg.get(
                "distribution",
                {"broadcaster": 0.33, "explorer": 0.34, "validator": 0.33},
            )
            keys = list(dist.keys())
            weights = list(dist.values())
            enriched["archetype"] = random.choices(keys, weights=weights, k=1)[0]
        else:
            enriched["archetype"] = None

    enriched["enable_opinion_dynamics"] = simulation_config.get("opinion_dynamics", {}).get("enabled", False)
    enriched["enable_sentiment"] = bool(simulation_config.get("enable_sentiment", False))
    enriched["enable_emotion_annotation"] = bool(
        simulation_config.get("enable_emotion_annotation", True)
    )
    enriched["enable_memory_annotations"] = bool(
        simulation_config.get("enable_memory_annotations", True)
    )

    agents_cfg = simulation_config.get("agents", {})
    enriched["probability_of_secondary_follow"] = agents_cfg.get(
        "probability_of_secondary_follow", 0.1
    )
    enriched["probability_of_follow_back"] = agents_cfg.get(
        "probability_of_follow_back", 0.1
    )
    return enriched


def build_initial_interest_ids(
    *,
    user_config: dict,
    simulation_config: Optional[dict],
    topic_ids: List[str],
    topic_lookup: Dict[str, str],
) -> List[str]:
    """Build the initial interest set for a user from config and available topics."""
    simulation_config = simulation_config or {}
    topics = simulation_config.get("discussion_topics", ["general"])
    user_interests = user_config.get("interests", [])

    if user_interests:
        interest_ids = []
        for topic in user_interests:
            if topic in topic_lookup:
                interest_ids.append(topic_lookup[topic])
            elif topic in topics:
                idx = topics.index(topic)
                if idx < len(topic_ids):
                    interest_ids.append(topic_ids[idx])
            elif topic:
                # Let the server create a topic identifier for out-of-band topics.
                interest_ids.append(topic)
        return interest_ids

    if not topic_ids:
        return []

    num_interests = random.randint(1, min(3, max(1, len(topic_ids))))
    return random.sample(topic_ids, num_interests)
