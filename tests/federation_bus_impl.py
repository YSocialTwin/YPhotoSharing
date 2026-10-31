"""Bus and membership of the YPhotoSharing server and client (F3.4d): export, ingest, membership, invisibility,
cross-post choice. No coordinator, no network."""

import asyncio
import inspect
import random
import sys
import types
import uuid
from types import SimpleNamespace

import pytest

try:  # the annotation stack is optional in this environment; the bus does not use it
    import detoxify  # noqa: F401
except ImportError:
    stub = types.ModuleType("detoxify")
    stub.Detoxify = object
    sys.modules["detoxify"] = stub

pytest.importorskip("ysocial_federation", reason="the federation SDK is not installed")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from ysocial_federation.envelope import Envelope  # noqa: E402
from ysocial_federation.schemas import MembershipChange  # noqa: E402

from YPhotoSharing.YClient import federation as client_fed  # noqa: E402
from YPhotoSharing.YClient.simulation.round_planner import SimulationRoundPlanner  # noqa: E402
from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware  # noqa: E402
from YPhotoSharing.YServer.classes.models import Interest, Photo, PhotoTopic, User_mgmt  # noqa: E402
from YPhotoSharing.YServer.federation.adapter import YPhotoSharingAdapter  # noqa: E402
from YPhotoSharing.YServer.federation.tables import FederationMembership, FederationRef  # noqa: E402
from YPhotoSharing.YServer.server import OrchestratorServer  # noqa: E402

CLASS = getattr(OrchestratorServer, "__ray_actor_class__", OrchestratorServer)
U = {n: f"user-{n}" for n in (1, 2, 3)}


def _unwrap(name):
    return inspect.unwrap(getattr(CLASS, name))


@pytest.fixture()
def host(tmp_path):
    db = DatabaseMiddleware({"type": "sqlite", "sqlite": {"filename": "t.db"}}, tmp_path)
    for n, uid in U.items():
        db.create_user({"id": uid, "username": f"u{n}", "language": "it" if n == 2 else "en"})
    round_id = db.get_or_create_round(0, 0)
    return SimpleNamespace(_db=db, current_round_id=round_id, _current_day=0, _current_hour=0)


def adapter_for(host, **kw):
    return YPhotoSharingAdapter("photos", 1, host=host, accounts={f"g{n}": u for n, u in U.items()}, **kw)


def new_photo(host, n, caption, topics=(), image="https://img/x.jpg"):
    pid = str(uuid.uuid4())
    host._db.create_photo({"id": pid, "user_id": U[n], "round": host.current_round_id, "image_url": image,
                           "caption": caption, "topics": list(topics)})
    return pid


def crosspost(seq, target, text="hello", topics=(), image="https://img/y.jpg", tick=4):
    return Envelope.create(1, "forum", "photos", tick, seq, "crosspost.v1",
                           {"global_agent_id": "g9", "source_ref": f"ysocial://1/forum/post/{seq}", "kind": "post",
                            "text_excerpt": text, "image_ref": image, "topics": list(topics), "lang": "en",
                            "target_account_id": target})


def test_export_only_marked_photos_with_a_stable_retry(host):
    a = adapter_for(host)
    new_photo(host, 1, "not marked")
    p2 = new_photo(host, 2, "marked two", topics=("sport",))
    p1 = new_photo(host, 1, "marked one")
    a.mark_for_export(p2)
    a.mark_for_export(p1)
    out = a.export_outbox(3)
    assert [(e.seq, e.payload["text_excerpt"], e.payload["global_agent_id"], e.payload["kind"]) for e in out] == [
        (0, "marked one", "g1", "photo"), (1, "marked two", "g2", "photo")]
    assert out[1].payload["lang"] == "it" and out[1].payload["topics"] == ["sport"]
    assert out[0].payload["image_ref"] == "https://img/x.jpg"
    assert out[0].payload["source_ref"] == f"ysocial://1/photos/photo/{p1}" and out[0].target_member == "coordinator"
    assert [e.fed_msg_id for e in a.export_outbox(3)] == [e.fed_msg_id for e in out]  # retry of the same tick
    assert a.export_outbox(4) == []  # exported once


def test_export_all_policy_takes_the_photos_of_the_round_but_not_dormant_or_federated(host):
    a = adapter_for(host, export_policy="all")
    new_photo(host, 1, "new photo")
    new_photo(host, 3, "dormant author")
    a.apply_membership([MembershipChange("g3", "dormant", 0, "initial")])
    assert a.ingest_inbox(2, [crosspost(0, U[2])]).materialized == 1  # a federated photo is never sent back
    assert [e.payload["text_excerpt"] for e in a.export_outbox(5)] == ["new photo"]


