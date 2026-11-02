"""Client side of the federation (F3.4d, opt-in): which agents may act, and the agent's choice to cross-post.

With the `federation` section of the client simulation configuration absent or `enabled: false` every function here does
nothing: no call to the server, no random draw (INV-01).

- inactive_ids(server): ids of the agents that are not active on the platform (dormant or left); the round planner
  leaves them out, so they do not act.
- post_fields(): {"crosspost": True} when this agent chose to cross-post the photo it is publishing (D-07): a Bernoulli
  draw with `federation.crosspost_propensity` (default 0 = never) from a generator of its own (`federation.seed`)."""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import threading

_state = {"enabled": False, "propensity": 0.0, "rng": None, "inactive": set(), "attention": {},
          "mode": "coordinator_rule", "member": None, "peers": {}, "label": None, "adopt": False, "decision": "random",
          "triggers": ("publish", "interaction"), "max_per_day": 5, "content": frozenset(), "counts": {}}

# Longest text each destination accepts (characters); the rules and the parser of an LLM reply both apply them.
LIMITS = {"microblogging": 280, "forum": 2000, "photo_sharing": 300, "instant_messaging": 400, "dating": 200}


def install(config):
    """Read config["federation"]; call once when the client starts."""
    section = (config or {}).get("federation") or {}
    enabled = bool(section.get("enabled"))
    _state.update(enabled=enabled, propensity=0.0, rng=None, inactive=set(), attention={}, mode="coordinator_rule", member=None, peers={}, label=None,
                  adopt=False, decision="random", triggers=("publish", "interaction"), max_per_day=5, content=frozenset(),
                  counts={})
    if enabled:
        _state.update(propensity=float(section.get("crosspost_propensity", 0.0)), rng=random.Random(section.get("seed", 0)),
                      mode=str(section.get("crosspost_mode") or "coordinator_rule"), member=section.get("member"), label=section.get("name"),
                      adopt=bool(section.get("adopt")))
        _state.update(read_decision(section))
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


async def adopt_provisioned(server, client):
    """INV-19: accounts the server created because an agent of another platform decided to join this one get an agent here.

    Only with `federation.adopt` in the client configuration. Each account the server lists (get_federation_provisioned)
    becomes an agent of `client` (`await client.adopt_federated_account(account)` returns it, or None) and is reported as
    adopted; the new agent acts like any other from the next round. Returns the number adopted; never raises for a
    server that cannot be reached."""
    if not (_state["enabled"] and _state["adopt"]):
        return 0
    try:
        accounts = await server.get_federation_provisioned.remote()
    except Exception:  # noqa: BLE001 - try again at the next round
        return 0
    done = []
    for account in accounts:
        if await client.adopt_federated_account(account) is not None:
            done.append(account["user_id"])
    if done:
        try:
            await server.mark_federation_adopted.remote(done)
        except Exception:  # noqa: BLE001 - they are offered again and skipped as already known
            pass
    return len(done)


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
        try:  # P15: member, platform and name of each destination
            info = await server.get_federation_destination_info.remote(str(user_id))
            _learn(info)
            return sorted(str(i["member"]) for i in info)
        except Exception:  # noqa: BLE001 - a server without it: the member names only
            pass
        return sorted(str(m) for m in await server.get_federation_destinations.remote(str(user_id)))
    except Exception:  # noqa: BLE001 - no destination known: no cross-post this time
        return []


def source_platform():
    return _state.get("label") or _state["member"] or "another platform"


def platform_of(dest):
    """Platform type of a destination member (P15: several members may share a type; the member name is then
    `<platform>-<id>`). The server answers it with the destinations; without it the member name is the type (older worlds)."""
    return (_state["peers"].get(str(dest)) or {}).get("platform") or str(dest)


def _learn(items):
    """Remember the platform and the name of each destination the server listed (additive fields `platform`, `name`)."""
    for it in items or ():
        if isinstance(it, dict) and it.get("member") and it.get("platform"):
            _state["peers"][str(it["member"])] = {"platform": str(it["platform"]), "name": str(it.get("name") or it["member"])}


def _destination_line(dest):
    kind = platform_of(dest)
    name = (_state["peers"].get(str(dest)) or {}).get("name")
    if kind == str(dest) and (not name or name == str(dest)):
        return f"- {dest} ({LIMITS.get(kind, 280)})"  # a member named after its type: the line of a single-type world
    return f"- {dest} ({name or dest}, {kind}, {LIMITS.get(kind, 280)})"


def adapt_prompt_key(dest):
    """Prompt-store key that adapts a text for the destination platform (None for a platform without one)."""
    return f"crosspost_adapt_{platform_of(dest)}" if platform_of(dest) in LIMITS else None


