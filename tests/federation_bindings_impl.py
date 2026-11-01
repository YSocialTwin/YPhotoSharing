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
