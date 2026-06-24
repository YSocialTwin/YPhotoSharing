"""
Deterministic photo-sharing behaviors for rule-based agents.
"""

from __future__ import annotations

import hashlib
from typing import Iterable, Optional


def _stable_choice(options: Iterable[str], *parts: object) -> str:
    options = list(options)
    if not options:
        return ""
    seed = "::".join(str(part) for part in parts)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return options[int(digest[:8], 16) % len(options)]


def generate_rule_based_caption(topic: str, username: str, cluster_id: int = 0) -> str:
    return _stable_choice(
        [
            f"{topic.title()} moments from @{username} #photo",
            f"Sharing a {topic} snapshot ✨",
            f"{topic.title()} vibes by @{username}",
        ],
        "caption",
        username,
        topic,
        cluster_id,
    )


def generate_rule_based_comment(
    caption: str,
    author: str,
    username: str,
    cluster_id: int = 0,
) -> str:
    return _stable_choice(
        [
            f"Nice shot, @{author}!",
            f"Love this {caption[:32].strip()}",
            f"Great photo @{author} #goodvibes",
            f"@{author} this is lovely!",
        ],
        "comment",
        username,
        author,
        caption,
        cluster_id,
    )


def generate_rule_based_reply(
    caption: str,
    author: str,
    username: str,
    cluster_id: int = 0,
) -> str:
    return _stable_choice(
        [
            f"@{author} totally agree!",
            f"@{author} love this reply",
            f"@{author} nice perspective!",
        ],
        "reply",
        username,
        author,
        caption,
        cluster_id,
    )


def generate_rule_based_reaction(
    caption: str,
    username: str,
    interests: Optional[Iterable[str]] = None,
    cluster_id: int = 0,
) -> str:
    caption_lower = caption.lower()
    matched = []
    for interest in interests or []:
        if interest and str(interest).lower() in caption_lower:
            matched.append(str(interest))

    if matched:
        return _stable_choice(["LIKE", "LOVE", "WOW"], "reaction", username, caption, cluster_id)
    return _stable_choice(["LIKE", "LIKE", "ANGRY", "WOW", "IGNORE"], "reaction", username, caption, cluster_id)


def generate_rule_based_follow_decision(
    username: str,
    bio: str,
    topics: str,
    cluster_id: int = 0,
) -> str:
    decision = _stable_choice(["FOLLOW", "SKIP", "FOLLOW"], "follow", username, bio, topics, cluster_id)
    return decision


def generate_rule_based_follow_request_decision(
    username: str,
    bio: str,
    cluster_id: int = 0,
) -> str:
    decision = _stable_choice(["ACCEPT", "REJECT", "ACCEPT"], "follow_request", username, bio, cluster_id)
    return decision


def generate_rule_based_story(topic: str, username: str, cluster_id: int = 0) -> str:
    return _stable_choice(
        [
            f"Story update from @{username} about {topic}",
            f"{topic.title()} moments, shared by @{username}",
            f"{username} is feeling {topic} today",
        ],
        "story",
        username,
        topic,
        cluster_id,
    )
