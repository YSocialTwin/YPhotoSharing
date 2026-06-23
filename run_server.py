"""
Server entry point for YPhotoSharing.

Initialises the database, starts Ray, and launches the OrchestratorServer actor.
Usage::

    python run_server.py --config path/to/config_dir

The config directory must contain a ``server_config.json`` file.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import ray

from YPhotoSharing.common_utils import validate_config_directory
from YPhotoSharing.utils.init_db import database_exists, initialize_database
from YPhotoSharing.YServer.server import OrchestratorServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("YPhotoSharing.Server")


def main():
    parser = argparse.ArgumentParser(
        description="YPhotoSharing Server – Ray-based Instagram-like simulation orchestrator"
    )
    parser.add_argument(
        "--config", type=str, default=".",
        help="Path to config directory containing server_config.json",
    )
    args = parser.parse_args()

    config_dir = validate_config_directory(args.config, required_files=["server_config.json"])
    config_file = config_dir / "server_config.json"

    with open(config_file) as f:
        config = json.load(f)

    server_name = config.get("server_name", "orchestrator_server")
    namespace = config.get("namespace", "yphotosharing")
    min_to_start = config.get("min_to_start", 1)
    timeout_seconds = config.get("timeout_seconds", 60)

    # Database config
    db_config = config.get("database", {}) or {"type": "sqlite", "sqlite": {"filename": "yphotosharing.db"}}
    simulation_config = config.get("simulation", {})

    # Initialise DB if needed
    if not database_exists(db_config, config_dir):
        print(f"--- 🔧 Initialising database ---")
        if not initialize_database(db_config, config_dir, logger):
            logger.error("Failed to initialise database.")
            sys.exit(1)
        print("--- ✅ Database ready ---")
    else:
        print("--- 💾 Using existing database ---")

    # Start Ray
    try:
        ray.init(address="auto", namespace=namespace, include_dashboard=False)
        print("--- Reusing existing Ray cluster ---")
    except Exception:
        ray.init(namespace=namespace, include_dashboard=False)
        print("--- Started new Ray cluster ---")

    # Write connection info for clients
    gcs_address = ray.get_runtime_context().gcs_address
    (config_dir / "ray_config.temp").write_text(gcs_address)
    (config_dir / "ray_namespace.temp").write_text(namespace)

    print(f"--- 🚀 Server Running ---")
    print(f"--- 📝 Server Name: {server_name} ---")
    print(f"--- 📝 Namespace:   {namespace} ---")
    print(f"--- 💾 Database:    {db_config.get('type','sqlite').upper()} ---")
    print("--- 💾 Waiting for clients... ---")

    # Launch orchestrator actor
    try:
        old_actor = ray.get_actor(server_name, namespace=namespace)
        ray.kill(old_actor)
    except ValueError:
        pass

    server_actor = OrchestratorServer.options(name=server_name, namespace=namespace).remote(
        db_config=db_config,
        config_path=str(config_dir),
        min_to_start=min_to_start,
        server_name=server_name,
        timeout_seconds=timeout_seconds,
        simulation_config=simulation_config,
    )

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server…")
        for tmp in ["ray_config.temp", "ray_namespace.temp"]:
            p = config_dir / tmp
            if p.exists():
                p.unlink()
        ray.shutdown()
        print("Server stopped.")


if __name__ == "__main__":
    main()
