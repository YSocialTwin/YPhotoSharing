def get_opinion_group(opinion: float, group_classes: dict) -> str:
    """
    Map a continuous opinion score to a discrete class label based on defined ranges.

    Parameters:
    - opinion (float): The opinion score to classify.
    - group_classes (dict): A mapping of score ranges to class labels.

    Returns:
    - str: The class label corresponding to the opinion score.
    """
    if opinion is None:
        return "unknown"
    for class_label, (lower_bound, upper_bound) in group_classes.items():
        if lower_bound <= opinion < upper_bound or (upper_bound == 1.0 and opinion == 1.0):
            return class_label
    return "unknown"


def ordered_opinion_labels(group_classes: dict) -> list:
    """Return opinion class labels ordered from low to high."""
    if not group_classes:
        return []
    ordered = sorted(group_classes.items(), key=lambda item: item[1][0])
    return [label for label, _ in ordered]


def get_opinion_bounds(group_classes: dict, label: str):
    """Return the numeric bounds for an opinion label if present."""
    if not group_classes:
        return None
    return group_classes.get(label)
