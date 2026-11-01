"""H5c: human participation gateway of YPhotoSharing: accounts, actions, cross-post, exclusion from the agent rules,
HTTP transport and offline mode. No coordinator, no network beyond loopback, no LLM."""

import json
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from federation_bus_impl import U, _unwrap, adapter_for, host, new_photo  # noqa: F401
from YPhotoSharing.YGateway.core import HumanGateway, LocalBackend, RateLimiter
from YPhotoSharing.YGateway.humans import global_id_of, human_account_id
from YPhotoSharing.YGateway.http import serve
from YPhotoSharing.YGateway.offline import handle_offline

IMG = "https://img/h.jpg"


def gw_for(host, **kw):  # noqa: F811
    a = adapter_for(host, crosspost_mode="agent_action", **kw)
    return HumanGateway(LocalBackend(host._db, a), RateLimiter(burst=50, per_second=50)), a


def ensure(gw, key="7", **kw):
    status, out = gw.ensure(key, **kw)
    assert status == 200, out
    return out


def test_ensure_is_idempotent_and_makes_a_human_account(host):  # noqa: F811
    gw, a = gw_for(host)
    first = ensure(gw, "7", username="Ada Lovelace", language="it")
    again = ensure(gw, "7")
    assert first["created"] is True and again["created"] is False and first["account_id"] == again["account_id"] == human_account_id("7")
    assert first["global_agent_id"] == "human:7"
    user = host._db.get_user(first["account_id"])
    assert user["user_type"] == "human" and user["round_actions"] == 0 and user["username"] == "Ada_Lovelace" and user["language"] == "it"
    assert gw.ensure("")[0] == 400 and gw.ensure("a:b")[0] == 400


def test_a_taken_username_gets_a_suffix(host):  # noqa: F811
    gw, a = gw_for(host)
    out = ensure(gw, "8", username="u1")  # "u1" belongs to an agent
    assert host._db.get_user(out["account_id"])["username"] != "u1"


def test_a_person_never_takes_the_local_id_as_global_identity(host):  # noqa: F811
    gw, a = gw_for(host)
    uid = ensure(gw, "7")["account_id"]
    assert a.agent_of(uid) == "human:7" and a.user_of("human:7") == uid and a.is_human(uid)
    assert a.agent_of(U[1]) == "g1" and not a.is_human(U[1])
    fresh = adapter_for(host, crosspost_mode="agent_action")  # the identity survives a restart (table)
    assert fresh.agent_of(uid) == "human:7"
    with pytest.raises(ValueError):
        a.register_human(uid, "human:other")
    with pytest.raises(ValueError):
        a.register_human(U[1], "human:7")
    with pytest.raises(ValueError):
        a.register_human(U[1], "g1")


def act(gw, uid, *actions):
    status, out = gw.actions(uid, list(actions))
    assert status == 200, out
    return out["results"]


def test_publish_with_crosspost_leaves_as_a_crosspost_of_the_person(host):  # noqa: F811
    gw, a = gw_for(host)
    uid = ensure(gw, "7")["account_id"]
    a.set_destinations({"human:7": [{"member": "forum", "local_account_id": "901"}, {"member": "dating", "local_account_id": "902"}]})
    r = act(gw, uid, {"type": "post_photo", "image_url": IMG, "caption": "my day", "topics": ["travel"],
                      "crosspost_to": [{"member": "forum", "text": "Title\nmy day"}, {"member": "dating"}]})[0]
    assert r["ok"] and host._db.get_photo(r["photo_id"])["user_id"] == uid
    out = a.export_outbox(3)
    assert [(e.target_member, e.payload["global_agent_id"], e.payload["target_account_id"], e.payload["text_excerpt"]) for e in out] == [
        ("dating", "human:7", "902", "my day"), ("forum", "human:7", "901", "Title\nmy day")]
    assert out[0].payload["topics"] == ["travel"] and out[0].payload["image_ref"] == IMG


def test_share_of_an_agent_photo_carries_the_quoted_author(host):  # noqa: F811
    gw, a = gw_for(host)
    uid = ensure(gw, "7")["account_id"]
    a.set_destinations({"human:7": [{"member": "forum", "local_account_id": "901"}]})
    original = new_photo(host, 2, "words of the second agent", topics=("sport",))
    r = act(gw, uid, {"type": "share", "photo_id": original, "caption": "so true", "crosspost_to": [{"member": "forum"}]})[0]
    assert r["ok"] and host._db.get_photo(r["photo_id"])["parent_photo_id"] == original
    e = a.export_outbox(3)[0]
    assert e.payload["global_agent_id"] == "human:7" and e.payload["text_excerpt"] == "so true"
    assert e.payload["quoted"]["global_agent_id"] == "g2" and e.payload["quoted"]["text_excerpt"] == "words of the second agent"
    assert e.payload["topics"] == ["sport"]


