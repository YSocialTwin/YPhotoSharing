from YPhotoSharing.YClient.simulation.round_planner import SimulationRoundPlanner


class FakeAgent:
    def __init__(self, activity_profile=None):
        self.user_data = {"activity_profile": activity_profile}


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
