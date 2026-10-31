"""Client side of the federation (F3.4d, opt-in): which agents may act, and the agent's choice to cross-post.

With the `federation` section of the client simulation configuration absent or `enabled: false` every function here does
nothing: no call to the server, no random draw (INV-01).

- inactive_ids(server): ids of the agents that are not active on the platform (dormant or left); the round planner
  leaves them out, so they do not act.
- post_fields(): {"crosspost": True} when this agent chose to cross-post the photo it is publishing (D-07): a Bernoulli
  draw with `federation.crosspost_propensity` (default 0 = never) from a generator of its own (`federation.seed`)."""

from __future__ import annotations

import random

_state = {"enabled": False, "propensity": 0.0, "rng": None, "inactive": set(), "attention": {}}


def install(config):
    """Read config["federation"]; call once when the client starts."""
    section = (config or {}).get("federation") or {}
    enabled = bool(section.get("enabled"))
    _state.update(enabled=enabled, propensity=0.0, rng=None, inactive=set(), attention={})
    if enabled:
        _state.update(propensity=float(section.get("crosspost_propensity", 0.0)), rng=random.Random(section.get("seed", 0)))
    return enabled


def enabled():
    return bool(_state["enabled"])


async def inactive_ids(server):
    """Ids that must not act now (the last known list when the server cannot be reached)."""
    if not _state["enabled"]:
        return set()
    try:
        _state["inactive"] = {str(i) for i in await server.get_federation_inactive_agents.remote()}
    except Exception:  # noqa: BLE001 - keep the last known list
        pass
    return set(_state["inactive"])


async def refresh_attention(server):
    """Read the attention multipliers of the day from the server (the last known ones when it cannot be reached)."""
    if not _state["enabled"]:
        return
    try:
        _state["attention"] = {str(k): float(v) for k, v in (await server.get_federation_attention.remote()).items()}
    except Exception:  # noqa: BLE001 - keep the last known multipliers
        pass


def attention_multiplier(user_id):
    """Attention multiplier of the account (1.0 when the federation is off or it has none)."""
    return _state["attention"].get(str(user_id), 1.0) if _state["enabled"] else 1.0


def skipped_by_attention(user_id):
    """True when an agent that would act for sure (it is in its activity profile) stays out of the round because its
    multiplier is below 1 (draw with the generator of this module, only when the multiplier is not 1)."""
    m = attention_multiplier(user_id)
    return m < 1.0 and _state["rng"].random() >= m


def post_fields():
    """Extra fields of the photo data."""
    if not _state["enabled"] or _state["propensity"] <= 0.0:
        return {}
    return {"crosspost": True} if _state["rng"].random() < _state["propensity"] else {}