def test_a_marked_photo_of_a_dormant_author_is_not_exported(host):
    a = adapter_for(host)
    p = new_photo(host, 3, "x")
    a.mark_for_export(p)
    a.apply_membership([MembershipChange("g3", "left", 0, "churn")])
    assert a.export_outbox(1) == []


def test_ingest_materialises_a_photo_once_with_topics_and_a_reference(host):
    a = adapter_for(host)
    inbox = [crosspost(0, U[1], "from the forum", topics=["music", "chess"]), crosspost(1, U[2], "second")]
    r1 = a.ingest_inbox(5, inbox)
    assert (r1.materialized, r1.duplicates, r1.skipped_total) == (2, 0, 0)
    r2 = a.ingest_inbox(5, inbox)  # INV-05
    assert (r2.materialized, r2.duplicates) == (0, 2)
    with Session(host._db.engine) as s:
        photos = {p.caption: p for p in s.scalars(select(Photo)).all()}
        p = photos["from the forum"]
        assert p.user_id == U[1] and p.image_url == "https://img/y.jpg" and p.round == host.current_round_id
        names = sorted(i.interest for i in s.scalars(select(Interest).join(PhotoTopic, PhotoTopic.topic_id == Interest.iid)
                                                     .where(PhotoTopic.photo_id == p.id)).all())
        assert names == ["chess", "music"]
        refs = {r.fed_msg_id: (r.local_kind, r.source_ref) for r in s.scalars(select(FederationRef)).all()}
        assert refs == {inbox[0].fed_msg_id: ("photo", "ysocial://1/forum/post/0"),
                        inbox[1].fed_msg_id: ("photo", "ysocial://1/forum/post/1")}


def test_ingest_skips_text_only_unknown_dormant_and_unsupported(host):
    a = adapter_for(host)
    a.apply_membership([MembershipChange("g2", "dormant", 0, "initial")])
    content = Envelope.create(1, "forum", "photos", 4, 9, "content.v1",
                              {"global_agent_id": "g1", "source_ref": "ysocial://1/forum/post/9", "kind": "post",
                               "text_excerpt": "x", "image_ref": None, "topics": [], "lang": "en"})
    r = a.ingest_inbox(5, [crosspost(0, U[1], image=None), crosspost(1, U[2]), crosspost(2, "nobody"), content,
                           crosspost(3, U[3])])
    assert r.materialized == 1 and r.skipped == {"skipped_no_image": 1, "skipped_ineligible": 2, "skipped_unsupported": 1}


def test_membership_is_stored_and_updated(host):
    a = adapter_for(host)
    a.apply_membership([MembershipChange("g1", "dormant", 0, "initial"), MembershipChange("g2", "active", 0, "initial")])
    a.apply_membership([MembershipChange("g1", "active", 24, "join")])
    with Session(host._db.engine) as s:
        rows = {r.user_id: (r.state, r.since_tick, r.reason) for r in s.scalars(select(FederationMembership)).all()}
    assert rows == {U[1]: ("active", 24, "join"), U[2]: ("active", 0, "initial")}
    a.apply_membership([MembershipChange("g2", "left", 48, "churn")])
    assert a.inactive_agent_ids() == {U[2]}
    assert adapter_for(host).inactive_agent_ids() == {U[2]}  # a new adapter (server restart) reads the table


def test_dormant_accounts_are_invisible_in_the_server_answers(host):
    a = adapter_for(host)
    p1, p2 = new_photo(host, 1, "visible"), new_photo(host, 2, "hidden")
    a.apply_membership([MembershipChange("g2", "dormant", 0, "initial")])
    assert a.filter_photo_ids([p2, p1]) == [p1] and a.filter_users([U[1], U[2], U[3]]) == [U[1], U[3]]
    assert [p["id"] for p in a.filter_photos([{"id": "a", "user_id": U[2]}, {"id": "b", "user_id": U[1]}])] == ["b"]

    seen = {}

    def feed(user_id, limit=30, **kw):
        seen["limit"] = limit
        return [{"id": "h", "user_id": U[2]}, {"id": "v", "user_id": U[1]}]

    srv = SimpleNamespace(
        _federation_adapter=a,
        _db=SimpleNamespace(get_home_feed=feed, get_explore_feed=feed, get_hashtag_feed=lambda h, limit: feed(h, limit),
                            get_recommendation=lambda u, r: [p2, p1]),
        social_action_service=SimpleNamespace(get_user_photos=lambda *a, **k: feed(None), get_recent_stories=lambda *a: feed(None)),
        follow_recsys=SimpleNamespace(recommend_users_to_follow=lambda u, n: [U[2], U[3]]))
    ids = lambda rows: [r["id"] for r in rows]  # noqa: E731
    assert ids(_unwrap("get_home_feed")(srv, U[3], limit=2)) == ["v"] and seen["limit"] == 4  # asked for more, then cut
    assert ids(_unwrap("get_explore_feed")(srv, U[3], 2)) == ["v"]
    assert ids(_unwrap("get_hashtag_feed")(srv, "x", 2)) == ["v"]
    assert ids(_unwrap("get_user_photos")(srv, U[2])) == ["v"] and ids(_unwrap("get_recent_stories")(srv, U[3])) == ["v"]
    assert _unwrap("get_recommendation")(srv, U[3], "r") == [p1]
    assert _unwrap("get_follow_recommendations")(srv, U[1]) == [U[3]]
    assert _unwrap("get_federation_inactive_agents")(srv) == [U[2]]
    srv._federation_adapter = None  # standalone: untouched
    assert ids(_unwrap("get_home_feed")(srv, U[3], limit=2)) == ["h", "v"]
    assert _unwrap("get_recommendation")(srv, U[3], "r") == [p2, p1]
    assert _unwrap("get_follow_recommendations")(srv, U[1]) == [U[2], U[3]]
    assert _unwrap("get_federation_inactive_agents")(srv) == []


