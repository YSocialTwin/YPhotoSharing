"""INV-17 in YPhotoSharing: accounts are reported by username and the global id comes from the coordinator, never from the local id."""

import pytest

from ysocial_federation.schemas import MembershipChange  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from tests.federation_bus_impl import U, host, new_photo  # noqa: E402,F401
from YPhotoSharing.YServer.federation.adapter import YPhotoSharingAdapter  # noqa: E402


def bound_adapter(host, tmp_path, **kw):
    return YPhotoSharingAdapter("photos", 1, host=host, bindings_file=str(tmp_path / "bindings.db"), **kw)


def test_accounts_are_offered_by_username_once(host, tmp_path):
    a = bound_adapter(host, tmp_path)
    offered = a.account_bindings()
    assert offered == [{"username": f"u{n}", "local_account_id": U[n]} for n in (1, 2, 3)]
    a.bindings_reported(offered, [{"global_agent_id": "12", "local_account_id": U[1]}, {"global_agent_id": "30", "local_account_id": U[3]}])
    assert a.account_bindings() == []
    host._db.create_user({"id": "user-4", "username": "u4", "language": "en"})
    offered = a.account_bindings()
    assert offered == [{"username": "u4", "local_account_id": "user-4"}]
    a.bindings_reported(offered, [])
    assert a.account_bindings() == []
    assert {"username": "u4", "local_account_id": "user-4"} in a.account_bindings(retry=True)


def test_the_global_id_is_the_bound_one_and_never_the_local_id(host, tmp_path):
    a = bound_adapter(host, tmp_path)
    a.bindings_reported(a.account_bindings(), [{"global_agent_id": "12", "local_account_id": U[1]}])
    assert a.agent_of(U[1]) == "12" and a.user_of("12") == U[1]
    assert a.agent_of(U[2]) == f"unbound:{U[2]}"
    assert a.user_of("g2") is None and a.user_of(U[2]) is None


def test_membership_reaches_only_bound_accounts(host, tmp_path):
    a = bound_adapter(host, tmp_path)
    a.bindings_reported(a.account_bindings(), [{"global_agent_id": "12", "local_account_id": U[1]}])
    a.apply_membership([MembershipChange("12", "dormant", 0, "initial"), MembershipChange("77", "dormant", 0, "initial")])
    assert a.inactive_agent_ids() == {U[1]}


def test_only_bound_accounts_are_exported(host, tmp_path):
    a = bound_adapter(host, tmp_path, export_policy="all")
    a.bindings_reported(a.account_bindings(), [{"global_agent_id": "12", "local_account_id": U[1]}])
    new_photo(host, 1, "from a federation agent")
    new_photo(host, 2, "from an account the federation does not know")
    out = a.export_outbox(3)
    assert [e.payload["global_agent_id"] for e in out] == ["12"]


def test_a_restart_keeps_the_bindings(host, tmp_path):
    first = bound_adapter(host, tmp_path)
    first.bindings_reported(first.account_bindings(), [{"global_agent_id": "12", "local_account_id": U[2]}])
    second = bound_adapter(host, tmp_path)
    assert second.agent_of(U[2]) == "12" and second.account_bindings() == []


def test_without_a_bindings_file_nothing_changes(host):
    a = YPhotoSharingAdapter("photos", 1, host=host)
    assert a.account_bindings() == [] and a.agent_of(U[2]) == U[2] and a.user_of(U[2]) == U[2]


# -- INV-19: accounts created on the coordinator's request, and the client that adopts them ----------------------------------

import asyncio  # noqa: E402
import inspect  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from YPhotoSharing.YClient import federation as client_fed  # noqa: E402
from YPhotoSharing.YClient.client import SimulationClient  # noqa: E402
from YPhotoSharing.YServer.federation.tables import FederationMembership  # noqa: E402,F401
from YPhotoSharing.YServer.server import OrchestratorServer  # noqa: E402

SERVER = getattr(OrchestratorServer, "__ray_actor_class__", OrchestratorServer)
CLIENT = getattr(SimulationClient, "__ray_actor_class__", SimulationClient)

REQ = {"global_agent_id": "40", "username": "newcomer", "interests": ["jazz", "sport"], "oe": "inventive", "leaning": "left", "age": 31,
       "gender": "female", "nationality": "Italian", "toxicity": "no", "profession": "nurse", "language": "it", "profile": {"co": "organized"}}


def test_provisioned_accounts_are_created_bound_and_offered_to_a_client_once(host, tmp_path):
    a = bound_adapter(host, tmp_path)
    done = a.provision_accounts([REQ,
                                 {"global_agent_id": "41", "username": "u1", "interests": []},  # already an account
                                 {"global_agent_id": "42", "username": "x" * 51, "interests": []}])  # not a username
    by = {d["global_agent_id"]: d["local_account_id"] for d in done}
    assert set(by) == {"40", "41"} and by["41"] == U[1]
    uid = by["40"]
    assert a.agent_of(uid) == "40" and a.user_of("40") == uid and a._federated(uid)  # bound: acts, no `unbound:` id
    user = host._db.get_user(uid)
    assert (user["username"], user["oe"], user["co"], user["leaning"], user["age"], user["gender"], user["nationality"], user["profession"],
            user["language"], user["toxicity"]) == ("newcomer", "inventive", "organized", "left", 31, "female", "Italian", "nurse", "it", "no")
    # photo-sharing defaults: a public account, no picture, no bio, neutral traits where the request says nothing
    assert (user["is_private"], user["bio"], user["profile_picture_url"], user["archetype"], user["user_type"]) == (False, "", "", None, "regular")
    assert (user["ex"], user["ag"], user["ne"], user["round_actions"], user["owner"]) == ("medium", "medium", "medium", 3, "federation")
    assert [(p["username"], p["interests"]) for p in a.provisioned_accounts()] == [("newcomer", ["jazz", "sport"])]
    assert all(o["username"] != "newcomer" for o in a.account_bindings())  # known: never offered again
    a.mark_adopted([uid])
    assert a.provisioned_accounts() == []


