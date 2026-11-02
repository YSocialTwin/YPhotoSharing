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


# -- F8: sharing the photo of another agent ---------------------------------------------------------------
def new_share(host, n, parent, caption=""):  # noqa: F811
    import uuid

    pid = str(uuid.uuid4())
    host._db.create_photo({"id": pid, "user_id": U[n], "round": host.current_round_id, "image_url": "https://img/x.jpg",
                           "caption": caption, "parent_photo_id": parent, "topics": []})
    return pid


def test_a_marked_share_leaves_as_a_crosspost_quoting_the_original_author(host):  # noqa: F811
    a = agent_adapter(host)
    original = new_photo(host, 2, "words of the second agent")
    share = new_share(host, 1, original, "so true")
    a.mark_for_export(share, [{"member": "forum", "text": "so true"}])
    out = a.export_outbox(3)
    assert [(e.payload_type, e.target_member, e.payload["global_agent_id"], e.payload["text_excerpt"]) for e in out] == [
        ("crosspost.v1", "forum", "g1", "so true")]
    q = out[0].payload["quoted"]
    assert q["global_agent_id"] == "g2" and q["member"] == "photos" and q["text_excerpt"] == "words of the second agent"
    assert q["source_ref"] == f"ysocial://1/photos/photo/{original}"


def test_an_unmarked_share_and_a_share_in_coordinator_rule_mode_never_leave(host):  # noqa: F811
    a = agent_adapter(host)
    original = new_photo(host, 2, "words")
    new_share(host, 1, original, "plain")
    assert a.export_outbox(3) == []
    b = adapter_for(host)
    b.mark_for_export(new_share(host, 1, original, "marked"), [{"member": "forum", "text": "t"}])
    assert b.export_outbox(4) == []


def test_an_author_outside_the_identity_map_is_quoted_as_anonymous(host):  # noqa: F811
    a = agent_adapter(host)
    original = new_photo(host, 3, "from a non member")
    a._by_user.pop(U[3], None)
    a.mark_for_export(new_share(host, 1, original, "look"), [{"member": "forum", "text": "look"}])
    q = a.export_outbox(3)[0].payload["quoted"]
    assert q["global_agent_id"] is None and q["source_ref"] is None


def test_the_destination_writes_the_caption_with_the_attribution_and_keeps_the_reference(host):  # noqa: F811
    from ysocial_federation.envelope import Envelope
    from YPhotoSharing.YServer.classes.models import Photo
    from YPhotoSharing.YServer.federation.tables import FederationQuoted

    a = agent_adapter(host)
    q = {"author_name": "ann", "global_agent_id": "gx", "member": "forum", "source_ref": "ysocial://1/forum/post/4",
         "text_excerpt": "original words"}
    env = Envelope.create(1, "forum", "photos", 2, 0, "crosspost.v1",
                          {"global_agent_id": "g1", "source_ref": "ysocial://1/forum/post/7", "kind": "post", "text_excerpt": "agreed",
                           "image_ref": "https://img/z.jpg", "topics": [], "lang": "en", "target_account_id": U[1], "quoted": q})
    assert a.ingest_inbox(3, [env]).materialized == 1
    with a._session() as s:
        photo = s.query(Photo).filter(Photo.image_url == "https://img/z.jpg").one()
        assert photo.caption == "agreed\n↪ ann @ forum: «original words»"
        row = s.get(FederationQuoted, photo.id)
        assert (row.author_name, row.global_agent_id, row.member, row.source_ref) == ("ann", "gx", "forum", "ysocial://1/forum/post/4")


def test_client_share_fields_only_in_agent_action_and_a_wordless_share_still_goes():
    federation.install({})
    state = random.getstate()
    assert run(federation.share_fields_async(_server(["forum"]), "u", "text")) == {} and random.getstate() == state
    _on(mode="coordinator_rule")
    assert run(federation.share_fields_async(_server(["forum"]), "u", "text")) == {}  # no draw, shares stay local
    _on()
    fields = run(federation.share_fields_async(_server(["forum", "dating"]), "u", "nice one", _llm(lambda d: "from the model" if d == "dating" else "")))
    assert fields["crosspost_to"] == [{"member": "dating", "text": "from the model"}, {"member": "forum", "text": "nice one\nnice one"}]
    assert run(federation.share_fields_async(_server(["forum"]), "u", "")) == {"crosspost": True, "crosspost_to": [{"member": "forum", "text": ""}]}
    federation.install({})


# -- topic migration -------------------------------------------------------------------------------------
def _topic_env(topics, seq=0, source="forum"):
    from ysocial_federation.envelope import Envelope

    return Envelope.create(1, source, "photos", 2, seq, "crosspost.v1",
                           {"global_agent_id": "g1", "source_ref": f"ysocial://1/{source}/post/{seq + 50}", "kind": "post",
                            "text_excerpt": "hi", "image_ref": f"https://img/t{seq}.jpg", "topics": topics, "lang": "en",
                            "target_account_id": U[1]})


def test_a_share_exports_the_topics_of_the_original(host):  # noqa: F811
    a = agent_adapter(host)
    original = new_photo(host, 2, "about cats", topics=["Cats", "pets"])
    share = new_share(host, 1, original, "so true")
    a.mark_for_export(share, [{"member": "forum", "text": "so true"}])
    assert a.export_outbox(3)[0].payload["topics"] == ["Cats", "pets"]


