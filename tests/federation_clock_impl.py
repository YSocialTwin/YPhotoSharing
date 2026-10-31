"""Federated clock hooks of the YPhotoSharing server and client (F2.7): the gate is a stub, no coordinator, no network."""

import asyncio
import inspect
import sys
import types
from types import SimpleNamespace

import pytest

try:  # the annotation stack is optional in this environment; the clock hooks do not use it
    import detoxify  # noqa: F401
except ImportError:
    stub = types.ModuleType("detoxify")
    stub.Detoxify = object
    sys.modules["detoxify"] = stub

from YPhotoSharing.YClient.client import SimulationClient  # noqa: E402
from YPhotoSharing.YServer.server import OrchestratorServer  # noqa: E402

CLASS = getattr(OrchestratorServer, "__ray_actor_class__", OrchestratorServer)
CLIENT_CLASS = getattr(SimulationClient, "__ray_actor_class__", SimulationClient)


class StubGate:
    def __init__(self, allowed=True):
        self.allowed = allowed
        self.calls = []

    def on_barrier_ready(self, local_round):
        self.calls.append(("barrier", tuple(local_round)))
        return self.allowed

    def on_round_opened(self, local_round):
        self.calls.append(("opened", tuple(local_round)))

    def on_finished(self):
        self.calls.append(("finished",))


def make_server(gate=None, clients=("a", "b")):
    s = SimpleNamespace(
        _federation_gate=gate, _advance_pending=False, _round_ready={}, _finished_clients=set(),
        _registered_clients={c: {} for c in clients}, min_to_start=1, _current_day=0, _current_hour=0,
    )

    def advance():
        s._current_hour += 1
        if s._current_hour >= 24:
            s._current_hour, s._current_day = 0, s._current_day + 1

    s._advance_round = advance
    for name in ("ready_for_next_round", "_try_advance", "round_pending", "finish_client"):
        setattr(s, name, inspect.unwrap(getattr(CLASS, name)).__get__(s))  # unwrap: Ray's tracing wrapper hides return values
    return s


def at(s):
    return s._current_day, s._current_hour


def test_standalone_advances_when_every_client_is_ready_and_round_pending_is_false():
    s = make_server()
    assert s.ready_for_next_round("a") is False and at(s) == (0, 0)
    assert s.ready_for_next_round("b") is True and at(s) == (0, 1)
    assert s._round_ready == {} and s.round_pending() is False


def test_closed_gate_holds_the_round_and_keeps_the_ready_marks():
    gate = StubGate(allowed=False)
    s = make_server(gate)
    s.ready_for_next_round("a")
    s.ready_for_next_round("b")
    assert at(s) == (0, 0) and s._advance_pending is True and set(s._round_ready) == {"a", "b"}
    assert gate.calls == [("barrier", (0, 0))]


def test_polling_round_pending_releases_the_round_once_the_gate_opens():
    gate = StubGate(allowed=False)
    s = make_server(gate)
    s.ready_for_next_round("a")
    s.ready_for_next_round("b")
    assert s.round_pending() is True and at(s) == (0, 0)
    gate.allowed = True
    assert s.round_pending() is False and at(s) == (0, 1)
    assert s.round_pending() is False and at(s) == (0, 1)  # a second poller does not advance again
    assert gate.calls[-1] == ("opened", (0, 1)) and s._round_ready == {}


def test_gate_is_not_asked_before_every_client_is_ready():
    gate = StubGate()
    s = make_server(gate)
    s.ready_for_next_round("a")
    assert gate.calls == []


def test_day_rollover_is_reported_in_zero_based_local_time():
    gate = StubGate()
    s = make_server(gate, clients=("a",))
    s._current_hour = 23
    s.ready_for_next_round("a")
    assert at(s) == (1, 0) and gate.calls[-1] == ("opened", (1, 0))


def test_end_of_run_is_reported_when_every_client_has_finished():
    gate = StubGate()
    s = make_server(gate)
    s.finish_client("a")
    assert ("finished",) not in gate.calls
    s.finish_client("b")
    assert gate.calls[-1] == ("finished",)


def test_client_waits_for_the_round_to_open():
    cls = CLIENT_CLASS
    answers = iter([True, True, False])
    polls = []

    class Remote:
        async def remote(self):
            polls.append(1)
            return next(answers)

    fake = SimpleNamespace(server=SimpleNamespace(round_pending=Remote()))
    asyncio.run(inspect.unwrap(cls._wait_for_round_open)(fake, poll_seconds=0))
    assert len(polls) == 3
