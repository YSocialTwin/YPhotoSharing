"""Client side of the federation (F3.4d, opt-in): which agents may act, and the agent's choice to cross-post.

With the `federation` section of the client simulation configuration absent or `enabled: false` every function here does
nothing: no call to the server, no random draw (INV-01).

- inactive_ids(server): ids of the agents that are not active on the platform (dormant or left); the round planner
  leaves them out, so they do not act.
- post_fields(): {"crosspost": True} when this agent chose to cross-post the photo it is publishing (D-07): a Bernoulli
  draw with `federation.crosspost_propensity` (default 0 = never) from a generator of its own (`federation.seed`)."""

from __future__ import annotations

import random
import re

_state = {"enabled": False, "propensity": 0.0, "rng": None, "inactive": set(), "attention": {},
          "mode": "coordinator_rule", "member": None}

# Longest text each destination accepts (characters); the rules and the parser of an LLM reply both apply them.
LIMITS = {"microblogging": 280, "forum": 2000, "photo_sharing": 300, "instant_messaging": 400, "dating": 200}


def install(config):
    """Read config["federation"]; call once when the client starts."""
    section = (config or {}).get("federation") or {}
    enabled = bool(section.get("enabled"))
    _state.update(enabled=enabled, propensity=0.0, rng=None, inactive=set(), attention={}, mode="coordinator_rule", member=None)
    if enabled:
        _state.update(propensity=float(section.get("crosspost_propensity", 0.0)), rng=random.Random(section.get("seed", 0)),
                      mode=str(section.get("crosspost_mode") or "coordinator_rule"), member=section.get("member"))
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


def agent_action():
    """True when the agent itself chooses where to cross-post and with which text (crosspost.mode = agent_action)."""
    return bool(_state["enabled"]) and _state["mode"] == "agent_action"


async def destinations(server, user_id):
    """Platforms where this agent can post now (the server tells; empty when it cannot be reached)."""
    try:
        return sorted(str(m) for m in await server.get_federation_destinations.remote(str(user_id)))
    except Exception:  # noqa: BLE001 - no destination known: no cross-post this time
        return []


def source_platform():
    return _state["member"] or "another platform"


def adapt_prompt_key(dest):
    """Prompt-store key that adapts a text for the destination platform (None for a platform without one)."""
    return f"crosspost_adapt_{dest}" if dest in LIMITS else None


def _cut(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    return (cut.rsplit(" ", 1)[0] if " " in cut[-30:] else cut).rstrip(",;:- ")


def rule_text(dest, text):
    """The text for the destination without an LLM: the same words, shaped and cut for the platform."""
    text = " ".join(str(text or "").split()) if dest != "forum" else str(text or "").strip()
    if dest == "forum" and "\n" not in text:
        title = _cut(re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0], 80)
        return f"{title}\n{text}"[:LIMITS["forum"]]
    return _cut(text, LIMITS.get(dest, 280))


def parse_reply(dest, reply, fallback=None):
    """Clean the reply of a model asked to adapt a text: no reasoning block, fences, labels or quotes; at most the
    platform limit; for a forum a title line then a body. The fallback (default: nothing) when little is left."""
    text = re.sub(r"<think>.*?</think>", "", str(reply or ""), flags=re.S | re.I)
    text = re.sub(r"^```[a-z]*\n?|```$", "", text.strip(), flags=re.M).strip()
    text = re.sub(r"^(post|caption|message|text|testo|didascalia|messaggio|frase)\s*:\s*", "", text, flags=re.I).strip()
    if len(text) >= 2 and (text[0], text[-1]) in {('"', '"'), ("'", "'"), ("\u201c", "\u201d"), ("\u00ab", "\u00bb")}:
        text = text[1:-1].strip()
    if dest == "forum":
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return fallback
        title = re.sub(r"^(title|titolo)\s*:\s*|^#+\s*", "", lines[0], flags=re.I).strip()
        body = " ".join(re.sub(r"^(body|corpo)\s*:\s*", "", ln, flags=re.I) for ln in lines[1:]).strip()
        if not title:
            return fallback
        return _cut(f"{_cut(title, 120)}\n{body or title}", LIMITS["forum"])
    text = " ".join(text.split())
    if len(text) < 3:
        return fallback
    return _cut(text, LIMITS.get(dest, 280))


async def post_fields_async(server, user_id, text, llm_service=None):
    """Extra fields of the photo data. coordinator_rule: as post_fields(). agent_action: one draw per destination
    (sorted) with `federation.crosspost_propensity`, from the generator of this module, and for each chosen platform
    the model's version of the text (llm_service.adapt_crosspost) or, without a model or on a failed reply, the rule text."""
    if not _state["enabled"] or _state["propensity"] <= 0.0:
        return {}
    if _state["mode"] != "agent_action":
        return post_fields()
    if not str(text or "").strip():
        return {}
    targets = []
    for dest in await destinations(server, user_id):
        if _state["rng"].random() >= _state["propensity"]:
            continue
        version = None
        if llm_service is not None and adapt_prompt_key(dest) is not None:
            try:
                version = parse_reply(dest, await llm_service.adapt_crosspost.remote(dest, text, source_platform()))
            except Exception:  # noqa: BLE001 - a failing model must not stop the post
                version = None
        targets.append({"member": dest, "text": version or rule_text(dest, text)})
    return {"crosspost": True, "crosspost_to": targets} if targets else {}
