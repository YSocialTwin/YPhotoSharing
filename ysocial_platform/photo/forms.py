"""The photo-sharing fields of the population and agent forms (optional "Platform-specific fields" sections)."""

import hashlib
import json
import random

from y_web.sdk import FormSectionError
from y_web.sdk import gettext as _
from y_web.sdk import runtime
from y_web.sdk.agents import population as standard

KEY = "photo_sharing"
STORY_VISIBILITY = ("public", "followers", "private")
CREATOR_TIERS = ("standard", "pro", "influencer")
DEFAULT_FILTERS = ["warm", "vintage", "mono", "grain", "bright", "clean"]


def available(admin_user) -> bool:
    """Whether the Photo Sharing simulator is installed (and visible to this administrator)."""
    try:
        return bool(runtime.runtime_installed_and_visible(KEY, admin_user))
    except Exception:
        return False


def _percentage_value(raw_value, default=0):
    try:
        return max(0, min(100, int(float(raw_value))))
    except (TypeError, ValueError):
        return int(default)


def _distribution_from_form(form, prefix):
    return {
        "min": form.get(f"{prefix}_min", "1"),
        "max": form.get(f"{prefix}_max", "10"),
        "distribution": form.get(f"{prefix}_distribution", "Uniform"),
        "parameter": form.get(f"{prefix}_distribution_param", ""),
    }


def _json_array(raw_value, default=None):
    if raw_value in (None, ""):
        return list(default or [])
    if isinstance(raw_value, list):
        values = raw_value
    else:
        try:
            values = json.loads(raw_value)
        except (TypeError, ValueError):
            values = [item.strip() for item in str(raw_value).split(",")]
    if not isinstance(values, list):
        return list(default or [])
    cleaned = []
    for value in values:
        text = str(value).strip()
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned or list(default or [])


def _sums_to_100(distribution) -> bool:
    return abs(sum(float(v) for v in distribution.values()) - 100.0) < 0.01


def population_config(form, username_type, admin_user):
    """The photo-sharing section of the population form as a config (``None`` when the section is off)."""
    on = username_type == KEY or (
        form.get("include_photo_sharing") or ""
    ).strip().lower() in {
        "1",
        "on",
        "true",
        "yes",
    }
    if not on:
        return None
    if username_type != KEY and not available(admin_user):
        raise FormSectionError(_("The Photo Sharing simulator is not installed."))

    story_visibility = {
        "public": _percentage_value(form.get("photo_story_public_percentage"), 20),
        "followers": _percentage_value(
            form.get("photo_story_followers_percentage"), 65
        ),
        "private": _percentage_value(form.get("photo_story_private_percentage"), 15),
    }
    creator_tier = {
        "standard": _percentage_value(
            form.get("photo_creator_standard_percentage"), 60
        ),
        "pro": _percentage_value(form.get("photo_creator_pro_percentage"), 25),
        "influencer": _percentage_value(
            form.get("photo_creator_influencer_percentage"), 15
        ),
    }
    config = {
        "is_private_percentage": _percentage_value(
            form.get("photo_is_private_percentage"), 20
        ),
        "is_verified_percentage": _percentage_value(
            form.get("photo_is_verified_percentage"), 10
        ),
        "attention_budget": _distribution_from_form(form, "photo_attention_budget"),
        "favorite_filters": _json_array(
            form.get("photo_favorite_filters"), default=DEFAULT_FILTERS
        ),
        "story_visibility": story_visibility,
        "creator_tier": creator_tier,
    }
    if not _sums_to_100(story_visibility):
        raise FormSectionError(
            _("Photo story visibility percentages must sum to 100%.")
        )
    if not _sums_to_100(creator_tier):
        raise FormSectionError(_("Photo creator tier percentages must sum to 100%."))
    try:
        low = int(config["attention_budget"]["min"])
        high = int(config["attention_budget"]["max"])
    except (TypeError, ValueError):
        raise FormSectionError(
            _("Photo attention budget min/max must be valid integers.")
        )
    if low <= 0 or high <= 0 or low > high:
        raise FormSectionError(
            _(
                "Photo attention budget must use positive min/max values with min <= max."
            )
        )
    return config


