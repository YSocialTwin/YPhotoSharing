import tempfile
from pathlib import Path

from YPhotoSharing.YClient.stress_reward.update_system import (
    StressRewardSystem,
    build_stress_reward_settings_from_config,
)
from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware
from YPhotoSharing.YServer.classes.models import StressReward


def _make_db(tmpdir: str) -> DatabaseMiddleware:
    return DatabaseMiddleware(
        {"type": "sqlite", "sqlite": {"filename": "phase4.db"}},
        config_path=Path(tmpdir),
    )


def test_build_stress_reward_settings_from_config_prefers_nested_values():
    settings = build_stress_reward_settings_from_config(
        {
            "stress_reward": {
                "enabled": True,
                "backward_rounds": 12,
                "system": {"churn": {"enabled": True}},
            },
            "simulation": {
                "stress_reward": {
                    "enabled": False,
                    "backward_rounds": 8,
                }
            },
        }
    )

    assert settings["enabled"] is False
    assert settings["backward_rounds"] == 8
    assert settings["system"]["churn"]["enabled"] is True


def test_compute_current_stress_reward_uses_server_payload(monkeypatch):
    class FakeRemoteMethod:
        def __init__(self, payload):
            self.payload = payload
            self.calls = []

        def remote(self, *args):
            self.calls.append(args)
            return self.payload

    class FakeServer:
        def __init__(self, payload):
            self.get_stress_reward = FakeRemoteMethod(payload)

    monkeypatch.setattr(
        "YPhotoSharing.YClient.stress_reward.update_system.ray.get",
        lambda value: value,
    )

    system = StressRewardSystem({"churn": {"enabled": True}})
    server = FakeServer({"stress": 0.66, "reward": 0.12})

    payload = system.compute_current_stress_reward(
        server=server,
        agent_id="agent-1",
        current_tid="round-1",
        backward_rounds=6,
    )

    assert payload == {"stress": 0.66, "reward": 0.12}
    assert server.get_stress_reward.calls == [("agent-1", "round-1", 6)]


def test_stress_reward_variations_are_persisted_and_aggregated():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _make_db(tmpdir)
        user_id = db.create_user({"username": "alice", "password": "secret"})
        round_0 = db.get_or_create_round(0, 0)
        round_1 = db.get_or_create_round(0, 1)

        written = db.set_stress_reward_variations(
            user_id,
            round_0,
            [
                {"variable": "stress", "value": 0.25},
                {"variable": "reward", "value": 0.15},
            ],
            action_name="comment:supportive",
        )
        assert written == 2

        state = db.get_stress_reward(user_id, round_1, backward_rounds=24)
        assert state["status"] == 200
        assert state["stress"] == 0.25
        assert state["reward"] == 0.15

        with db.session_scope() as session:
            aggregate_rows = session.query(StressReward).filter_by(
                uid=user_id, type="aggregate", tid=round_1
            ).all()
            variation_rows = session.query(StressReward).filter_by(
                uid=user_id, type="variation"
            ).all()

        assert len(aggregate_rows) == 2
        assert len(variation_rows) == 2
