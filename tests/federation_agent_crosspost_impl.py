"""F6.2: cross-post as an agent action in YPhotoSharing: adapter, server entry point and the async client choice.
No coordinator, no network, no real LLM."""

import asyncio
import json
import random
from pathlib import Path
from types import SimpleNamespace

import pytest

from federation_bus_impl import U, _unwrap, adapter_for, host, new_photo  # noqa: F401
from YPhotoSharing import prompt_store
from YPhotoSharing.YClient import federation
from YPhotoSharing.YServer.federation.adapter import YPhotoSharingAdapter

DEST = {"g1": [{"member": "forum", "local_account_id": "201"}, {"member": "dating", "local_account_id": "301"}],
        "g2": [{"member": "forum", "local_account_id": "202"}]}


def agent_adapter(host, **kw):  # noqa: F811
    a = adapter_for(host, crosspost_mode="agent_action", **kw)
    a.set_destinations(DEST)
    return a


def test_the_agent_sends_a_crosspost_with_its_own_text_to_each_chosen_destination(host):  # noqa: F811
    a = agent_adapter(host)
    pid = new_photo(host, 1, "original")
    a.mark_for_export(pid, [{"member": "forum", "text": "Title\nbody"}, {"member": "dating", "text": "hi there"}])
    out = a.export_outbox(3)
    assert [(e.payload_type, e.target_member, e.payload["target_account_id"], e.payload["text_excerpt"]) for e in out] == [
        ("crosspost.v1", "dating", "301", "hi there"), ("crosspost.v1", "forum", "201", "Title\nbody")]
    assert [e.seq for e in out] == [1, 2]  # seq 0 belongs to the photo itself: no content.v1 is sent for it
    assert out[0].payload["image_ref"] == "https://img/x.jpg" and out[0].payload["source_ref"] == f"ysocial://1/photos/photo/{pid}"
    a.set_destinations({})  # a retry keeps the account fixed at the first export
    assert [e.to_dict() for e in a.export_outbox(3)] == [e.to_dict() for e in out]
    assert a.export_outbox(4) == []


def test_a_destination_without_an_active_account_is_dropped_and_a_plain_mark_still_sends_content(host):  # noqa: F811
    a = agent_adapter(host)
    a.mark_for_export(new_photo(host, 2, "two"), [{"member": "forum", "text": "ok"}, {"member": "dating", "text": "no account"}])
    a.mark_for_export(new_photo(host, 1, "nowhere"), [])
    out = a.export_outbox(3)
    assert sorted((e.payload_type, e.target_member) for e in out) == [("content.v1", "coordinator"), ("crosspost.v1", "forum")]
    assert len({e.seq for e in out}) == len(out)


def test_targets_are_ignored_in_coordinator_rule_mode_and_the_mode_is_validated(host):  # noqa: F811
    a = adapter_for(host)
    a.mark_for_export(new_photo(host, 1, "x"), [{"member": "forum", "text": "t"}])
    assert [(e.payload_type, e.target_member) for e in a.export_outbox(3)] == [("content.v1", "coordinator")]
    with pytest.raises(ValueError):
        YPhotoSharingAdapter("photos", 1, host=host, crosspost_mode="nope")


def test_destination_members(host):  # noqa: F811
    a = agent_adapter(host)
    assert a.destination_members(U[1]) == ["dating", "forum"] and a.destination_members(U[3]) == []


def test_the_server_passes_the_targets_to_the_adapter_and_tells_the_destinations(host):  # noqa: F811
    a = agent_adapter(host)
    srv = SimpleNamespace(_federation_adapter=a, social_action_service=SimpleNamespace(
        post_photo=lambda data: new_photo(host, 1, data["caption"])))
    _unwrap("post_photo")(srv, {"caption": "mine", "crosspost": True, "crosspost_to": [{"member": "forum", "text": "for the forum"}]})
    assert [(e.target_member, e.payload["text_excerpt"]) for e in a.export_outbox(1)] == [("forum", "for the forum")]
    assert _unwrap("get_federation_destinations")(srv, U[1]) == ["dating", "forum"]
    assert _unwrap("get_federation_destinations")(SimpleNamespace(_federation_adapter=None), U[1]) == []


