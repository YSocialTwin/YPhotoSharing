from __future__ import annotations

import random
from typing import Iterable, List, Sequence


class SimulationRoundPlanner:
    """Encapsulate client-side agent scheduling and action-weight shaping."""

    def __init__(self, simulation_config: dict):
        self.simulation_config = simulation_config or {}

    def build_action_weights(self, user_data: dict) -> dict:
        base_weights = self.simulation_config.get(
            "actions_likelihood",
            {
                "post_photo": 0.15,
                "react": 0.20,
                "comment": 0.15,
                "follow": 0.10,
                "share": 0.05,
                "report": 0.05,
                "save": 0.10,
                "reply_comment": 0.10,
                "unfollow": 0.05,
                "send_dm": 0.05,
                "post_story": 0.05,
                "watch_story": 0.05,
            },
        )
        weights = dict(base_weights)
        if "post" in weights:
            weights["post_photo"] = weights.pop("post")
        if "read" in weights:
            weights["react"] = weights.pop("read")

        archetype = user_data.get("archetype")
        if archetype == "broadcaster":
            weights["post_photo"] = weights.get("post_photo", 0) * 2.0
            weights["post_story"] = weights.get("post_story", 0) * 2.0
        elif archetype == "explorer":
            weights["watch_story"] = weights.get("watch_story", 0) * 2.0
            weights["react"] = weights.get("react", 0) * 2.0
        elif archetype == "validator":
            weights["comment"] = weights.get("comment", 0) * 2.0
            weights["react"] = weights.get("react", 0) * 1.5

        return weights

    def select_active_agents(self, agents: Sequence[object], hour: int) -> List[object]:
        profiles = self.simulation_config.get("activity_profiles", {})
        hourly_activity = self.simulation_config.get("hourly_activity", {})

        active_agents = []
        for agent in agents:
            user_data = getattr(agent, "user_data", {}) or {}
            u_profile = user_data.get("activity_profile")

            if u_profile and u_profile in profiles:
                try:
                    profile_val = profiles[u_profile]
                    if isinstance(profile_val, list):
                        active_hours = [int(h) for h in profile_val]
                    else:
                        active_hours = [int(h) for h in str(profile_val).split(",")]
                    if hour in active_hours:
                        active_agents.append(agent)
                except ValueError:
                    continue
                continue

            prob = hourly_activity.get(str(hour), 0.04)
            if random.random() < float(prob):
                active_agents.append(agent)

        return active_agents
