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
        for i in range(10):
            try:
                self.server = ray.get_actor(server_name, namespace=namespace)
                break
            except ValueError:
                if i == 9:
                    raise
                time.sleep(1)

        # Instantiate LLM service
        llm_config = llm_config or {"address": "localhost", "port": 11434, "model": "llama3.2"}
        prompts_config = prompts_config or {}
        self.llm_service = _build_llm_service(
            llm_config, prompts_config, llm_v_config, logging_config or {}
        )

        from YPhotoSharing.YClient.LLM_interactions.image_generation_service import ImageGenerationService
        use_local_diffusion = self.simulation_config.get("use_local_diffusion", False)
        local_diffusion_model = self.simulation_config.get("local_diffusion_model", "segmind/tiny-sd")
        self.image_gen_service = ImageGenerationService(
            use_local_diffusion=use_local_diffusion,
            local_diffusion_model=local_diffusion_model
        )

        # Register with server
        # Do NOT call ray.get here. It will block the async actor loop.
        pass

    async def setup(self):
        """Asynchronously register with the server."""
        server_meta = await self.server.register_client.remote(
            client_id=self.client_id,
            client_info={"type": "simulation_client"},
        )
        self._current_day = server_meta["current_day"]
        self._current_hour = server_meta["current_hour"]
        self._run_id = server_meta.get("run_id", str(uuid.uuid4()))
        logger.info(
            f"Client {self.client_id} registered. "
            f"Server run_id={self._run_id}"
        )

    # ------------------------------------------------------------------
    # Agent population
    # ------------------------------------------------------------------

    async def load_agents(self, user_configs: List[dict]) -> int:
        """Register agents from user config dicts. Returns number loaded."""
        self._agents = []
        import random
        for u in user_configs:
            # Phase 8: Randomly assign 20% to be private accounts
            if "is_private" not in u:
                u["is_private"] = random.random() < 0.20
            
            # YSimulator Stage 1: Assign activity profile
            if "activity_profile" not in u:
                profiles = list(self.simulation_config.get("activity_profiles", {"Always On": ""}).keys())
                u["activity_profile"] = random.choice(profiles) if profiles else None
            
            # YSimulator Stage 1: Assign archetype
            if "archetype" not in u:
                arch_cfg = self.simulation_config.get("agent_archetypes", {})
                if arch_cfg.get("enabled", False):
                    dist = arch_cfg.get("distribution", {"broadcaster": 0.33, "explorer": 0.34, "validator": 0.33})
                    keys = list(dist.keys())
                    weights = list(dist.values())
                    u["archetype"] = random.choices(keys, weights=weights, k=1)[0]
                else:
                    u["archetype"] = None
            # Register user in the database
            try:
                u["id"] = await self.server.create_user.remote(u)
                
                # Stage 6: Initialize Opinions
                op_dyn = self.simulation_config.get("opinion_dynamics", {})
                u["enable_opinion_dynamics"] = op_dyn.get("enabled", False)
                u["enable_sentiment"] = self.simulation_config.get("enable_sentiment", False)
                
                # Stage 7: Follow Mechanisms
                agent_cfg = self.simulation_config.get("agents", {})
                u["probability_of_secondary_follow"] = agent_cfg.get("probability_of_secondary_follow", 0.1)
                u["probability_of_follow_back"] = agent_cfg.get("probability_of_follow_back", 0.1)
                
                if op_dyn.get("enabled", False):
                    topics = self.simulation_config.get("discussion_topics", ["general"])
                    groups = op_dyn.get("opinion_groups", {"Neutral": [0.4, 0.6]})
                    for topic in topics:
                        group = random.choice(list(groups.values()))
                        val = random.uniform(group[0], group[1])
                        await self.server.update_user_opinion.remote(u["id"], topic, val)
                        
                # Stage 9: Interest Configuration and Dynamics
                topics = self.simulation_config.get("discussion_topics", ["general"])
                topic_ids = []
                for topic in topics:
                    tid = await self.server.get_or_create_interest.remote(topic)
                    topic_ids.append(tid)
                # Assign interests
                user_interests = u.get("interests", [])
                user_interest_ids = []
                if user_interests:
                    for t in user_interests:
                        if t not in topics:
                            # Register the topic if it's new
                            tid = await self.server.get_or_create_interest.remote(t)
                        else:
                            tid = topic_ids[topics.index(t)]
                        user_interest_ids.append(tid)
                else:
                    # Fallback Assign 1 to 3 random interests to the user
                    num_interests = random.randint(1, min(3, max(1, len(topic_ids))))
                    user_interest_ids = random.sample(topic_ids, num_interests) if topic_ids else []
                
                # Use a dummy round_id "init" for initial interests
                await self.server.set_user_interests.remote(u["id"], user_interest_ids, "init")
                
            except Exception as e:
                logger.warning(f"Could not register user {u.get('id')} or opinions: {e}")
            # YSimulator Stage 3: Calculate dynamic action_weights
            base_weights = self.simulation_config.get("actions_likelihood", {
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
                "watch_story": 0.05
            })
            weights = base_weights.copy()
            if "post" in weights: weights["post_photo"] = weights.pop("post")
            if "read" in weights: weights["react"] = weights.pop("read")
            
            archetype = u.get("archetype")
            if archetype == "broadcaster":
                weights["post_photo"] = weights.get("post_photo", 0) * 2.0
                weights["post_story"] = weights.get("post_story", 0) * 2.0
            elif archetype == "explorer":
                weights["watch_story"] = weights.get("watch_story", 0) * 2.0
                weights["react"] = weights.get("react", 0) * 2.0
            elif archetype == "validator":
                weights["comment"] = weights.get("comment", 0) * 2.0
                weights["react"] = weights.get("react", 0) * 1.5

            self._agents.append(Agent(
                user_data=u, 
                server=self.server, 
                llm_service=self.llm_service,
                image_gen_service=self.image_gen_service,
                action_weights=weights
            ))
        logger.info(f"Client {self.client_id}: loaded {len(self._agents)} agents")
        return len(self._agents)

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    async def run_round(self, day: int, hour: int) -> dict:
        """
        Execute one simulation round for all agents managed by this client.
        Returns a summary dict.
        """
        round_id = await self.server.get_or_create_round.remote(day, hour)
        self._round_count += 1

        all_results = await self._run_agents_async(day, hour, round_id)

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
        await self.server.ready_for_next_round.remote(self.client_id)
        return summary

    async def _run_agents_async(self, day: int, hour: int,
                                 round_id: str) -> List[list]:
        import random
        profiles = self.simulation_config.get("activity_profiles", {})
        hourly_activity = self.simulation_config.get("hourly_activity", {})
        
        active_agents = []
        for agent in self._agents:
            u_profile = agent.user_data.get("activity_profile")
            
            # Check profile
            if u_profile and u_profile in profiles:
                try:
                    active_hours = [int(h) for h in profiles[u_profile].split(",")]
                    if hour in active_hours:
                        active_agents.append(agent)
                except ValueError:
                    # Fallback on parse error
                    pass
                continue
            
            # If no profile or unknown, use hourly_activity
            prob = hourly_activity.get(str(hour), 0.04)
            if random.random() < float(prob):
                active_agents.append(agent)

        tasks = [agent.run_round(day, hour, round_id) for agent in active_agents]
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