def agent_ext_values(agent, config):
    """``(feature name, value)`` pairs of the photo-sharing fields of an agent generated with ``config``."""
    config = config or {}

    def _percentage(name: str, fallback: float) -> float:
        try:
            value = float(config.get(name, fallback))
        except (TypeError, ValueError):
            return float(fallback)
        return max(0.0, min(100.0, value))

    favorite_filters = config.get("favorite_filters") or [
        "warm",
        "vintage",
        "mono",
        "grain",
        "bright",
        "clean",
    ]
    favorite_filters = [
        str(tag).strip() for tag in favorite_filters if str(tag).strip()
    ]
    favorite_filters = list(dict.fromkeys(favorite_filters))
    if favorite_filters:
        max_pick = min(3, len(favorite_filters))
        min_pick = 1 if max_pick > 0 else 0
        selected_filters = random.sample(
            favorite_filters,
            k=random.randint(min_pick, max_pick),
        )
    else:
        selected_filters = []

    attention_budget_config = config.get("attention_budget") or {}
    attention_budget = standard.sample_integer_from_distribution(
        attention_budget_config.get("min", 50),
        attention_budget_config.get("max", 150),
        attention_budget_config.get("parameter"),
        attention_budget_config.get("distribution", "Uniform"),
    )

    story_visibility = standard.weighted_choice(
        config.get("story_visibility"),
        default=["public", "followers", "private"],
    )
    creator_tier = standard.weighted_choice(
        config.get("creator_tier"),
        default=["standard", "pro", "influencer"],
    )

    bio_text = " | ".join(
        part for part in [agent.profession, agent.nationality, agent.language] if part
    )

    return [
        ("bio", bio_text),
        (
            "is_private",
            random.random() < (_percentage("is_private_percentage", 20) / 100.0),
        ),
        (
            "is_verified",
            random.random() < (_percentage("is_verified_percentage", 10) / 100.0),
        ),
        ("attention_budget", attention_budget),
        ("favorite_filters", selected_filters),
        ("story_visibility", story_visibility),
        ("creator_tier", creator_tier),
    ]


def agent_ext(form, admin_user) -> dict:
    """The ``Agent_Ext`` values of the section of the single-agent form (none when it is off)."""
    if not form.get("include_photo_sharing"):
        return {}
    if not available(admin_user):
        raise FormSectionError(_("The Photo Sharing simulator is not installed."))
    ext: dict = {}
    bio = (form.get("photo_bio") or "").strip()
    if bio:
        ext["bio"] = bio
    for name in ("is_private", "is_verified"):
        value = (form.get("photo_" + name) or "").strip()
        if value in ("yes", "no"):
            ext[name] = json.dumps(value == "yes")
    budget = (form.get("photo_attention_budget") or "").strip()
    if budget:
        try:
            number = int(budget)
        except ValueError:
            number = 0
        if number <= 0:
            raise FormSectionError(
                _("Photo attention budget must be a positive integer.")
            )
        ext["attention_budget"] = str(number)
    filters = [
        t.strip()
        for t in (form.get("photo_favorite_filters") or "").split(",")
        if t.strip()
    ]
    if filters:
        ext["favorite_filters"] = json.dumps(list(dict.fromkeys(filters)))
    for name, allowed in (
        ("story_visibility", STORY_VISIBILITY),
        ("creator_tier", CREATOR_TIERS),
    ):
        value = (form.get("photo_" + name) or "").strip()
        if value:
            if value not in allowed:
                raise FormSectionError(
                    _("Photo Sharing: %(field)s has an unknown value.", field=name)
                )
            ext[name] = value
    return ext


def payload_ext(agent_payload):
    """``(feature name, value)`` pairs the photo-sharing runtime reads from an agent of a population file."""
    pairs = [
        (name, agent_payload.get(name))
        for name in ("bio", "is_private", "is_verified", "attention_budget")
    ]
    own = agent_payload.get("photo_sharing") or {}
    if isinstance(own, dict):
        pairs += [
            (name, own.get(name))
            for name in ("favorite_filters", "story_visibility", "creator_tier")
        ]
    return pairs


def default_avatar_url(user):
    """Stock picture of a photo-sharing user that has none (one of the numbered images, by id or a hash of the name)."""
    user_key = str(
        getattr(user, "id", "") or getattr(user, "username", "") or ""
    ).strip()
    if not user_key:
        return ""
    try:
        image_id = str(int(user_key))
    except (TypeError, ValueError):
        hashed = int(hashlib.md5(user_key.encode("utf-8")).hexdigest(), 16)
        image_id = str((hashed % 1000) + 1)
    return f"/static/assets/img/users/{image_id}.png"
