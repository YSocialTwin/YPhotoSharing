"""
Ray Client actor for YPhotoSharing.

Manages a pool of agents, coordinates with the OrchestratorServer and drives
the simulation loop.  Only client-side code lives here; all DB access goes
through the server's remote API.
"""

import asyncio
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import ray

from YPhotoSharing.YClient.agent_management.agent import Agent

logger = logging.getLogger(__name__)


def _build_llm_service(llm_config: dict, prompts_config: dict,
                       llm_v_config: Optional[dict], logging_config: dict):
    """Instantiate the correct LLM service actor based on configuration."""
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
    # Default: standard Ollama
    from YPhotoSharing.YClient.LLM_interactions.llm_service import LLMService
    return LLMService.remote(
        llm_config=llm_config,
        prompts_config=prompts_config,
        llm_v_config=llm_v_config,
        logging_config=logging_config,
    )


@ray.remote
class SimulationClient:
    """
    Ray remote actor representing one simulation client process.

    A single client manages a slice of the agent population and drives them
    through simulation rounds by calling the OrchestratorServer.
    """

    def __init__(
        self,
        client_id: str,
        server_name: str,
        namespace: str,
        llm_config: Optional[Dict[str, Any]] = None,
        prompts_config: Optional[Dict[str, Any]] = None,
        llm_v_config: Optional[Dict[str, Any]] = None,
        logging_config: Optional[Dict[str, Any]] = None,
        simulation_config: Optional[Dict[str, Any]] = None,
    ):
        self.client_id = client_id
        self.simulation_config = simulation_config or {}
        self._agents: List[Agent] = []
        self._round_count = 0
        self._start_time = time.time()

        # Connect to server
        self.server = ray.get_actor(server_name, namespace=namespace)

        # Instantiate LLM service
        llm_config = llm_config or {"address": "localhost", "port": 11434, "model": "llama3.2"}
        prompts_config = prompts_config or {}
        self.llm_service = _build_llm_service(
            llm_config, prompts_config, llm_v_config, logging_config or {}
        )

        # Register with server
        server_meta = ray.get(self.server.register_client.remote(
            client_id=client_id,
            client_info={"client_id": client_id},
        ))
        self._run_id = server_meta.get("run_id", str(uuid.uuid4()))
        logger.info(
            f"SimulationClient {client_id} connected "
            f"(run_id={self._run_id}, server={server_name})"
        )

    # ------------------------------------------------------------------
    # Agent population
    # ------------------------------------------------------------------

    def load_agents(self, user_configs: List[dict]) -> int:
        """Register agents from user config dicts. Returns number loaded."""
        self._agents = [
            Agent(user_data=u, server=self.server, llm_service=self.llm_service)
            for u in user_configs
        ]
        logger.info(f"Client {self.client_id}: loaded {len(self._agents)} agents")
        return len(self._agents)

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def run_round(self, day: int, hour: int) -> dict:
        """
        Execute one simulation round for all agents managed by this client.
        Returns a summary dict.
        """
        round_id = ray.get(self.server.get_or_create_round.remote(day, hour))
        self._round_count += 1

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            all_results = loop.run_until_complete(
                self._run_agents_async(day, hour, round_id)
            )
        finally:
            loop.close()

        summary = {
            "client_id": self.client_id,
            "round": self._round_count,
            "day": day,
            "hour": hour,
            "agents": len(self._agents),
            "actions": sum(len(r) for r in all_results),
        }
        logger.info(f"Round {day}/{hour} complete: {summary['actions']} actions")

        # Signal readiness to advance
        ray.get(self.server.ready_for_next_round.remote(self.client_id))
        return summary

    async def _run_agents_async(self, day: int, hour: int,
                                 round_id: str) -> List[list]:
        tasks = [agent.run_round(day, hour, round_id) for agent in self._agents]
        return await asyncio.gather(*tasks, return_exceptions=False)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        return {
            "client_id": self.client_id,
            "run_id": self._run_id,
            "agents": len(self._agents),
            "rounds_completed": self._round_count,
            "uptime_seconds": time.time() - self._start_time,
        }