def test_a_quoted_person_is_a_federation_identity(host):  # noqa: F811
    gw, a = gw_for(host)
    uid = ensure(gw, "7")["account_id"]
    other = ensure(gw, "9")["account_id"]
    a.set_destinations({"human:9": [{"member": "forum", "local_account_id": "909"}]})
    photo = act(gw, uid, {"type": "post_photo", "image_url": IMG, "caption": "hello"})[0]["photo_id"]
    act(gw, other, {"type": "share", "photo_id": photo, "caption": "mine too", "crosspost_to": [{"member": "forum"}]})
    assert a.export_outbox(3)[0].payload["quoted"]["global_agent_id"] == "human:7"


def test_without_crosspost_nothing_leaves_and_social_actions_work(host):  # noqa: F811
    gw, a = gw_for(host)
    uid = ensure(gw, "7")["account_id"]
    photo = new_photo(host, 1, "agent photo")
    res = act(gw, uid, {"type": "post_photo", "image_url": IMG, "caption": "plain"},
              {"type": "comment", "photo_id": photo, "body": "nice"}, {"type": "react", "photo_id": photo, "reaction_type": "love"},
              {"type": "follow", "user_id": U[1]}, {"type": "unreact", "photo_id": photo}, {"type": "unfollow", "user_id": U[1]})
    assert [r["ok"] for r in res] == [True] * 6, res
    assert len(host._db.get_comments(photo)) == 1
    assert a.export_outbox(3) == []


@pytest.mark.parametrize("bad", [{"type": "nope"}, {"type": "post_photo", "caption": "no image"}, {"type": "comment", "photo_id": "x", "body": "y"},
                                 {"type": "react", "photo_id": "x"}, {"type": "follow", "user_id": "missing"},
                                 {"type": "post_photo", "image_url": IMG, "caption": "x" * 2300},
                                 {"type": "post_photo", "image_url": IMG, "caption": "c", "crosspost_to": "forum"},
                                 {"type": "post_photo", "image_url": IMG, "caption": "c", "crosspost_to": [{"text": "no member"}]}, "text"])
def test_invalid_actions_are_refused_without_effect(host, bad):  # noqa: F811
    gw, a = gw_for(host)
    uid = ensure(gw, "7")["account_id"]
    assert act(gw, uid, bad)[0]["ok"] is False
    assert a.export_outbox(3) == []


def test_only_people_can_use_the_gateway_and_requests_are_limited(host):  # noqa: F811
    gw, a = gw_for(host)
    assert gw.actions(U[1], [{"type": "follow", "user_id": U[2]}])[0] == 403  # an agent account
    assert gw.actions("missing", [{"type": "follow", "user_id": U[2]}])[0] == 403
    uid = ensure(gw, "7")["account_id"]
    assert gw.actions(uid, [])[0] == 400 and gw.actions(uid, [{"type": "follow", "user_id": U[2]}] * 21)[0] == 400
    slow = HumanGateway(gw.backend, RateLimiter(burst=2, per_second=0.0001))
    assert slow.actions(uid, [{"type": "follow", "user_id": U[2]}] * 2)[0] == 200
    assert slow.actions(uid, [{"type": "follow", "user_id": U[2]}])[0] == 429


def test_people_are_outside_attention_churn_and_the_affective_report(host):  # noqa: F811
    from ysocial_federation.schemas import MembershipChange

    gw, a = gw_for(host)
    uid = ensure(gw, "7")["account_id"]
    a.apply_membership([MembershipChange("human:7", "active", 0, "initial"), MembershipChange("g1", "active", 0, "initial")])
    act(gw, uid, {"type": "post_photo", "image_url": IMG, "caption": "x"})
    host._db.get_or_create_round(0, 23)
    assert [s.global_agent_id for s in a.affective_report(0)] == ["g1"]
    a.apply_attention(0, {"human:7": 0.2, "g1": 0.5})
    assert a.attention_multipliers() == {U[1]: 0.5}
    from YPhotoSharing.YServer.classes.models import User_mgmt
    from sqlalchemy.orm import Session

    with Session(host._db.engine) as s:
        for user_id in (uid, U[1]):
            s.get(User_mgmt, user_id).left_on = host.current_round_id
        s.commit()
    assert a.churned_agents(0) == ["g1"]


