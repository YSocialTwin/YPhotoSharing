from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List, Optional

from YPhotoSharing.YClient.simulation.bootstrap import normalize_agent_config


class LifecycleManager:
    """Client-side agent lifecycle hooks for churn and new-user injection."""

    def __init__(
        self,
        *,
        server,
        client_id: str,
        config_path,
        simulation_config: Dict[str, Any],
        logger,
        add_agent_from_record_func,
        existing_usernames_func,
    ) -> None:
        self.server = server
        self.client_id = client_id
        self.config_path = config_path
        self.simulation_config = simulation_config or {}
        self.logger = logger
        self._add_agent_from_record = add_agent_from_record_func
        self._existing_usernames = existing_usernames_func

        agents_cfg = (self.simulation_config.get("agents") or {})
        churn_cfg = agents_cfg.get("churn") or {}
        new_agents_cfg = agents_cfg.get("new_agents") or {}

        self.churn_enabled = bool(churn_cfg.get("enabled", False))
        self.churn_probability = float(churn_cfg.get("churn_probability", 0.0) or 0.0)
        self.inactivity_threshold = int(churn_cfg.get("inactivity_threshold", 5) or 5)
        self.churn_percentage = float(churn_cfg.get("churn_percentage", 0.0) or 0.0)

        self.new_agents_enabled = bool(new_agents_cfg.get("enabled", False))
        self.probability_new_agents = float(new_agents_cfg.get("probability_new_agents", 0.0) or 0.0)
        self.percentage_new_agents = float(new_agents_cfg.get("percentage_new_agents", 0.0) or 0.0)

    async def evaluate_end_of_day(self, *, day: int, round_id: str, agents: List[object]) -> Dict[str, int]:
        churned = await self._evaluate_churn(day=day, round_id=round_id, agents=agents)
        new_agents = await self._evaluate_new_agents(day=day, round_id=round_id, agents=agents)
        return {"churned": churned, "new_agents": new_agents}

    async def _evaluate_churn(self, *, day: int, round_id: str, agents: List[object]) -> int:
        if not self.churn_enabled:
            return 0

        candidates = []
        for agent in agents:
            user_data = getattr(agent, "user_data", {}) or {}
            if user_data.get("is_churned") or user_data.get("left_on") is not None:
                continue
            last_active_day = user_data.get("last_active_day")
            if last_active_day is None:
                continue
            if day - int(last_active_day) >= self.inactivity_threshold:
                candidates.append(agent)

        if not candidates or self.churn_probability <= 0.0 or self.churn_percentage <= 0.0:
            return 0

        num_candidates = max(1, int(len(candidates) * self.churn_percentage))
        selected = random.sample(candidates, min(num_candidates, len(candidates)))
        churned = 0
        for agent in selected:
            if random.random() >= self.churn_probability:
                continue
            try:
                updated = await self.server.set_churn_state.remote(agent.user_id, True)
                if updated:
                    agent.user_data["is_churned"] = True
                    agent.user_data["left_on"] = round_id
                    churned += 1
            except Exception as exc:
                self.logger.warning(f"Failed to churn agent {agent.user_id}: {exc}")
        return churned

    async def _evaluate_new_agents(self, *, day: int, round_id: str, agents: List[object]) -> int:
        if not self.new_agents_enabled:
            return 0

        non_churned_agents = [
            agent for agent in agents if not agent.user_data.get("is_churned") and agent.user_data.get("left_on") is None
        ]
        if not non_churned_agents or self.percentage_new_agents <= 0.0 or self.probability_new_agents <= 0.0:
            return 0

        num_slots = int(len(non_churned_agents) * self.percentage_new_agents)
        if num_slots <= 0:
            return 0

        added = 0
        for _ in range(num_slots):
            if random.random() >= self.probability_new_agents:
                continue
            template_agent = random.choice(non_churned_agents)
            template_user_data = dict(getattr(template_agent, "user_data", {}) or {})
            new_user_data = self._make_new_agent_user_data(template_user_data, day=day, round_id=round_id)
            try:
                await self._add_agent_from_record(new_user_data, round_id=round_id, day=day)
                added += 1
            except Exception as exc:
                self.logger.warning(f"Failed to create new agent from template {template_agent.user_id}: {exc}")
        return added

    def _make_new_agent_user_data(self, template_user_data: Dict[str, Any], *, day: int, round_id: str) -> Dict[str, Any]:
        new_user_data = normalize_agent_config(template_user_data, self.simulation_config)
        new_user_data = dict(new_user_data)
        new_user_data["id"] = str(uuid.uuid4())
        new_user_data["username"] = self._unique_username(
            base_username=str(new_user_data.get("username") or "agent"),
            existing_usernames=self._current_usernames(),
        )
        new_user_data["email"] = f"{new_user_data['username']}@simulation.local"
        new_user_data["joined_on"] = round_id
        new_user_data["left_on"] = None
        new_user_data["is_churned"] = False
        new_user_data["is_page"] = 0
        new_user_data["last_active_day"] = int(day)
        return new_user_data

    def _current_usernames(self) -> set[str]:
        if callable(self._existing_usernames):
            try:
                return set(self._existing_usernames())
            except Exception:
                return set()
        return set()

    def _unique_username(self, *, base_username: str, existing_usernames: set[str]) -> str:
        candidate = base_username.replace(" ", "_").replace(".", "")
        suffix = 1
        while candidate in existing_usernames:
            candidate = f"{base_username}_{suffix}"
            suffix += 1
        return candidate