def _cut(text, limit):
    text = text.strip()
    if len(text) <= limit:
        return text
    cut = text[:limit].rstrip()
    return (cut.rsplit(" ", 1)[0] if " " in cut[-30:] else cut).rstrip(",;:- ")


def rule_text(dest, text):
    """The text for the destination without an LLM: the same words, shaped and cut for the platform."""
    dest = platform_of(dest)
    text = " ".join(str(text or "").split()) if dest != "forum" else str(text or "").strip()
    if dest == "forum" and "\n" not in text:
        title = _cut(re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0], 80)
        return f"{title}\n{text}"[:LIMITS["forum"]]
    return _cut(text, LIMITS.get(dest, 280))


def parse_reply(dest, reply, fallback=None):
    """Clean the reply of a model asked to adapt a text: no reasoning block, fences, labels or quotes; at most the
    platform limit; for a forum a title line then a body. The fallback (default: nothing) when little is left."""
    dest = platform_of(dest)
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


async def decide_async(server, user_id, text, trigger, ask, own=True, has_image=False, context=None, day=None):
    """The model's decision for one event (see `decide` below for the contract); `ask` is a coroutine function
    `ask(trigger, text, destination_lines, context)`, None for an agent without a model (it keeps the draw)."""
    if not decision_for(trigger) or ask is None or user_id is None or not str(text or "").strip():
        return None
    dests = await destinations(server, user_id)
    early = _precheck(user_id, text, trigger, own, has_image, dests, None, day)
    if early is not None:
        return early
    try:
        reply = await asyncio.wait_for(ask(trigger, text, destination_lines(dests), context), DECISION_TIMEOUT)
    except asyncio.TimeoutError:
        return {"source": "fallback", "reason": "timeout"}
    except Exception as exc:  # noqa: BLE001 - a failing model must not stop the agent
        return _failed(exc)
    return _conclude(user_id, trigger, reply, dests)


def _asker(llm_service, user_id, agent_attrs, cluster_id):
    """The decision call of an agent with a model (llm_service is a Ray actor handle): None without one."""
    if llm_service is None:
        return None

    async def ask(trigger, text, lines, context):
        action = (context or {}).get("action", "share")
        return await llm_service.decide_crosspost.remote(trigger, text, lines, str(user_id), action, cluster_id, agent_attrs)

    return ask


async def _adapt(llm_service, dest, text):
    if llm_service is None or adapt_prompt_key(dest) is None:
        return None
    try:
        return parse_reply(dest, await llm_service.adapt_crosspost.remote(platform_of(dest), text, source_platform()))
    except Exception:  # noqa: BLE001 - a failing model must not stop the post
        return None


async def _decision_targets(decided, text, llm_service, shared=False):
    """The /photo fields for a model decision; the texts the model did not write come from the adaptation prompt, else the rule."""
    if not decided.get("crosspost"):
        return {}
    if _state["mode"] != "agent_action":
        return {"crosspost": True}
    targets = []
    for dest in decided["destinations"]:
        version = decided["text"].get(dest) or (await _adapt(llm_service, dest, text) if text else None)
        targets.append({"member": dest, "text": (version or rule_text(dest, text)) if text else ""})
    return {"crosspost": True, "crosspost_to": targets}


async def post_fields_async(server, user_id, text, llm_service=None, day=None, agent_attrs=None, cluster_id=0):
    """Extra fields of the photo data. coordinator_rule: as post_fields(). agent_action: one draw per destination
    (sorted) with `federation.crosspost_propensity`, from the generator of this module, and for each chosen platform
    the model's version of the text (llm_service.adapt_crosspost) or, without a model or on a failed reply, the rule text.

    With crosspost.decision = llm and a model (`llm_service`) the model decides (trigger `publish`, the photo has an
    image); on any failure the draw above is used."""
    if not _state["enabled"]:
        return {}
    decided = await decide_async(server, user_id, text, "publish", _asker(llm_service, user_id, agent_attrs, cluster_id),
                                 own=True, has_image=True, day=day)
    if decided is not None and decided["source"] != "fallback":
        return await _decision_targets(decided, text, llm_service)
    fields = await _draw_post_fields(server, user_id, text, llm_service)
    if decided is not None:
        note_fallback(user_id, "publish", fields, decided["reason"])
    return fields


async def _draw_post_fields(server, user_id, text, llm_service):
    if _state["propensity"] <= 0.0:
        return {}
    if _state["mode"] != "agent_action":
        return post_fields()
    if not str(text or "").strip():
        return {}
    targets = []
    for dest in await destinations(server, user_id):
        if _state["rng"].random() >= _state["propensity"]:
            continue
        version = await _adapt(llm_service, dest, text)
        targets.append({"member": dest, "text": version or rule_text(dest, text)})
    return {"crosspost": True, "crosspost_to": targets} if targets else {}