def test_ingest_attaches_existing_topics_case_insensitively_and_creates_missing_ones_once(host):  # noqa: F811
    from sqlalchemy import func, select
    from YPhotoSharing.YServer.classes.models import Interest, PhotoTopic
    from YPhotoSharing.YServer.federation.tables import FederationTopic

    a = agent_adapter(host)
    new_photo(host, 2, "seed", topics=["Cats"])
    assert a.ingest_inbox(3, [_topic_env(["cats", "Dogs", "DOGS", "  "], 0), _topic_env(["dogs", "Birds"], 1, source="micro")]).materialized == 2
    with a._session() as s:
        names = sorted(i.interest for i in s.scalars(select(Interest)).all())
        assert names == ["Birds", "Cats", "Dogs"]  # "cats" reused "Cats"; "DOGS" and "dogs" reused "Dogs"
        assert s.scalar(select(func.count()).select_from(PhotoTopic)) == 1 + 2 + 2
        made = {t.name: (t.created_tick, t.source_member) for t in s.scalars(select(FederationTopic)).all()}
        assert made == {"Dogs": (3, "forum"), "Birds": (3, "micro")}
    assert a.ingest_inbox(3, [_topic_env(["cats", "Dogs", "DOGS", "  "], 0)]).duplicates == 1  # INV-05: nothing more is created


# -- P3: the exposure of the agent to the foreign content it quotes ---------------------------------------
def _foreign_share(host, emit=True):  # noqa: F811
    from federation_bus_impl import crosspost
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from YPhotoSharing.YServer.federation.tables import FederationRef

    a = agent_adapter(host, emit_exposures=emit)
    assert a.ingest_inbox(0, [crosspost(0, U[1], "from the forum")]).materialized == 1
    with Session(host._db.engine) as s:
        foreign = s.scalar(select(FederationRef.local_id).where(FederationRef.local_kind == "photo"))
    share = new_share(host, 2, foreign, "worth a look")
    a.mark_for_export(share, [{"member": "forum", "text": "worth a look"}])
    return a


def test_quoting_foreign_content_sends_the_exposure_first_and_a_retry_is_identical(host):  # noqa: F811
    a = _foreign_share(host)
    out = a.export_outbox(3)
    kinds = [e.payload_type for e in out]
    assert kinds.index("exposure.v1") < kinds.index("crosspost.v1")
    exp = next(e for e in out if e.payload_type == "exposure.v1")
    assert (exp.payload["viewer_global_agent_id"], exp.payload["source_ref"], exp.payload["kind"], exp.payload["exact"]) == (
        "g2", "ysocial://1/forum/post/0", "interact", True)
    assert exp.payload["tick"] == 3 and exp.target_member == "coordinator" and len({e.seq for e in out}) == len(out)
    again = a.export_outbox(3)
    assert [e.fed_msg_id for e in again] == [e.fed_msg_id for e in out] and [e.payload for e in again] == [e.payload for e in out]
    assert a.export_outbox(4) == []


def test_the_exposure_is_not_repeated_when_the_agent_already_has_one(host):  # noqa: F811
    from sqlalchemy.orm import Session
    from YPhotoSharing.YServer.federation.tables import FederationExposure

    a = _foreign_share(host)
    with Session(host._db.engine) as s:
        s.add(FederationExposure(tick=2, seq=0, viewer_uid=U[2], source_ref="ysocial://1/forum/post/0", kind="view", tie="none", exact=0))
        s.commit()
    assert [e for e in a.export_outbox(3) if e.payload_type == "exposure.v1"] == []


def test_without_emit_exposures_and_for_native_quotes_no_exposure(host):  # noqa: F811
    assert [e.payload_type for e in _foreign_share(host, emit=False).export_outbox(3)] == ["crosspost.v1"]


def test_quoting_native_content_sends_no_exposure(host):  # noqa: F811
    a = agent_adapter(host, emit_exposures=True)
    a.mark_for_export(new_share(host, 1, new_photo(host, 2, "native"), "so true"), [{"member": "forum", "text": "so true"}])
    assert [e.payload_type for e in a.export_outbox(3)] == ["crosspost.v1"]


# -- P15: several members of the same platform type ------------------------------------------------------------
INFO = [{"member": "microblogging-1", "platform": "microblogging", "name": "Alpha"},
        {"member": "microblogging-2", "platform": "microblogging", "name": "Beta"},
        {"member": "forum", "platform": "forum", "name": "forum"}]


def test_p15_the_client_learns_platform_and_name_of_each_member():
    async def info(user_id):
        return INFO

    server = SimpleNamespace(get_federation_destination_info=_remote(info))
    federation.install({"federation": dict(enabled=True, seed=3, member="photos", name="Photos exp")})
    assert run(federation.destinations(server, "u")) == ["forum", "microblogging-1", "microblogging-2"]
    assert federation.platform_of("microblogging-2") == "microblogging"
    assert federation.adapt_prompt_key("microblogging-1") == "crosspost_adapt_microblogging"
    assert "Beta" in federation._destination_line("microblogging-2")
    federation.install({})


def test_p15_a_server_without_the_new_method_still_works():
    federation.install({"federation": dict(enabled=True, seed=3, member="photos")})
    assert run(federation.destinations(_server(["forum", "dating"]), "u")) == ["dating", "forum"]
    assert federation.platform_of("forum") == "forum"
    federation.install({})


def test_p15_the_server_and_adapter_report_platform_and_name(host):  # noqa: F811
    a = agent_adapter(host)
    a.set_destinations({"g1": [{"member": "microblogging-1", "local_account_id": "1", "platform": "microblogging", "name": "Alpha"},
                               {"member": "microblogging-2", "local_account_id": "2", "platform": "microblogging", "name": "Beta"}]})
    assert a.destination_members(U[1]) == ["microblogging-1", "microblogging-2"]
    assert [(i["member"], i["platform"], i["name"]) for i in a.destination_info(U[1])] == [
        ("microblogging-1", "microblogging", "Alpha"), ("microblogging-2", "microblogging", "Beta")]
