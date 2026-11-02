"""P14: the agent's LLM decides whether (and where) to cross-post (publish and interaction triggers), with a fake model.
No coordinator, no network, no real LLM."""

import asyncio
import json
import logging
import random
from types import SimpleNamespace

import pytest

from YPhotoSharing import prompt_store
from YPhotoSharing.YClient import federation


DECIDE_KEY = "crosspost_decide"  # not a literal at the call: the call-site ratchet checks the real call sites only
INTERACTION_KEY = "crosspost_decide_interaction"


def _remote(fn):
    return SimpleNamespace(remote=fn)


def _server(dests):
    async def remote(user_id):
        return dests

    return SimpleNamespace(get_federation_destinations=_remote(remote))


class Model:
    """A fake llm_service: `decide_crosspost` answers `reply` (str, exception or function of the text), `adapt_crosspost` adapts."""

    def __init__(self, reply, delay=0.0):
        self.reply, self.calls, self.delay = reply, [], delay
        self.decide_crosspost = _remote(self._decide)
        self.adapt_crosspost = _remote(self._adapt)

    async def _decide(self, trigger, text, lines, name, action, cluster_id, attrs):
        self.calls.append((trigger, text, lines, name, action))
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply(text) if callable(self.reply) else self.reply

    async def _adapt(self, dest, text, source):
        return "adapted " + dest


def _on(dests_mode="agent_action", propensity=1.0, decision="llm", **kw):
    section = dict(enabled=True, seed=3, member="photos", crosspost_mode=dests_mode, crosspost_propensity=propensity, **kw)
    if decision is not None:
        section["crosspost_decision"] = decision
    federation.install({"federation": section})


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def _off():
    yield
    federation.install({})


def post(model, dests=("forum", "dating"), day=1, text="Golden hour at the park"):
    return run(federation.post_fields_async(_server(list(dests)), "u", text, model, day=day))


def test_random_mode_is_bit_identical_and_never_asks():
    out = []
    for decision in (None, "random"):
        _on("coordinator_rule", propensity=0.5, decision=decision)
        model = Model("{}")
        state = random.getstate()
        out.append(([post(model) for _ in range(40)], federation._state["rng"].getstate()))
        assert model.calls == [] and random.getstate() == state
    assert out[0] == out[1]
    ref = random.Random(3)
    assert [bool(f) for f in out[0][0]] == [ref.random() < 0.5 for _ in range(40)]
    _on(propensity=0.5, decision=None)  # agent_action
    ref = random.Random(3)
    want = [d for d in ["dating", "forum"] if ref.random() < 0.5]
    assert [t["member"] for t in post(Model("{}")).get("crosspost_to", [])] == want


def test_the_model_chooses_destinations_and_texts_without_the_generator():
    _on(propensity=0.0)
    model = Model(json.dumps({"crosspost": True, "destinations": ["forum", "myspace", "dating"], "text": {"forum": "Title\nBody"}}))
    before = federation._state["rng"].getstate()
    fields = post(model)
    assert fields == {"crosspost": True, "crosspost_to": [{"member": "dating", "text": "adapted dating"},
                                                           {"member": "forum", "text": "Title\nBody"}]}
    assert len(model.calls) == 1 and model.calls[0][0] == "publish" and "- dating (200)" in model.calls[0][2]
    assert federation._state["rng"].getstate() == before


def test_the_model_says_no_or_names_only_unknown_platforms():
    _on()
    assert post(Model('{"crosspost": false, "destinations": []}')) == {}
    assert post(Model('{"crosspost": true, "destinations": ["myspace"]}')) == {}


def test_coordinator_rule_the_model_only_marks_and_a_share_is_never_offered():
    _on("coordinator_rule", propensity=0.0)
    assert post(Model('{"crosspost": true, "destinations": ["forum"]}')) == {"crosspost": True}
    assert post(Model('{"crosspost": false}')) == {}
    model = Model('{"crosspost": true, "destinations": ["forum"]}')
    assert run(federation.share_fields_async(_server(["forum"]), "u", "words", model, day=1, shared="orig")) == {} and model.calls == []