def test_post_photo_marks_the_photo_the_agent_chose_to_cross_post(host):
    a = adapter_for(host)
    posted = []
    srv = SimpleNamespace(_federation_adapter=a, social_action_service=SimpleNamespace(
        post_photo=lambda data: posted.append(dict(data)) or new_photo(host, 1, data["caption"])))
    data = {"caption": "mine", "crosspost": True}
    pid = _unwrap("post_photo")(srv, data)
    assert "crosspost" not in posted[0] and data == {"caption": "mine", "crosspost": True}  # caller's dict untouched
    assert [e.payload["source_ref"] for e in a.export_outbox(1)] == [f"ysocial://1/photos/photo/{pid}"]
    _unwrap("post_photo")(srv, {"caption": "plain"})
    _unwrap("post_photo")(SimpleNamespace(_federation_adapter=None, social_action_service=srv.social_action_service),
                          {"caption": "x", "crosspost": True})  # standalone: the key is dropped, nothing is marked
    assert a.export_outbox(2) == []


def test_conformance_suite(host):
    from ysocial_federation.testing.conformance import ConformanceCase, run_all

    def sample_inbox(a, tick):
        return [Envelope.create(1, "forum", "photos", tick - 1, seq, "crosspost.v1",
                                {"global_agent_id": "g1", "source_ref": f"ysocial://1/forum/post/{tick}-{seq}", "kind": "post",
                                 "text_excerpt": "x", "image_ref": "https://img/z.jpg", "topics": [], "lang": "en",
                                 "target_account_id": U[1]})
                for seq in range(3)]

    case = ConformanceCase(lambda: adapter_for(host), (0, 0), lambda r: (r[0], r[1] + 1) if r[1] < 23 else (r[0] + 1, 0),
                           "photos", 1, agent_ids=["g1", "g2"], sample_inbox=sample_inbox)
    assert "ingest_is_idempotent" in run_all(case)


# -- client ---------------------------------------------------------------------------------
def test_client_is_off_by_default_and_draws_nothing():
    client_fed.install({})
    state = random.getstate()
    assert client_fed.post_fields() == {} and not client_fed.enabled()
    assert asyncio.run(client_fed.inactive_ids(object())) == set() and random.getstate() == state
    client_fed.install({"federation": {"enabled": False, "crosspost_propensity": 1.0}})
    assert client_fed.post_fields() == {}


def test_client_inactive_ids_come_from_the_server_and_the_last_list_is_kept():
    client_fed.install({"federation": {"enabled": True}})
    calls = {"n": 0}

    async def remote():
        calls["n"] += 1
        if calls["n"] > 1:
            raise OSError("down")
        return ["a", "b"]

    server = SimpleNamespace(get_federation_inactive_agents=SimpleNamespace(remote=remote))
    assert asyncio.run(client_fed.inactive_ids(server)) == {"a", "b"}
    assert asyncio.run(client_fed.inactive_ids(server)) == {"a", "b"}
    client_fed.install({})


def test_round_planner_leaves_out_the_excluded_agents():
    agents = [SimpleNamespace(user_data={"id": i, "daily_activity_level": 1, "activity_profile": "p"}) for i in "abc"]
    planner = SimulationRoundPlanner({"activity_profiles": {"p": list(range(24))}})
    assert [a.user_data["id"] for a in planner.select_active_agents(agents, 3)] == ["a", "b", "c"]
    planner.excluded_ids = {"b"}
    assert [a.user_data["id"] for a in planner.select_active_agents(agents, 3)] == ["a", "c"]


