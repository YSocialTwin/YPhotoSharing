from __future__ import annotations

import re
from typing import List

_HASHTAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_]+)")
_MENTION_RE = re.compile(r"(?<!\w)@([A-Za-z0-9_.]+)")


def extract_components(text: str, c_type: str) -> List[str]:
    """Extract hashtags or mentions from text in YSimulator-compatible form."""
    text = text or ""
    if c_type == "hashtags":
        return [f"#{match}" for match in _HASHTAG_RE.findall(text)]
    if c_type == "mentions":
        return [f"@{match}" for match in _MENTION_RE.findall(text)]
    raise ValueError(f"Unsupported component type: {c_type}")

