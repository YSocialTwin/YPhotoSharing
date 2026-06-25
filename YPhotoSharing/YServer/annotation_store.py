from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AnnotationStore:
    """In-memory annotation sink used by the rebuilt configuration path."""

    posts: List[Dict[str, Any]] = field(default_factory=list)
    comments: List[Dict[str, Any]] = field(default_factory=list)

    def add_post_annotations(self, post_id: str, annotations: Dict[str, Any]) -> None:
        self.posts.append({"post_id": post_id, **annotations})

    def add_comment_annotations(self, comment_id: str, annotations: Dict[str, Any]) -> None:
        self.comments.append({"comment_id": comment_id, **annotations})

