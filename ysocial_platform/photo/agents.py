"""What the runtime of a photo-sharing experiment reads from the agents of a population file."""

import json

from y_web.sdk.agents import random_cover_image_url

PHOTO_SHARING_LIKERT_SCALE = [
    "Strongly disagree",
    "Disagree",
    "Neutral",
    "Agree",
    "Strongly agree",
]


def _parse_agent_ext_value(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return json.loads(stripped)
        except Exception:
            return value
    return value


def payload_from_agent(agent, ext_map):
    photo_payload = {"cover_image": agent.cover_image or random_cover_image_url()}
    for feature_name in ("favorite_filters", "story_visibility", "creator_tier"):
        parsed = _parse_agent_ext_value(ext_map.get(feature_name))
        if parsed not in (None, ""):
            photo_payload[feature_name] = parsed
    return photo_payload


def apply_agent_fields(agent_payload, agent, ext_map):
    bio = _parse_agent_ext_value(ext_map.get("bio"))
    if bio not in (None, ""):
        agent_payload["bio"] = bio

    is_private = _parse_agent_ext_value(ext_map.get("is_private"))
    if is_private is not None:
        agent_payload["is_private"] = bool(is_private)

    is_verified = _parse_agent_ext_value(ext_map.get("is_verified"))
    if is_verified is not None:
        agent_payload["is_verified"] = bool(is_verified)

    attention_budget = _parse_agent_ext_value(ext_map.get("attention_budget"))
    if attention_budget not in (None, ""):
        agent_payload["attention_budget"] = attention_budget

    agent_payload["photo_sharing"] = payload_from_agent(agent, ext_map)


def cluster_id(value) -> str:
    """Return a YPhotoSharing-compatible persona cluster id."""
    if value is None:
        return "0"
    text = str(value).strip()
    if not text:
        return "0"
    if text.isdigit():
        return text
    return "0"


def activity_profiles(profiles: dict) -> dict:
    """Convert stored activity profile hours to the list format used by YPhotoSharing."""
    serialized = {}
    for name, hours in (profiles or {}).items():
        if isinstance(hours, str):
            values = []
            for item in hours.split(","):
                item = item.strip()
                if not item:
                    continue
                try:
                    values.append(int(item))
                except ValueError:
                    continue
            serialized[name] = values
        elif isinstance(hours, (list, tuple)):
            serialized[name] = [int(value) for value in hours]
        else:
            serialized[name] = []
    return serialized