@pytest.mark.parametrize("reply", ["no json", '{"crosspost": "maybe"}', RuntimeError("down")])
def test_failures_fall_back_to_the_draw(caplog, reply):
    _on("coordinator_rule", propensity=1.0)
    with caplog.at_level(logging.INFO, logger="YPhotoSharing.federation"):
        assert post(Model(reply)) == {"crosspost": True}
    assert "source=fallback" in caplog.text


def test_timeout_falls_back(monkeypatch):
    monkeypatch.setattr(federation, "DECISION_TIMEOUT", 0.05)
    _on("coordinator_rule", propensity=1.0)
    assert post(Model("{}", delay=1.0)) == {"crosspost": True}


def test_cap_per_agent_per_day():
    _on("coordinator_rule", propensity=1.0, crosspost_decision_max_per_day=2)
    model = Model('{"crosspost": false}')
    assert [post(model, day=1) for _ in range(3)] == [{}, {}, {"crosspost": True}] and len(model.calls) == 2
    assert post(model, day=2) == {} and len(model.calls) == 3


def test_rule_based_agent_keeps_the_draw():
    _on("coordinator_rule", propensity=0.5)
    ref = random.Random(3)
    assert [post(None) for _ in range(20)] == [{"crosspost": True} if ref.random() < 0.5 else {} for _ in range(20)]


def test_no_destination_is_not_asked():
    _on()
    model = Model('{"crosspost": true, "destinations": ["forum"]}')
    before = federation._state["rng"].getstate()
    assert post(model, dests=()) == {} and model.calls == [] and federation._state["rng"].getstate() == before


def test_interaction_trigger_on_a_share_and_trigger_selection():
    _on(propensity=0.0)
    model = Model('{"crosspost": true, "destinations": ["forum"], "text": {"forum": "Their photo\\nLovely"}}')
    fields = run(federation.share_fields_async(_server(["forum"]), "u", "my words", model, day=1, shared="their caption"))
    assert fields == {"crosspost": True, "crosspost_to": [{"member": "forum", "text": "Their photo\nLovely"}]}
    assert model.calls[0][0] == "interaction" and model.calls[0][1] == "my words" and model.calls[0][4] == "share"
    _on(propensity=1.0, crosspost_decision_triggers=["publish"])
    model = Model('{"crosspost": false}')
    fields = run(federation.share_fields_async(_server(["forum"]), "u", "my words", model, day=1, shared="x"))
    assert fields["crosspost"] is True and model.calls == []  # interaction not selected: the draw
    _on(propensity=1.0, crosspost_decision_triggers=["interaction"])
    assert post(model)["crosspost"] is True and model.calls == []  # publish not selected: the draw


def test_a_share_without_words_is_decided_on_the_shared_caption():
    _on(propensity=0.0)
    model = Model('{"crosspost": true, "destinations": ["forum"]}')
    fields = run(federation.share_fields_async(_server(["forum"]), "u", "", model, day=1, shared="their caption"))
    assert fields == {"crosspost": True, "crosspost_to": [{"member": "forum", "text": ""}]}
    assert model.calls[0][1] == "their caption"


def test_unknown_decision_is_random(caplog):
    with caplog.at_level(logging.WARNING, logger="YPhotoSharing.federation"):
        _on(decision="oracle")
    assert federation._state["decision"] == "random" and not federation.decision_for("publish")


def test_the_prompts_exist_in_both_languages():
    for lang in ("en", "it"):
        text = prompt_store.prompt(DECIDE_KEY, language=lang, name="u", profile="p", text="SAMPLE",
                                   trigger=prompt_store.get("crosspost_decide_publish", lang), destinations="- forum (2000)")
        assert "SAMPLE" in text and '"crosspost"' in text and "{name}" not in text
