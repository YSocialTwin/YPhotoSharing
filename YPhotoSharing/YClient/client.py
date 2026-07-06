"""
Ray Client actor for YPhotoSharing.

Manages a pool of agents, coordinates with the OrchestratorServer and drives
the simulation loop. Only client-side code lives here; all DB access goes
through the server's remote API.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import random
import time
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List, Optional

import ray

from YPhotoSharing.common_utils import build_structured_file_logger, setup_logging
from YPhotoSharing.YClient.agent_management.agent import Agent
from YPhotoSharing.YClient.simulation.bootstrap import (
    build_initial_interest_ids,
    normalize_agent_config,
    normalize_agent_population_document,
)
from YPhotoSharing.YClient.simulation.lifecycle_manager import LifecycleManager
from YPhotoSharing.YClient.simulation.round_planner import SimulationRoundPlanner

logger = logging.getLogger(__name__)


def _build_llm_service(
    llm_config: dict,
    prompts_config: dict,
    llm_v_config: Optional[dict],
    logging_config: dict,
):
    backend = str(llm_config.get("backend", "ollama")).lower()
    use_vllm = llm_config.get("use_vllm", False)
    use_remote_batch = llm_config.get("use_remote_batch", False)

    if use_vllm:
        from YPhotoSharing.YClient.LLM_interactions.vllm_service import VLLMService

        return VLLMService.remote(
            llm_config=llm_config,
            prompts_config=prompts_config,
            llm_v_config=llm_v_config,
            logging_config=logging_config,
        )
    if use_remote_batch:
        from YPhotoSharing.YClient.LLM_interactions.remote_batch_service import RemoteBatchLLMService

        return RemoteBatchLLMService.remote(
            llm_config=llm_config,
            prompts_config=prompts_config,
            llm_v_config=llm_v_config,
            logging_config=logging_config,
        )

    from YPhotoSharing.YClient.LLM_interactions.llm_service import LLMService

    return LLMService.remote(
        llm_config=llm_config,
        prompts_config=prompts_config,
        llm_v_config=llm_v_config,
        logging_config=logging_config,
    )


class ActionFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        stripped = msg.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                json.loads(stripped)
                return stripped
            except json.JSONDecodeError:
                pass
        
        log_data = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": msg,
        }
        if hasattr(record, "extra_data"):
            ext = getattr(record, "extra_data")
            if isinstance(ext, dict):
                log_data.update(ext)
        elif hasattr(record, "extra"):
            ext = getattr(record, "extra")
            if isinstance(ext, dict):
                log_data.update(ext)
        return json.dumps(log_data)


@ray.remote
class SimulationClient:
    """Ray remote actor representing one simulation client process."""

    def __init__(
        self,
        client_id: str,
        server_name: str,
        namespace: str,
        config_path: str,
        llm_config: Optional[Dict[str, Any]] = None,
        prompts_config: Optional[Dict[str, Any]] = None,
        llm_v_config: Optional[Dict[str, Any]] = None,
        logging_config: Optional[Dict[str, Any]] = None,
        simulation_config: Optional[Dict[str, Any]] = None,
    ):
        self.client_id = client_id
        self.config_path = Path(config_path)
        self.simulation_config = simulation_config or {}
        logging_config = dict(logging_config or {})
        logging_config.setdefault("log_dir", str(self.config_path / "logs"))
        logging_config.setdefault("instance_name", self.client_id)
        self._agents: List[Agent] = []
        self._round_count = 0
        self._start_time = time.time()
        self._current_day = 0
        self._current_hour = 0
        self._run_id = str(uuid.uuid4())
        self.round_planner = SimulationRoundPlanner(self.simulation_config)
        self.lifecycle_manager = None

        global logger
        logger = setup_logging(
            self.config_path,
            "client",
            logging_config,
            instance_name=self.client_id,
        )
        self.logger = logger
        self.action_logger = None

        enable_client_log = logging_config.get("enable_client_log", True)
        if enable_client_log:
            action_log_file = self.config_path / "logs" / f"{self.client_id}_client.log"
            action_handler = RotatingFileHandler(
                action_log_file, maxBytes=10 * 1024 * 1024, backupCount=5
            )

            from YPhotoSharing.common_utils import _compress_rotated_log
            action_handler.rotator = _compress_rotated_log
            action_handler.namer = lambda name: name + ".gz"

            action_handler.setFormatter(ActionFormatter())
            self.action_logger = logging.getLogger(f"YPhotoSharing.Client.{self.client_id}.Actions")
            self.action_logger.setLevel(logging.INFO)
            self.action_logger.handlers = []
            self.action_logger.propagate = False
            self.action_logger.addHandler(action_handler)

        self.hourly_actions = []
        self.daily_actions = []

        for attempt in range(10):
            try:
                self.server = ray.get_actor(server_name, namespace=namespace)
                break
            except ValueError:
                if attempt == 9:
                    raise
                time.sleep(1)

        llm_config = llm_config or {
            "address": "localhost",
            "port": 11434,
            "model": "llama3.2",
        }
        prompts_config = prompts_config or {}
        self.llm_service = _build_llm_service(
            llm_config,
            prompts_config,
            llm_v_config,
            logging_config,
        )

        from YPhotoSharing.YClient.stress_reward import (
            StressRewardSystem,
            build_stress_reward_settings_from_config,
        )

        stress_reward_settings = build_stress_reward_settings_from_config(self.simulation_config)
        self.stress_reward_enabled = bool(stress_reward_settings.get("enabled", False))
        self.stress_reward_backward_rounds = int(
            stress_reward_settings.get("backward_rounds", 24) or 24
        )
        self.stress_reward_system = StressRewardSystem(stress_reward_settings.get("system") or {})

        from YPhotoSharing.YClient.LLM_interactions.image_generation_service import ImageGenerationService

        use_local_diffusion = self.simulation_config.get("use_local_diffusion", False)
        local_diffusion_model = self.simulation_config.get("local_diffusion_model", "segmind/tiny-sd")
        self.image_gen_service = ImageGenerationService(
            use_local_diffusion=use_local_diffusion,
            local_diffusion_model=local_diffusion_model,
        )

        from YPhotoSharing.YClient.opinion.opinion_manager import OpinionManager

        self.opinion_manager = OpinionManager(
            simulation_config=self.simulation_config,
            server=self.server,
            llm_manager=self.llm_service,
            agent_profiles=self._agents,
            client_id=self.client_id,
            logger=logger,
        )

        self.lifecycle_manager = LifecycleManager(
            server=self.server,
            client_id=self.client_id,
            config_path=self.config_path,
            simulation_config=self.simulation_config,
            logger=logger,
            add_agent_from_record_func=self._register_agent_from_record,
            existing_usernames_func=lambda: [agent.username for agent in self._agents],
        )

    async def setup(self):
        server_meta = await self.server.register_client.remote(
            client_id=self.client_id,
            client_info={"type": "simulation_client"},
        )
        self._current_day = server_meta["current_day"]
        self._current_hour = server_meta["current_hour"]
        self._run_id = server_meta.get("run_id", str(uuid.uuid4()))
        logger.info(f"Client {self.client_id} registered. Server run_id={self._run_id}")

    async def load_agents(self, user_configs) -> int:
        population = normalize_agent_population_document(user_configs)
        user_records = list(population.get("agents", []))
        self._agents.clear()

        init_round_id = await self.server.get_or_create_round.remote(-1, -1)
        for user_record in user_records:
            try:
                registered_user = await self._register_agent_record(
                    normalize_agent_config(user_record, self.simulation_config),
                    round_id=init_round_id,
                    day=self.simulation_config.get("start_day", 0),
                    initialize_opinions=True,
                )
            except Exception as exc:
                logger.warning(f"Could not register user {user_record.get('id')} or opinions: {exc}")
                registered_user = normalize_agent_config(user_record, self.simulation_config)

            weights = self.round_planner.build_action_weights(registered_user)
            self._agents.append(
                Agent(
                    user_data=registered_user,
                    server=self.server,
                    llm_service=self.llm_service,
                    action_logger=self.action_logger,
                    image_gen_service=self.image_gen_service,
                    action_weights=weights,
                    opinion_manager=self.opinion_manager,
                    stress_reward_system=self.stress_reward_system,
                    stress_reward_enabled=self.stress_reward_enabled,
                    stress_reward_backward_rounds=self.stress_reward_backward_rounds,
                )
            )

        logger.info(f"Client {self.client_id}: loaded {len(self._agents)} agents")
        return len(self._agents)

    async def _register_agent_record(
        self,
        user_record: Dict[str, Any],
        *,
        round_id: str,
        day: int,
        initialize_opinions: bool = False,
    ) -> Dict[str, Any]:
        record = dict(user_record)
        record.setdefault("is_churned", False)
        record.setdefault("left_on", None)
        record.setdefault("last_active_day", None)
        record.setdefault("satisfaction_score", 100.0)
        if "id" not in record or not record["id"]:
            record["id"] = str(uuid.uuid4())
        record["id"] = await self.server.create_user.remote(record)

        if initialize_opinions:
            opinion_config = self.simulation_config.get("opinion_dynamics", {})
            if opinion_config.get("enabled", False):
                topics = self.simulation_config.get("discussion_topics", ["general"])
                groups = opinion_config.get("opinion_groups", {"Neutral": [0.4, 0.6]})
                for topic in topics:
                    bounds = random.choice(list(groups.values()))
                    value = random.uniform(bounds[0], bounds[1])
                    await self.server.update_user_opinion.remote(record["id"], topic, value, round_id)

            topics = self.simulation_config.get("discussion_topics", ["general"])
            topic_ids = []
            topic_lookup = {}
            for topic in topics:
                topic_id = await self.server.get_or_create_interest.remote(topic)
                topic_ids.append(topic_id)
                topic_lookup[topic] = topic_id

            if record.get("interests"):
                user_interest_ids = []
                for topic_name in record["interests"]:
                    if topic_name in topic_lookup:
                        user_interest_ids.append(topic_lookup[topic_name])
                    else:
                        user_interest_ids.append(await self.server.get_or_create_interest.remote(topic_name))
            else:
                user_interest_ids = build_initial_interest_ids(
                    user_config=record,
                    simulation_config=self.simulation_config,
                    topic_ids=topic_ids,
                    topic_lookup=topic_lookup,
                )

            await self.server.set_user_interests.remote(record["id"], user_interest_ids, round_id)
            await self.server.update_last_active_day.remote(record["id"], day)

        return record

    async def _register_agent_from_record(
        self,
        user_record: Dict[str, Any],
        *,
        round_id: str,
        day: int,
    ) -> Dict[str, Any]:
        registered_user = await self._register_agent_record(
            user_record,
            round_id=round_id,
            day=day,
            initialize_opinions=True,
        )
        weights = self.round_planner.build_action_weights(registered_user)
        self._agents.append(
            Agent(
                user_data=registered_user,
                server=self.server,
                llm_service=self.llm_service,
                action_logger=self.action_logger,
                image_gen_service=self.image_gen_service,
                action_weights=weights,
                opinion_manager=self.opinion_manager,
                stress_reward_system=self.stress_reward_system,
                stress_reward_enabled=self.stress_reward_enabled,
                stress_reward_backward_rounds=self.stress_reward_backward_rounds,
            )
        )
        return registered_user

    async def run_round(self, day: int, hour: int) -> dict:
        round_id = await self.server.get_or_create_round.remote(day, hour)
        self._round_count += 1

        start_time = time.time()
        all_results = await self._run_agents_async(day, hour, round_id)
        execution_time_seconds = time.time() - start_time

        # Extract active agents to match results
        active_agents = self.round_planner.select_active_agents(self._agents, hour)

        # Extract and log individual actions
        flat_actions = []
        for agent, agent_results in zip(active_agents, all_results):
            if isinstance(agent_results, list):
                for res in agent_results:
                    if isinstance(res, dict):
                        action_name = res.get("action")
                        if action_name and action_name != "churned":
                            flat_actions.append((agent.username, action_name))

        total_actions = len(flat_actions)
        per_action_time = execution_time_seconds / total_actions if total_actions > 0 else 0.0

        for username, action_name in flat_actions:
            self._log_action(
                agent_name=username,
                method_name=action_name.lower(),
                execution_time_seconds=per_action_time,
                success=True,
                day=day,
                slot=hour,
            )

        # Log hourly summary
        self._log_hourly_summary(day, hour)

        # Log daily summary if last hour of the day
        if hour == 23:
            self._log_daily_summary(day)

        if hour == 23 and self.lifecycle_manager is not None:
            try:
                lifecycle_stats = await self.lifecycle_manager.evaluate_end_of_day(
                    day=day,
                    round_id=round_id,
                    agents=self._agents,
                )
                if self.action_logger:
                    self.action_logger.info(
                        json.dumps({
                            "event": "client_lifecycle_completed",
                            "client_id": self.client_id,
                            "day": day,
                            "round_id": round_id,
                            **lifecycle_stats,
                        })
                    )
            except Exception as exc:
                logger.warning(f"Lifecycle evaluation failed for day {day}: {exc}")

        summary = {
            "client_id": self.client_id,
            "round": self._round_count,
            "day": day,
            "hour": hour,
            "round_id": round_id,
            "agents": len(self._agents),
            "actions": total_actions,
        }
        logger.info(f"Round {day}/{hour} complete: {summary['actions']} actions")
        if self.action_logger:
            self.action_logger.info(
                json.dumps({
                    "event": "client_round_completed",
                    "client_id": self.client_id,
                    "round": self._round_count,
                    "day": day,
                    "hour": hour,
                    "actions": summary["actions"],
                    "agents": len(self._agents),
                })
            )

        await self.server.ready_for_next_round.remote(self.client_id)
        return summary

    async def _run_agents_async(self, day: int, hour: int, round_id: str) -> List[list]:
        active_agents = self.round_planner.select_active_agents(self._agents, hour)
        tasks = [agent.run_round(day, hour, round_id) for agent in active_agents]
        return await asyncio.gather(*tasks, return_exceptions=False)

    def _log_action(
        self,
        agent_name: str,
        method_name: str,
        execution_time_seconds: float,
        success: bool,
        day: int,
        slot: int,
    ):
        """Log an individual agent action in the standardized format."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "time": timestamp,
            "agent_name": agent_name,
            "method_name": method_name,
            "execution_time_seconds": round(execution_time_seconds, 4),
            "success": success,
        }
        if self.action_logger:
            self.action_logger.info(json.dumps(log_entry))

        # Track for hourly/daily summaries
        action_info = {
            "method_name": method_name,
            "execution_time_seconds": execution_time_seconds,
            "success": success,
            "day": day,
            "slot": slot,
        }
        self.hourly_actions.append(action_info)
        self.daily_actions.append(action_info)

    def _log_hourly_summary(self, day: int, slot: int):
        """Log hourly summary with execution time statistics."""
        total_time = sum(a["execution_time_seconds"] for a in self.hourly_actions)
        total_actions = len(self.hourly_actions)
        successful_actions = sum(1 for a in self.hourly_actions if a["success"])

        # Count actions by method
        method_counts = {}
        for action in self.hourly_actions:
            method = action["method_name"]
            method_counts[method] = method_counts.get(method, 0) + 1

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = {
            "time": timestamp,
            "summary_type": "hourly",
            "day": day,
            "slot": slot,
            "total_actions": total_actions,
            "successful_actions": successful_actions,
            "total_execution_time_seconds": round(total_time, 4),
            "average_execution_time_seconds": round(
                total_time / total_actions if total_actions > 0 else 0, 4
            ),
            "actions_by_method": method_counts,
        }
        if self.action_logger:
            self.action_logger.info(json.dumps(summary))
        self.hourly_actions = []

    def _log_daily_summary(self, day: int):
        """Log daily summary with execution time statistics."""
        total_time = sum(a["execution_time_seconds"] for a in self.daily_actions)
        total_actions = len(self.daily_actions)
        successful_actions = sum(1 for a in self.daily_actions if a["success"])

        # Count actions by method
        method_counts = {}
        for action in self.daily_actions:
            method = action["method_name"]
            method_counts[method] = method_counts.get(method, 0) + 1

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = {
            "time": timestamp,
            "summary_type": "daily",
            "day": day,
            "total_actions": total_actions,
            "successful_actions": successful_actions,
            "total_execution_time_seconds": round(total_time, 4),
            "average_execution_time_seconds": round(
                total_time / total_actions if total_actions > 0 else 0, 4
            ),
            "actions_by_method": method_counts,
        }
        if self.action_logger:
            self.action_logger.info(json.dumps(summary))
        self.daily_actions = []

    def get_status(self) -> dict:
        return {
            "client_id": self.client_id,
            "run_id": self._run_id,
            "agents": len(self._agents),
            "rounds_completed": self._round_count,
            "uptime_seconds": time.time() - self._start_time,
        }