def test_provisioning_twice_gives_the_same_account_and_creates_nothing_new(host, tmp_path):
    a = bound_adapter(host, tmp_path)
    first = a.provision_accounts([REQ])
    users = len(host._db.list_users())
    assert a.provision_accounts([REQ]) == first and len(host._db.list_users()) == users
    assert len(a.provisioned_accounts()) == 1


def test_a_provisioned_account_survives_a_restart_and_is_not_a_person(host, tmp_path):
    first = bound_adapter(host, tmp_path)
    uid = first.provision_accounts([REQ])[0]["local_account_id"]
    second = bound_adapter(host, tmp_path)
    assert second.agent_of(uid) == "40" and all(o["username"] != "newcomer" for o in second.account_bindings())
    second.register_human(U[3], "human:h3")  # the account of a person is never provisioned
    assert second.provision_accounts([{"global_agent_id": "50", "username": "u3", "interests": []}]) == []


def test_provisioning_without_a_bindings_file_creates_the_account_and_changes_nothing_else(host):
    a = YPhotoSharingAdapter("photos", 1, host=host)
    done = a.provision_accounts([REQ])
    assert a.agent_of(done[0]["local_account_id"]) == "40" and a.agent_of(U[2]) == U[2] and a.user_of(U[2]) == U[2]


def _remote(fn):
    async def call(*args, **kw):
        return fn(*args, **kw)

    return SimpleNamespace(remote=call)


def _server_of(host, adapter):
    """The server methods the client calls, over the real database and adapter (what a Ray handle gives)."""
    core = SimpleNamespace(_db=host._db, _federation_adapter=adapter, current_round_id=host.current_round_id, _current_day=0, _current_hour=0)
    out = {name: _remote(lambda *a, _f=inspect.unwrap(getattr(SERVER, name)), **k: _f(core, *a, **k))
           for name in ("get_federation_provisioned", "mark_federation_adopted", "create_user", "get_or_create_interest",
                        "set_user_interests", "update_last_active_day", "get_or_create_round", "get_user_interests")}
    return SimpleNamespace(**out)


def _client_of(server):
    fake = SimpleNamespace(server=server, _agents=[], _current_day=0, _current_hour=0, simulation_config={"discussion_topics": ["general"]})
    fake._register_agent_record = lambda *a, **k: inspect.unwrap(CLIENT._register_agent_record)(fake, *a, **k)

    async def add(record, *, round_id, day):
        registered = await fake._register_agent_record(record, round_id=round_id, day=day, initialize_opinions=True)
        fake._agents.append(SimpleNamespace(user_data=registered))
        return registered

    fake._register_agent_from_record = add
    fake.adopt_federated_account = lambda account: inspect.unwrap(CLIENT.adopt_federated_account)(fake, account)
    return fake


def test_the_client_adopts_each_provisioned_account_once_and_the_agent_can_act(host, tmp_path):
    a = bound_adapter(host, tmp_path)
    uid = a.provision_accounts([REQ])[0]["local_account_id"]
    server = _server_of(host, a)
    client = _client_of(server)
    client_fed.install({"federation": {"enabled": True}})
    assert asyncio.run(client_fed.adopt_provisioned(server, client)) == 0 and client._agents == []  # no `adopt`: nothing asked
    client_fed.install({"federation": {"enabled": True, "adopt": True}})
    try:
        assert asyncio.run(client_fed.adopt_provisioned(server, client)) == 1
        record = client._agents[0].user_data
        assert record["id"] == uid and record["username"] == "newcomer" and record["oe"] == "inventive"
        assert record["is_private"] is False and record["archetype"] is None  # the stored photo-sharing defaults are kept
        assert sorted(host._db.get_user_interests(uid)) == ["jazz", "sport"]  # the request's interests, stored once
        assert a.provisioned_accounts() == [] and len(host._db.list_users()) == 4  # reported as adopted, nobody registered twice
        assert asyncio.run(client_fed.adopt_provisioned(server, client)) == 0 and len(client._agents) == 1
        assert a.agent_of(uid) == "40" and a._active(host_session(host), uid)  # reachable and active: acts with multiplier 1
        assert client_fed.attention_multiplier(uid) == 1.0
    finally:
        client_fed.install({})


def host_session(host):
    return Session(host._db.engine)


def test_the_client_keeps_an_account_it_could_not_adopt_offered(host, tmp_path):
    a = bound_adapter(host, tmp_path)
    a.provision_accounts([REQ])
    server = _server_of(host, a)
    client = SimpleNamespace(adopt_federated_account=lambda account: _none())
    client_fed.install({"federation": {"enabled": True, "adopt": True}})
    try:
        assert asyncio.run(client_fed.adopt_provisioned(server, client)) == 0
        assert len(a.provisioned_accounts()) == 1
    finally:
        client_fed.install({})


async def _none():
    return None