def test_server_methods_create_the_account_and_report_the_round(host):  # noqa: F811
    a = adapter_for(host, crosspost_mode="agent_action")
    stub = SimpleNamespace(_db=host._db, _federation_adapter=a, current_round_id=host.current_round_id, _current_day=0, _current_hour=0)
    stub.human_context = lambda: _unwrap("human_context")(stub)
    ctx = stub.human_context()
    assert ctx["round_id"] == host.current_round_id and ctx["federated"] is True and ctx["crosspost_mode"] == "agent_action"
    out = _unwrap("human_ensure")(stub, "5", "Grace", "en")
    assert out["global_agent_id"] == "human:5" and a.agent_of(out["account_id"]) == "human:5"
    assert _unwrap("human_ensure")(stub, "5")["created"] is False


def test_http_transport_needs_the_token_and_serves_the_routes(host):  # noqa: F811
    gw, a = gw_for(host)
    server = serve(gw, "t" * 20)
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def call(method, path, body=None, token="t" * 20):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method,
                                     headers={"X-YPS-Gateway-Token": token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    try:
        assert call("GET", "/v1/state", token="wrong")[0] == 401
        assert call("GET", "/v1/state")[1]["federated"] is True
        uid = call("POST", "/v1/humans/ensure", {"human_key": "7", "username": "ada"})[1]["account_id"]
        a.set_destinations({"human:7": [{"member": "forum", "local_account_id": "901"}]})
        status, out = call("POST", "/v1/actions", {"account_id": uid, "actions": [
            {"type": "post_photo", "image_url": IMG, "caption": "via http", "crosspost_to": [{"member": "forum"}]}]})
        assert status == 200 and out["ok"]
        pid = out["results"][0]["photo_id"]
        assert [e.target_member for e in a.export_outbox(3)] == ["forum"]
        assert call("GET", f"/v1/feed?account_id={uid}")[0] == 200
        assert call("GET", f"/v1/photos/{pid}/comments?account_id={uid}")[1]["comments"] == []
        assert call("GET", "/v1/nowhere")[0] == 404
        assert call("POST", "/v1/actions", {"account_id": U[1], "actions": [{"type": "follow", "user_id": U[2]}]})[0] == 403
    finally:
        server.shutdown()


def test_offline_applies_the_request_under_a_lock_and_the_crosspost_leaves_after_the_restart(tmp_path):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from run_offline_gateway import backend_factory
    from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware

    (tmp_path / "server_config.json").write_text(json.dumps({
        "database": {"type": "sqlite", "sqlite": {"filename": "x.db"}},
        "federation": {"enabled": True, "member": "photos", "crosspost_mode": "agent_action", "accounts": {}}}))
    DatabaseMiddleware({"type": "sqlite", "sqlite": {"filename": "x.db"}}, tmp_path).get_or_create_round(2, 5)

    def request(method, path, body=None, q=None):
        return handle_offline(tmp_path, method, [p for p in path.split("/") if p], q or {}, body or {}, backend_factory)

    status, out = request("POST", "/v1/humans/ensure", {"human_key": "7", "username": "ada"})
    assert status == 200 and out["created"] and out["global_agent_id"] == "human:7"
    status, out = request("POST", "/v1/actions", {"account_id": out["account_id"], "actions": [
        {"type": "post_photo", "image_url": IMG, "caption": "offline", "crosspost_to": [{"member": "forum", "text": "offline"}]}]})
    assert status == 200 and out["ok"]
    # "restart": a new adapter on the same database finds the request and exports it
    db = DatabaseMiddleware({"type": "sqlite", "sqlite": {"filename": "x.db"}}, tmp_path)
    host_ = SimpleNamespace(_db=db, current_round_id=db.get_or_create_round(2, 5), _current_day=2, _current_hour=5)
    a = adapter_for_offline(host_)
    a.set_destinations({"human:7": [{"member": "forum", "local_account_id": "901"}]})
    exported = a.export_outbox(53)
    assert [(e.target_member, e.payload["global_agent_id"], e.payload["text_excerpt"]) for e in exported] == [("forum", "human:7", "offline")]
    # the round of the action is the one where the experiment stopped
    assert db.get_photo(out["results"][0]["photo_id"])["round"] == host_.current_round_id
    (tmp_path / "ray_ready.temp").write_text("ns\n")
    assert request("POST", "/v1/humans/ensure", {"human_key": "8"})[0] == 409  # the server is running: refused
    assert request("GET", "/v1/state")[0] == 409


def adapter_for_offline(host_):
    from YPhotoSharing.YServer.federation.adapter import YPhotoSharingAdapter

    return YPhotoSharingAdapter("photos", 1, host=host_, accounts={}, crosspost_mode="agent_action")