async def share_fields_async(server, user_id, text, llm_service=None, day=None, agent_attrs=None, cluster_id=0, shared=None):
    """Extra fields of the photo data of a share (F8): the agent shares the photo of another agent and may choose to
    share it, with its own words, on other platforms. Only with crosspost.mode = agent_action; otherwise nothing is
    drawn and the share stays on this platform. A share without words (no model) still goes: the quotation carries it.

    With crosspost.decision = llm and a model the model decides (trigger `interaction`: `shared` is the caption of the
    photo of the other agent); on any failure the draw is used."""
    if not _state["enabled"] or _state["mode"] != "agent_action":
        return {}
    text = str(text or "").strip()
    candidate = text or str(shared or "").strip()
    decided = await decide_async(server, user_id, candidate, "interaction", _asker(llm_service, user_id, agent_attrs, cluster_id),
                                 own=False, has_image=True, context={"action": "share", "content": shared or text}, day=day)
    if decided is not None and decided["source"] != "fallback":
        return await _decision_targets(decided, text, llm_service)
    fields = await _draw_share_fields(server, user_id, text, llm_service)
    if decided is not None:
        note_fallback(user_id, "interaction", fields, decided["reason"])
    return fields


async def _draw_share_fields(server, user_id, text, llm_service):
    if _state["propensity"] <= 0.0:
        return {}
    targets = []
    for dest in await destinations(server, user_id):
        if _state["rng"].random() >= _state["propensity"]:
            continue
        version = await _adapt(llm_service, dest, text) if text else None
        targets.append({"member": dest, "text": (version or rule_text(dest, text)) if text else ""})
    return {"crosspost": True, "crosspost_to": targets} if targets else {}


# --- P14: the agent decides whether to cross-post (crosspost.decision = llm) --------------------------------------------
# `random` (default) is the Bernoulli draw above, unchanged. With `llm` an LLM agent is asked, ONCE per event, whether to
# cross-post the content it just published (trigger `publish`) or interacted with (trigger `interaction`) and, with
# crosspost.mode = agent_action, towards which platforms. Any failure falls back to the draw, so a run never stalls.
DECISIONS = ("random", "llm")
TRIGGERS = ("publish", "interaction")
DEFAULT_MAX_PER_DAY = 5  # model calls per agent per simulated day (0 = no limit)
DECISION_TIMEOUT = 60.0  # seconds a decision may take before the draw is used instead
ROUNDS_PER_DAY = 24  # World Simulation: simulated clock with hourly slots
URL_RE = re.compile(r"https?://\S+", re.I)
_CONTENT_ALIASES = {"own_posts": "own_content"}
_TRUE = {"true", "yes", "si", "sì", "1"}
_FALSE = {"false", "no", "0"}
log = logging.getLogger("YPhotoSharing.federation")
_lock = threading.Lock()
_stats = {"llm": 0, "fallback": 0, "skipped": 0, "crossposts_llm": 0}


def decision_stats():
    """Counters of this process: decisions taken by the model, fallbacks to the draw, skipped events and cross-posts the model chose."""
    return dict(_stats)


def _content_options(content):
    names = {_CONTENT_ALIASES.get(str(c), str(c)) for c in (content or ())}
    return frozenset() if (not names or "all" in names) else frozenset(names)


def _eligible(text, own=True, has_image=False):
    """Client-side view of crosspost.content (the coordinator stays the authority): False only when the agent's OWN content
    can certainly not be eligible. The content of others is left to the coordinator (it knows the link and the image)."""
    opts = _state["content"]
    if not opts or not own or "own_content" in opts:
        return True
    return ("news" in opts and bool(URL_RE.search(str(text or "")))) or ("images" in opts and bool(has_image))


def parse_decision(reply, allowed):
    """The decision in a model reply: {"crosspost": bool, "destinations": [allowed names, in the order of `allowed`],
    "text": {destination: cleaned text}}, or None when there is no valid JSON object with a boolean `crosspost`.
    Unknown destinations are ignored; texts are cleaned and cut like an adaptation (`parse_reply`)."""
    raw = re.sub(r"<think>.*?</think>", "", str(reply or ""), flags=re.S | re.I)
    decoder, obj = json.JSONDecoder(), None
    for match in re.finditer(r"\{", raw):
        try:
            found, _ = decoder.raw_decode(raw[match.start():])
        except ValueError:
            continue
        if isinstance(found, dict) and "crosspost" in found:
            obj = found
            break
    if obj is None:
        return None
    flag = obj["crosspost"]
    if isinstance(flag, str):
        flag = True if flag.strip().lower() in _TRUE else False if flag.strip().lower() in _FALSE else None
    if not isinstance(flag, bool):
        return None
    asked = obj.get("destinations")
    asked = [str(d).strip().lower() for d in asked] if isinstance(asked, list) else []
    dests = [d for d in allowed if d in asked]
    texts = obj.get("text") if isinstance(obj.get("text"), dict) else {}
    out = {}
    for dest in dests:
        value = next((v for k, v in texts.items() if str(k).strip().lower() == dest), None)
        cleaned = parse_reply(dest, value) if isinstance(value, str) else None
        if cleaned:
            out[dest] = cleaned
    return {"crosspost": flag, "destinations": dests, "text": out}


