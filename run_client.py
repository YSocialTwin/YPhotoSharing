"""
Client entry point for YPhotoSharing.

Connects to a running OrchestratorServer, loads agents and runs the
simulation for the configured number of rounds.
Usage::

    python run_client.py --config path/to/config_dir

The config directory must contain a ``client_config.json`` file.
"""

import argparse
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import ray

from YPhotoSharing.common_utils import validate_config_directory, setup_logging
from YPhotoSharing.YClient.client import SimulationClient
from YPhotoSharing.YClient.simulation.bootstrap import normalize_agent_population_document

logger = logging.getLogger("YPhotoSharing.Client")


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _state_path_for_config(config_file: Path) -> Path:
    return config_file.with_suffix(".state.json")


def _load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {}
    try:
        with open(state_path, "r", encoding="utf-8") as handle:
            state = json.load(handle)
        return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def _write_state(state_path: Path, payload: dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    tmp_path.replace(state_path)


def main():
    parser = argparse.ArgumentParser(
        description="YPhotoSharing Client – simulation agent runner"
    )
    parser.add_argument(
        "--config", type=str, default=".",
        help="Path to config directory containing client_config.json",
    )
    args = parser.parse_args()

    config_input = Path(args.config).expanduser().resolve()
    if config_input.is_file():
        config_dir = config_input.parent
        config_file = config_input
        if not config_file.exists():
            print(f"❌ Error: Configuration file does not exist: '{config_file}'")
            sys.exit(1)
    else:
        config_dir = validate_config_directory(
            args.config, required_files=["client_config.json"]
        )
        config_file = config_dir / "client_config.json"

    with open(config_file) as f:
        config = json.load(f)
        
    global logger
    # Ray connection – read address written by server
    ray_config_file = config_dir / "ray_config.temp"
    namespace_file = config_dir / "ray_namespace.temp"
    namespace = config.get("namespace", "yphotosharing")
    if namespace_file.exists():
        namespace = namespace_file.read_text().strip()

    client_id = config.get("client_id") or str(uuid.uuid4())
    logging_config = dict(config.get("logging", {}) or {})
    logging_config.setdefault("log_dir", str(config_dir / "logs"))
    logging_config.setdefault("instance_name", client_id)
    logger = setup_logging(config_dir, "client", logging_config, instance_name=client_id)

    address = config.get("address", "auto")
    if ray_config_file.exists() and address == "auto":
        address = ray_config_file.read_text().strip()

    ray.init(address=address, namespace=namespace, include_dashboard=False)
    print(f"--- 🔗 Connected to Ray cluster ---")

    server_name = config.get("server_name", "Orchestrator")

    llm_config = config.get("llm", {})
    
    # Phase 8: Externalize Prompts
    prompts_file = config_dir / "prompts_ygram.json"
    if prompts_file.exists():
        with open(prompts_file) as f:
            prompts_config = json.load(f)
    else:
        prompts_config = config.get("prompts", {})
        logger.warning(f"prompts_ygram.json not found in {config_dir}, falling back to client_config prompts or empty")
        
    llm_v_config = config.get("llm_vision")
    logging_config = config.get("logging", {})
    simulation_config = config.get("simulation", {})
    state_path = _state_path_for_config(config_file)
    state = _load_state(state_path)
    if "completed_rounds" not in state and "elapsed_rounds" in state:
        state["completed_rounds"] = state.get("elapsed_rounds", 0)
    start_round = int(state.get("completed_rounds") or state.get("elapsed_rounds") or 0)
    if start_round < 0:
        start_round = 0

    # Load agent population
    population_filename = config.get("agents_file") or config.get("users_file") or "agents.json"
    population_file = config_dir / population_filename
    if not population_file.exists():
        legacy_file = config_dir / "users.json"
        if population_filename == "agents.json" and legacy_file.exists():
            population_file = legacy_file
        else:
            logger.error(f"Agent population file not found: {population_file}")
            sys.exit(1)
    with open(population_file) as f:
        users = normalize_agent_population_document(json.load(f))

    num_rounds = simulation_config.get("num_rounds", 24)
    start_day = simulation_config.get("start_day", 0)
    slots_per_day = int(simulation_config.get("num_slots_per_day", 24) or 24)
    start_round = min(start_round, num_rounds)

    from YPhotoSharing.YClient.LLM_interactions.vision_service import VisionService

    # Spin up or get Vision Service actor
    try:
        vision_actor = ray.get_actor("VisionService", namespace=namespace)
    except ValueError:
        vision_actor = VisionService.options(name="VisionService", namespace=namespace).remote(config=llm_v_config or {})

    # Spin up client actor
    client_actor = SimulationClient.options(name=f"Client_{client_id}").remote(
        client_id=client_id,
        server_name=server_name,
        namespace=namespace,
        config_path=str(config_dir),
        llm_config=llm_config,
        prompts_config=prompts_config,
        llm_v_config=llm_v_config,
        logging_config=logging_config,
        simulation_config=simulation_config,
    )

    # Call async setup method
    ray.get(client_actor.setup.remote())

    n_loaded = ray.get(client_actor.load_agents.remote(users))
    print(f"--- 👤 Loaded {n_loaded} agents ---")
    if start_round > 0:
        print(f"--- ↻ Resuming from round {start_round + 1} of {num_rounds} ---")
    print(f"--- ▶  Running {num_rounds - start_round} remaining rounds ---")

    if start_round >= num_rounds:
        state.update(
            {
                "completed": True,
                "completed_rounds": num_rounds,
                "elapsed_rounds": num_rounds,
                "expected_duration_rounds": num_rounds,
                "progress": 100 if num_rounds > 0 else 0,
                "updated_at": _now_iso(),
            }
        )
        _write_state(state_path, state)
        print("--- ✅ Simulation already completed ---")
        ray.shutdown()
        return

    for round_num in range(start_round, num_rounds):
        day = start_day + round_num // slots_per_day
        hour = round_num % slots_per_day
        summary = ray.get(client_actor.run_round.remote(day=day, hour=hour))
        state.update(
            {
                "version": 1,
                "completed_rounds": round_num + 1,
                "elapsed_rounds": round_num + 1,
                "last_round_id": summary.get("round_id"),
                "last_day": day,
                "last_hour": hour,
                "expected_duration_rounds": num_rounds,
                "progress": (
                    0
                    if num_rounds <= 0
                    else min(100, int(((round_num + 1) / num_rounds) * 100))
                ),
                "completed": False,
                "updated_at": _now_iso(),
            }
        )
        _write_state(state_path, state)
        print(
            f"  Round {round_num + 1:>4}/{num_rounds}  "
            f"day={summary['day']} hour={summary['hour']}  "
            f"actions={summary['actions']}"
        )

    state.update(
        {
            "completed": True,
            "progress": 100 if num_rounds > 0 else 0,
            "updated_at": _now_iso(),
        }
    )
    _write_state(state_path, state)
    print("--- ✅ Simulation complete ---")
    ray.shutdown()


if __name__ == "__main__":
    main()
