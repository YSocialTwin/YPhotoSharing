from __future__ import annotations

import random
from typing import Dict, List, Optional


def coerce_cluster_id(value) -> int:
    """Convert legacy/non-numeric recsys_type values into a valid persona cluster id."""
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return 0
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def normalize_agent_population_document(population):
    """Normalize a population config into the YSimulator-style document format."""
    if isinstance(population, list):
        return {
            "agents": population,
            "generation_config": {
                "num_additional_agents": 0,
                "default_settings": {},
            },
        }

    if isinstance(population, dict):
        normalized = dict(population)
        normalized.setdefault("agents", [])
        normalized.setdefault(
            "generation_config",
            {
                "num_additional_agents": 0,
                "default_settings": {},
            },
        )
        if not isinstance(normalized["generation_config"], dict):
            normalized["generation_config"] = {
                "num_additional_agents": 0,
                "default_settings": {},
            }
        normalized["generation_config"].setdefault("num_additional_agents", 0)
        normalized["generation_config"].setdefault("default_settings", {})
        return normalized

    raise TypeError("Agent population must be a list or a dict with an 'agents' key")


def normalize_agent_config(user_config: dict, simulation_config: Optional[dict]) -> dict:
    """Return a simulation-ready agent config without mutating the input."""
    simulation_config = simulation_config or {}
    enriched = dict(user_config)

    photo_sharing_cfg = enriched.get("photo_sharing")
    if isinstance(photo_sharing_cfg, dict):
        for key, value in photo_sharing_cfg.items():
            enriched.setdefault(key, value)

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
    enriched.setdefault("email", "")
    enriched.setdefault("password", "simulation_agent")
    enriched.setdefault("user_type", "regular")
    enriched.setdefault("age", 0)
    enriched.setdefault("gender", "unknown")
    enriched.setdefault("nationality", "")
    enriched.setdefault("oe", "medium")
    enriched.setdefault("co", "medium")
    enriched.setdefault("ex", "medium")
    enriched.setdefault("ag", "medium")
    enriched.setdefault("ne", "medium")
    enriched.setdefault("language", "en")
    enriched.setdefault("round_actions", 3)
    enriched.setdefault("daily_activity_level", 1)
    enriched.setdefault("bio", "")
    enriched.setdefault("is_verified", False)
    enriched.setdefault("attention_budget", 100)
    enriched.setdefault("frecsys_type", enriched.get("recsys_type", "default"))
    enriched["recsys_type"] = coerce_cluster_id(enriched.get("recsys_type"))
    enriched.setdefault("feed_url", None)
    enriched.setdefault("opinions", {})
    enriched.setdefault("stubborn_topics", [])
    enriched.setdefault("custom_features", {})

    interests = enriched.get("interests", [])
    if isinstance(interests, list):
        if len(interests) == 2 and isinstance(interests[0], list) and isinstance(interests[1], (int, float)):
            enriched["interests"] = list(interests[0])
        else:
            normalized_interests = []
            for item in interests:
                if isinstance(item, list):
                    normalized_interests.extend(item)
                elif isinstance(item, str):
                    normalized_interests.append(item)
            enriched["interests"] = normalized_interests
    else:
        enriched["interests"] = []

    user_type = str(enriched.get("user_type", "")).strip().lower()
    if user_type in {"llm", "rule_based", "rule-based", "rule"}:
        enriched["llm"] = user_type == "llm"
    elif "llm" in enriched:
        enriched["llm"] = bool(enriched["llm"])
    else:
        enriched["llm"] = True

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