def destination_lines(dests):
    """The destinations as lines for the prompt: `- forum (2000)`, the number being the longest text in characters."""
    return "\n".join(_destination_line(d) for d in dests)


def _note(user_id, trigger, source, crosspost, dests, reason=""):
    """One log line per decision, the record YWeb analytics read: `federation_decision agent=.. trigger=.. source=llm|fallback
    crosspost=0|1 destinations=a,b [reason=..]`. For `fallback` the crosspost value is the outcome of the Bernoulli draw."""
    _stats[source] += 1
    if crosspost and source == "llm":
        _stats["crossposts_llm"] += 1
    log.info("federation_decision agent=%s trigger=%s source=%s crosspost=%d destinations=%s%s", user_id, trigger, source,
             1 if crosspost else 0, ",".join(dests), f" reason={reason}" if reason else "")


def note_fallback(user_id, trigger, fields, reason):
    """Log a decision that fell back to the Bernoulli draw (`fields` are the ones the draw produced) and say why."""
    to = [t["member"] for t in fields.get("crosspost_to", [])]
    _note(user_id, trigger, "fallback", bool(fields.get("crosspost")), to, reason)


def decision_for(trigger):
    """True when this event is decided by the model: crosspost.decision = llm and the trigger is selected."""
    return bool(_state["enabled"]) and _state["decision"] == "llm" and trigger in _state["triggers"]


def _precheck(user_id, text, trigger, own, has_image, dests, round_id, day):
    """What can be said before asking the model: {"source": "skip"} (no destination, content not eligible: nothing to do),
    {"source": "fallback", "reason": "cap"} (the agent used its calls of the day) or None (ask the model)."""
    if not dests or not _eligible(text, own, has_image):
        _stats["skipped"] += 1
        return {"source": "skip", "crosspost": False, "destinations": [], "text": {}}
    cap = int(_state["max_per_day"])
    try:  # the simulated day: given (clients that know it) or derived from the round id (hourly slots)
        which = int(day) if day is not None else (int(round_id) // ROUNDS_PER_DAY if round_id is not None else None)
    except (TypeError, ValueError):
        which = None
    if cap > 0 and which is not None:
        with _lock:
            if _state["counts"].get((user_id, which), 0) >= cap:
                return {"source": "fallback", "reason": "cap"}
            _state["counts"] = {k: v for k, v in _state["counts"].items() if k[1] >= which - 1}  # keep today and yesterday
            _state["counts"][(user_id, which)] = _state["counts"].get((user_id, which), 0) + 1
    return None


def _failed(exc):
    return {"source": "fallback", "reason": "timeout" if isinstance(exc, TimeoutError) else f"error:{type(exc).__name__}"}


def _conclude(user_id, trigger, reply, dests):
    """The decision in the reply of the model (see `decide`); a reply that cannot be read is a fallback."""
    parsed = parse_decision(reply, dests)
    if parsed is None:
        return {"source": "fallback", "reason": "invalid"}
    if _state["mode"] == "agent_action":  # the model chooses the destinations; none valid means no cross-post
        parsed["crosspost"] = bool(parsed["crosspost"] and parsed["destinations"])
    else:  # coordinator_rule: the model only marks the content, the coordinator's probabilities choose where it goes
        parsed["destinations"], parsed["text"] = [], {}
    _note(user_id, trigger, "llm", parsed["crosspost"], parsed["destinations"])
    return dict(parsed, source="llm")


def read_decision(section):
    """The decision settings of a member `federation` section (invalid values are logged and mean the default)."""
    decision = str(section.get("crosspost_decision") or "random")
    if decision not in DECISIONS:
        log.warning("federation: unknown crosspost_decision %r, using 'random'", decision)
        decision = "random"
    asked = section.get("crosspost_decision_triggers")
    triggers = tuple(t for t in TRIGGERS if t in asked) if isinstance(asked, (list, tuple)) else TRIGGERS
    try:
        cap = max(0, int(section.get("crosspost_decision_max_per_day", DEFAULT_MAX_PER_DAY)))
    except (TypeError, ValueError):
        cap = DEFAULT_MAX_PER_DAY
    return {"decision": decision, "triggers": triggers, "max_per_day": cap,
            "content": _content_options(section.get("crosspost_content")), "counts": {}}
