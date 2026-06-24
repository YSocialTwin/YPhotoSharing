from enum import Enum
from typing import List, Optional

from YPhotoSharing.YClient.opinion_dynamics.utils import get_opinion_group, ordered_opinion_labels


class Direction(Enum):
    """Direction of opinion shift."""

    AGREE = 1
    DISAGREE = -1


def class_mid(bounds):
    """Calculate the midpoint of an opinion class range."""
    return (bounds[0] + bounds[1]) / 2


def shift_class(current_label, target_label, direction, class_bounds):
    """
    Shift opinion from one discrete class to an adjacent class.

    The transition is always at most one step, matching the YSimulator pattern:
    - AGREE moves one class toward the target label
    - DISAGREE moves one class away from the target label
    - NEUTRAL keeps the current label
    """
    ordered_labels = ordered_opinion_labels(class_bounds)
    bounds_map = dict(class_bounds.items())

    if current_label not in bounds_map or target_label not in bounds_map:
        raise ValueError("Class label not found")
    if current_label == target_label:
        return current_label, class_mid(bounds_map[current_label])

    current_idx = ordered_labels.index(current_label)
    target_idx = ordered_labels.index(target_label)
    step_toward_target = 1 if target_idx > current_idx else -1

    if direction == Direction.AGREE:
        step = step_toward_target
    elif direction == Direction.DISAGREE:
        step = -step_toward_target
    else:
        raise ValueError("Unknown direction")

    new_idx = max(0, min(current_idx + step, len(ordered_labels) - 1))
    new_label = ordered_labels[new_idx]
    return new_label, class_mid(bounds_map[new_label])


def _build_peer_summary(peers_opinions: Optional[list], group_classes: dict) -> Optional[list]:
    if not peers_opinions:
        return None
    if peers_opinions and isinstance(peers_opinions[0], tuple):
        return list(peers_opinions)
    counts = {}
    for opinion_value in peers_opinions:
        label = get_opinion_group(opinion_value, group_classes)
        counts[label] = counts.get(label, 0) + 1
    return list(counts.items())


def llm_evaluation(
    x: float,
    y: float,
    text: str = None,
    topic: str = None,
    author_name: str = None,
    evaluation_scope: str = "interlocutor_only",
    cold_start: str = "neutral",
    group_classes: dict = None,
    peers_opinions: list = None,
    llm_manager=None,
    agent_id: str = None,
) -> float:
    """
    LLM-based discrete opinion evaluation.

    The model reasons over an ordered Likert scale and returns one of:
    AGREE, DISAGREE, or NEUTRAL. The resulting transition is applied as a
    single adjacent-class step, mirroring the YSimulator approach.
    """
    group_classes = group_classes or {}
    ordered_labels = ordered_opinion_labels(group_classes)
    if not ordered_labels:
        ordered_labels = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]
        group_classes = {
            "Strongly disagree": (0.0, 0.2),
            "Disagree": (0.2, 0.4),
            "Neutral": (0.4, 0.6),
            "Agree": (0.6, 0.8),
            "Strongly agree": (0.8, 1.0),
        }

    if x is None:
        if cold_start == "neutral":
            return class_mid(group_classes["Neutral"])
        if cold_start == "inherited":
            return y
        return class_mid(group_classes[ordered_labels[len(ordered_labels) // 2]])

    x_label = get_opinion_group(x, group_classes)
    y_label = get_opinion_group(y, group_classes)
    peer_summary = _build_peer_summary(peers_opinions, group_classes) if evaluation_scope != "interlocutor_only" else None

    import ray

    response = ray.get(
        llm_manager.evaluate_opinion_transition(
            post_content=text,
            author_name=author_name or "author",
            topic=topic,
            current_label=x_label,
            author_label=y_label,
            opinion_scale=ordered_labels,
            peers_opinions=peer_summary,
            agent_id=agent_id,
        )
    )

    if "AGREE" in str(response).upper():
        _, new_value = shift_class(x_label, y_label, Direction.AGREE, group_classes)
        return new_value
    if "DISAGREE" in str(response).upper():
        _, new_value = shift_class(x_label, y_label, Direction.DISAGREE, group_classes)
        return new_value
    return x
