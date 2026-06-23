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
from pathlib import Path

import ray

from YPhotoSharing.common_utils import validate_config_directory
from YPhotoSharing.YClient.client import SimulationClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("YPhotoSharing.Client")


def main():
    parser = argparse.ArgumentParser(
        description="YPhotoSharing Client – simulation agent runner"
    )
    parser.add_argument(
        "--config", type=str, default=".",
        help="Path to config directory containing client_config.json",
    )
    args = parser.parse_args()

    config_dir = validate_config_directory(args.config, required_files=["client_config.json"])
    config_file = config_dir / "client_config.json"

    with open(config_file) as f:
        config = json.load(f)

    # Ray connection – read address written by server
    ray_config_file = config_dir / "ray_config.temp"
    namespace_file = config_dir / "ray_namespace.temp"
    namespace = config.get("namespace", "yphotosharing")
    if namespace_file.exists():
        namespace = namespace_file.read_text().strip()

    address = config.get("address", "auto")
    if ray_config_file.exists() and address == "auto":
        address = ray_config_file.read_text().strip()

    ray.init(address=address, namespace=namespace, include_dashboard=False)
    print(f"--- 🔗 Connected to Ray cluster ---")

    client_id = config.get("client_id") or str(uuid.uuid4())
    server_name = config.get("server_name", "Orchestrator")

    llm_config = config.get("llm", {})
    prompts_config = config.get("prompts", {})
    llm_v_config = config.get("llm_vision")
    logging_config = config.get("logging", {})
    simulation_config = config.get("simulation", {})

    # Load user population
    users_file = config_dir / config.get("users_file", "users.json")
    if not users_file.exists():
        logger.error(f"Users file not found: {users_file}")
        sys.exit(1)
    with open(users_file) as f:
        users = json.load(f)

    num_rounds = simulation_config.get("num_rounds", 24)
    start_day = simulation_config.get("start_day", 0)

    # Spin up client actor
    client_actor = SimulationClient.options(name=f"Client_{client_id}").remote(
        client_id=client_id,
        server_name=server_name,
        namespace=namespace,
        llm_config=llm_config,
        prompts_config=prompts_config,
        llm_v_config=llm_v_config,
        logging_config=logging_config,
        simulation_config=simulation_config,
    )

    n_loaded = ray.get(client_actor.load_agents.remote(users))
    print(f"--- 👤 Loaded {n_loaded} agents ---")
    print(f"--- ▶  Running {num_rounds} rounds ---")

    for round_num in range(num_rounds):
        day = start_day + round_num // 24
        hour = round_num % 24
        summary = ray.get(client_actor.run_round.remote(day=day, hour=hour))
        print(
            f"  Round {round_num + 1:>4}/{num_rounds}  "
            f"day={summary['day']} hour={summary['hour']}  "
            f"actions={summary['actions']}"
        )

    print("--- ✅ Simulation complete ---")
    ray.shutdown()


if __name__ == "__main__":
    main()
