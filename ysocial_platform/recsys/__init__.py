"""The recommender systems of the people who use this platform's frontend.

This platform has no content ranking of its own here: what the people of the frontend pick
here is the mode (``modes``) and the accounts to follow (``follow_recsys``). ``RECSYS`` is what the platform hands to
YSocial (``provider.human_recsys``).
"""

from y_web.sdk import HumanRecsysTraits

from .follow_recsys import get_suggested_users  # noqa: F401
from .modes import (  # noqa: F401
    _normalize_content_recsys_mode,
    describe,
    is_supported_content_recsys_mode,
)

RECSYS = HumanRecsysTraits(
    normalize=_normalize_content_recsys_mode,
    is_supported=is_supported_content_recsys_mode,
    describe=describe,
    suggested_users=get_suggested_users,
)
