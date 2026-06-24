from enum import Enum

from YPhotoSharing.YClient.opinion_dynamics.utils import get_opinion_group


class Direction(Enum):
    """Direction of opinion shift."""

    AGREE = 1
    DISAGREE = -1


def class_mid(bounds):
    """Calculate the midpoint of an opinion class range."""
    return (bounds[0] + bounds[1]) / 2


def shift_class(A, B, direction, class_bounds):
    """
    Shift opinion from class A towards or away from class B.

    Args:
        A: Current opinion class label
        B: Target opinion class label (interlocutor's opinion)
        direction: Direction.AGREE (move towards B) or Direction.DISAGREE (move away from B)
        class_bounds: Dict mapping class labels to [min, max] ranges

    Returns:
        Tuple of (new_label, new_value) where new_value is the midpoint of the new class
    """
    # Order classes by lower bound
    ordered = sorted(class_bounds.items(), key=lambda x: x[1][0])

    labels = [lbl for lbl, _ in ordered]
    bounds_map = dict(ordered)

    if A not in bounds_map or B not in bounds_map:
        raise ValueError("Class label not found")

    # Case: identical classes → no shift
    if A == B:
        return A, class_mid(bounds_map[A])

    idx_A = labels.index(A)
    idx_B = labels.index(B)

    # Determine step direction
    step_towards_B = 1 if idx_B > idx_A else -1

    if direction == Direction.AGREE:
        step = step_towards_B
    elif direction == Direction.DISAGREE:
        step = -step_towards_B
    else:
        raise ValueError("Unknown direction")

    new_idx = idx_A + step

    # Clamp to boundaries
    new_idx = max(0, min(new_idx, len(labels) - 1))

    new_label = labels[new_idx]
    new_mid = class_mid(bounds_map[new_label])

    return new_label, new_mid


def llm_evaluation(
    x: float,
    y: float,
    text: str = None,
    topic: str = None,
    evaluation_scope: str = "interlocutor_only",
    cold_start: str = "neutral",
    group_classes: dict = None,
    peers_opinions: list = None,
    llm_manager=None,
    agent_id: str = None,
) -> float:
    """
    LLM-based evaluation of opinion dynamics between two users.

    This function uses an LLM to evaluate how an agent's opinion should change
    after reading a post from another user. The LLM considers:
    - The agent's current opinion on the topic
    - The author's opinion on the topic
    - The post content
    - Optionally, the opinions of the agent's neighbors

    Args:
        x: Agent's current opinion value (None for cold start)
        y: Author's opinion value (must not be None)
        text: Post content to evaluate
        topic: Topic name being discussed
        evaluation_scope: "interlocutor_only" or "neighbors"
        cold_start: "neutral" (start at 0.5) or "inherited" (start at y)
        group_classes: Dict mapping opinion labels to [min, max] ranges
        peers_opinions: List of (opinion_label, count) tuples for neighbors
        llm_manager: LLMManager instance (wraps Ray actor for LLM service)

    Returns:
        float: Updated opinion value in [0, 1] range
    """
    # Handle cold start case (agent has no prior opinion on this topic)
    if x is None:
        if cold_start == "neutral":
            x = 0.5
        elif cold_start == "inherited":
            x = y
        return x

    # Get opinion labels for agent and author
    x_op = get_opinion_group(x, group_classes)
    y_op = get_opinion_group(y, group_classes)

    # Call LLM manager to evaluate opinion (returns Ray future)
    import ray

    future = llm_manager.evaluate_opinion(
        agent_opinion=x_op,
        author_opinion=y_op,
        post_text=text,
        topic=topic,
        peers_opinions=peers_opinions if evaluation_scope != "interlocutor_only" else None,
        agent_id=agent_id,
    )
    response = ray.get(future)

    # Shift opinion class based on LLM response
    if "AGREE" in response.upper():
        new_class, x = shift_class(x_op, y_op, Direction.AGREE, group_classes)
    elif "DISAGREE" in response.upper():
        new_class, x = shift_class(x_op, y_op, Direction.DISAGREE, group_classes)
    # NEUTRAL means no change, keep current opinion x

    return x