# -- client -----------------------------------------------------------------------------------------------------
def _remote(fn):
    return SimpleNamespace(remote=fn)


def _server(dests):
    async def remote(user_id):
        return dests

    return SimpleNamespace(get_federation_destinations=_remote(remote))


def _llm(reply):
    async def remote(dest, text, source):
        if isinstance(reply, Exception):
            raise reply
        return reply(dest) if callable(reply) else reply

    return SimpleNamespace(adapt_crosspost=_remote(remote))


def _on(propensity=1.0, mode="agent_action"):
    federation.install({"federation": dict(enabled=True, seed=3, member="photos", crosspost_mode=mode, crosspost_propensity=propensity)})


def run(coro):
    return asyncio.run(coro)


def test_client_off_or_other_mode_changes_nothing():
    federation.install({})
    state = random.getstate()
    assert run(federation.post_fields_async(_server(["forum"]), "u", "text")) == {} and random.getstate() == state
    _on(mode="coordinator_rule")
    assert run(federation.post_fields_async(_server(["forum"]), "u", "text")) == {"crosspost": True}  # the old behaviour
    federation.install({})


def test_client_agent_action_chooses_destinations_and_texts():
    _on()
    reply = lambda dest: "from the model" if dest == "dating" else ""  # noqa: E731 - an empty reply falls back to the rule text
    fields = run(federation.post_fields_async(_server(["forum", "dating"]), "u", "A sunny day at the park. Come along.", _llm(reply)))
    assert fields == {"crosspost": True, "crosspost_to": [
        {"member": "dating", "text": "from the model"},
        {"member": "forum", "text": "A sunny day at the park.\nA sunny day at the park. Come along."}]}
    federation.install({})


def test_client_failures_fall_back_and_nothing_to_post_means_no_field():
    _on()
    fields = run(federation.post_fields_async(_server(["dating"]), "u", "caption text", _llm(RuntimeError("down"))))
    assert fields["crosspost_to"] == [{"member": "dating", "text": "caption text"}]
    assert run(federation.post_fields_async(_server([]), "u", "caption text")) == {}
    assert run(federation.post_fields_async(SimpleNamespace(), "u", "caption text")) == {}
    _on(propensity=0.0)
    assert run(federation.post_fields_async(_server(["forum"]), "u", "caption text")) == {}
    federation.install({})


def test_client_one_draw_per_destination_from_its_own_generator():
    _on(propensity=0.5)
    state = random.getstate()
    fields = run(federation.post_fields_async(_server(["forum", "dating", "microblogging"]), "u", "caption text"))
    assert random.getstate() == state
    expected = random.Random(3)
    want = [d for d in ["dating", "forum", "microblogging"] if expected.random() < 0.5]
    assert [t["member"] for t in fields.get("crosspost_to", [])] == want
    federation.install({})


@pytest.mark.parametrize("dest,reply,expected", [
    ("microblogging", '"Great park! #city"', "Great park! #city"),
    ("microblogging", "<think>hm</think>\nPost: nice day out", "nice day out"),
    ("microblogging", "x" * 400, "x" * 280),
    ("microblogging", "  ", None),
    ("forum", "Title: The new park\nIt opened last week. Has anyone been?", "The new park\nIt opened last week. Has anyone been?"),
    ("forum", "", None),
    ("instant_messaging", "«hey, did you see it?»", "hey, did you see it?"),
    ("dating", "y" * 250, "y" * 200),
])
def test_recorded_model_replies_are_parsed(dest, reply, expected):
    assert federation.parse_reply(dest, reply) == expected


def test_the_five_prompts_exist_in_both_languages_and_render():
    root = Path(prompt_store.__file__).parent
    for suffix in ("", ".it"):
        pack = json.loads((root / f"prompts_internal{suffix}.json").read_text(encoding="utf-8"))
        for dest in federation.LIMITS:
            assert f"crosspost_adapt_{dest}" in pack
    for dest in federation.LIMITS:
        for lang in ("en", "it"):
            text = prompt_store.prompt(federation.adapt_prompt_key(dest), language=lang, source_platform="forum", text="SAMPLE")
            assert "SAMPLE" in text and "{" not in text