def test_crosspost_choice_is_a_seeded_draw_with_its_own_generator():
    def run():
        client_fed.install({"federation": {"enabled": True, "crosspost_propensity": 0.5, "seed": 3}})
        state = random.getstate()
        out = [bool(client_fed.post_fields()) for _ in range(40)]
        assert random.getstate() == state  # the global generator is not touched
        return out

    first = run()
    assert first == run() and 5 < sum(first) < 35
    client_fed.install({"federation": {"enabled": True, "crosspost_propensity": 1.0}})
    assert client_fed.post_fields() == {"crosspost": True}
    client_fed.install({"federation": {"enabled": True}})
    assert client_fed.post_fields() == {}
    client_fed.install({})


def test_affective_report_equals_what_the_runtime_computes(host):
    from YPhotoSharing.YServer.classes.models import Recommendation

    a = adapter_for(host)
    a.apply_membership([MembershipChange("g1", "active", 0, "initial"), MembershipChange("g2", "active", 0, "initial"),
                        MembershipChange("g3", "dormant", 0, "initial")])
    db = host._db
    r0 = host.current_round_id
    r1 = db.get_or_create_round(0, 1)
    r_next = db.get_or_create_round(1, 0)
    new_photo(host, 1, "one")
    db.set_stress_reward_variations(U[1], r1, [{"variable": "stress", "value": 0.3}, {"variable": "stress", "value": 0.1},
                                               {"variable": "reward", "value": 0.8}, {"variable": "reward", "value": 0.5}])
    db.set_stress_reward_variations(U[1], r_next, [{"variable": "stress", "value": 0.5}])  # next day: not in the report of day 0
    db.add_reaction(U[1], new_photo(host, 2, "two"), "LIKE", r0)
    with Session(db.engine) as s:
        s.add(Recommendation(id="rec1", user_id=U[1], photo_ids='["a", "b", "c"]', round=r0))
        s.commit()
    samples = {x.global_agent_id: x for x in a.affective_report(0)}
    assert set(samples) == {"g1", "g2"}
    native = db.get_stress_reward(U[1], r1)  # the server's own computation at the last round of the day
    assert (samples["g1"].stress, samples["g1"].reward) == (pytest.approx(native["stress"]), pytest.approx(native["reward"]))
    assert (samples["g1"].stress, samples["g1"].reward) == (pytest.approx(0.4), 1.0)
    assert samples["g1"].actions == 2 and samples["g1"].exposures == 3
    assert (samples["g2"].stress, samples["g2"].reward, samples["g2"].actions) == (0.0, 0.0, 1)
    assert a.affective_report(9) == []


def test_attention_multipliers_are_stored_per_account_and_served_to_the_client(host):
    a = adapter_for(host)
    a.apply_attention(1, {"g1": 1.5, "g2": 1.0, "g3": 0.4, "nobody": 3.0})
    assert a.attention_multipliers() == {U[1]: 1.5, U[3]: 0.4}  # 1.0 needs no row, unknown agents are ignored
    server = SimpleNamespace(_federation_adapter=a)
    assert _unwrap("get_federation_attention")(server) == {U[1]: 1.5, U[3]: 0.4}
    a.apply_attention(2, {"g2": 2.0})  # a new day replaces the previous multipliers
    assert adapter_for(host).attention_multipliers() == {U[2]: 2.0}  # and they survive a restart
    a.apply_attention(3, {})
    assert a.attention_multipliers() == {} and _unwrap("get_federation_attention")(SimpleNamespace(_federation_adapter=None)) == {}


def test_client_attention_changes_who_acts_with_its_own_generator():
    async def remote():
        return {"a": 0.0, "b": 0.5, "c": 1.0}

    server = SimpleNamespace(get_federation_attention=SimpleNamespace(remote=remote))

    def agents(profile):
        return [SimpleNamespace(user_data={"id": i, "daily_activity_level": 5, **({"activity_profile": "p"} if profile else {})})
                for i in "abc"]

    def acting(planner, profile, rounds=200):
        counts = {"a": 0, "b": 0, "c": 0}
        for _ in range(rounds):
            for x in planner.select_active_agents(agents(profile), 3):
                counts[x.user_data["id"]] += 1
        return counts

    client_fed.install({"federation": {"enabled": True, "seed": 3}})
    asyncio.run(client_fed.refresh_attention(server))
    for profile in (True, False):
        random.seed(11)
        planner = SimulationRoundPlanner({"activity_profiles": {"p": list(range(24))}, "hourly_activity": {"3": 1.0}})
        c = acting(planner, profile)
        assert c["a"] == 0 and c["c"] == 200 and 70 < c["b"] < 130, (profile, c)  # 0 never acts, 1 as usual, 0.5 half the rounds
    client_fed.install({})  # off: identity, nobody is held back and the generator is not used
    random.seed(11)
    assert acting(SimulationRoundPlanner({"activity_profiles": {"p": list(range(24))}}), True) == {"a": 200, "b": 200, "c": 200}
