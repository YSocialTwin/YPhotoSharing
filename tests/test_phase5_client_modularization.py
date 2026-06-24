import asyncio
from types import SimpleNamespace

from YPhotoSharing.YClient.agent_management.agent import Agent
from YPhotoSharing.YClient.simulation.round_planner import SimulationRoundPlanner


class FakeAgent:
    def __init__(self, activity_profile=None, daily_activity_level=1):
        self.user_data = {
            "activity_profile": activity_profile,
            "daily_activity_level": daily_activity_level,
        }


class RemoteMethodStub:
    def __init__(self, value):
        self.value = value

    def remote(self, *args, **kwargs):
        return self.value


class AgentServerStub:
    def __init__(self, user_record):
        self.get_user = RemoteMethodStub(user_record)
        self.update_last_active_day = RemoteMethodStub(True)


def test_round_planner_builds_archetype_sensitive_weights():
    planner = SimulationRoundPlanner(
        {
            "actions_likelihood": {
                "post": 0.2,
                "read": 0.3,
                "comment": 0.1,
                "post_story": 0.05,
                "watch_story": 0.05,
            }
        }
    )

    broadcaster_weights = planner.build_action_weights({"archetype": "broadcaster"})
    explorer_weights = planner.build_action_weights({"archetype": "explorer"})

    assert broadcaster_weights["post_photo"] == 0.4
    assert broadcaster_weights["post_story"] == 0.1
    assert broadcaster_weights["react"] == 0.3
    assert explorer_weights["watch_story"] == 0.1
    assert explorer_weights["react"] == 0.6


def test_round_planner_selects_active_agents_by_profile_and_hour(monkeypatch):
    planner = SimulationRoundPlanner(
        {
            "activity_profiles": {"day": [8, 9], "evening": "18,19"},
            "hourly_activity": {"9": 0.0, "10": 1.0},
        }
    )

    agents = [
        FakeAgent("day"),
        FakeAgent("evening"),
        FakeAgent(None),
    ]

    monkeypatch.setattr("random.random", lambda: 1.0)
    assert [agent.user_data["activity_profile"] for agent in planner.select_active_agents(agents, 8)] == [
        "day"
    ]
    assert [agent.user_data["activity_profile"] for agent in planner.select_active_agents(agents, 18)] == [
        "evening"
    ]
    monkeypatch.setattr("random.random", lambda: 0.0)
    assert [agent.user_data["activity_profile"] for agent in planner.select_active_agents(agents, 10)] == [
        None,
    ]


def test_round_planner_uses_daily_activity_level_for_fallback_sampling(monkeypatch):
    planner = SimulationRoundPlanner({"hourly_activity": {"10": 0.5}})
    monkeypatch.setattr("random.random", lambda: 0.3)

    low = FakeAgent(None, daily_activity_level=1)
    high = FakeAgent(None, daily_activity_level=5)

    selected = planner.select_active_agents([low, high], 10)
    assert selected == [high]


def test_agent_run_round_caps_actions_by_round_actions(monkeypatch):
    agent = Agent(
        user_data={
            "id": "agent-1",
            "username": "agent",
            "is_private": False,
            "is_churned": False,
            "round_actions": 4,
            "attention_budget": 200,
        },
        server=AgentServerStub(
            {
                "id": "agent-1",
                "username": "agent",
                "is_private": False,
                "is_churned": False,
                "round_actions": 4,
                "attention_budget": 200,
            }
        ),
        llm_service=SimpleNamespace(),
        action_weights={"react": 1.0},
    )

    async def fake_execute_action(action, day, hour, round_id):
        return {"ok": True}

    async def fake_update_satisfaction():
        return None

    monkeypatch.setattr("YPhotoSharing.YClient.agent_management.agent.ray.get", lambda value: value)
    monkeypatch.setattr("YPhotoSharing.YClient.agent_management.agent.random.randint", lambda low, high: 4)
    monkeypatch.setattr(agent, "_sample_action", lambda: "react")
    monkeypatch.setattr(agent, "_execute_action", fake_execute_action)
    monkeypatch.setattr(agent, "_update_satisfaction", fake_update_satisfaction)

    results = asyncio.run(agent.run_round(0, 1, "round-1"))
    assert len(results) == 4
