"""Start-up preparation of the clients of a photo-sharing experiment."""

import json
import os
from pathlib import Path

from y_web.sdk import runtime


def migrate_legacy_layout(
    exp_folder: str, client_name: str, population_name: str, client_config_path: str
) -> None:
    """Promote legacy per-client photo-sharing config into the standard HPC layout."""
    if os.path.exists(client_config_path):
        return

    legacy_dir = os.path.join(exp_folder, f"client_{client_name}-{population_name}")
    legacy_config = os.path.join(legacy_dir, "client_config.json")
    if not os.path.exists(legacy_config):
        return

    with open(legacy_config, "r", encoding="utf-8") as handle:
        client_config = json.load(handle)
    with open(client_config_path, "w", encoding="utf-8") as handle:
        json.dump(client_config, handle, indent=2)


def normalize_client_config(
    exp_folder: str, client_name: str, population_name: str, client_config_path: str
) -> None:
    """Align YPhotoSharing client config with the experiment server runtime."""
    server_config_path = os.path.join(exp_folder, "server_config.json")
    server_config = {}
    if os.path.exists(server_config_path):
        with open(server_config_path, "r", encoding="utf-8") as handle:
            server_config = json.load(handle)

    with open(client_config_path, "r", encoding="utf-8") as handle:
        client_config = json.load(handle)

    runtime_client_id = runtime.build_hpc_runtime_client_id(exp_folder, client_name)
    client_config["client_id"] = runtime_client_id
    client_config["namespace"] = server_config.get("namespace", "yphotosharing")
    client_config["server_name"] = server_config.get(
        "server_name", "orchestrator_server"
    )
    client_config["address"] = "auto"
    population_filename = f"{population_name}.json"
    client_config["agents_file"] = population_filename
    client_config["users_file"] = population_filename
    client_config.setdefault("logging", {})
    client_config["logging"]["log_dir"] = os.path.join(exp_folder, "logs")
    client_config["logging"]["instance_name"] = runtime_client_id

    with open(client_config_path, "w", encoding="utf-8") as handle:
        json.dump(client_config, handle, indent=2)


def finish_client_config(
    config: dict, form, exp_dir: str, population_name: str
) -> None:
    """Align a client file that has just been generated with the experiment server."""
    server_config_filename = os.path.join(exp_dir, "server_config.json")
    server_config = {}
    if os.path.exists(server_config_filename):
        with open(server_config_filename, "r", encoding="utf-8") as handle:
            server_config = json.load(handle)

    runtime_client_id = f"{Path(exp_dir).name}:{form.name}"
    config["client_id"] = runtime_client_id
    config["namespace"] = server_config.get("namespace", "yphotosharing")
    config["server_name"] = server_config.get("server_name", "orchestrator_server")
    config["address"] = "auto"
    config["agents_file"] = f"{population_name}.json"
    config["users_file"] = f"{population_name}.json"
    config["llm_vision"] = form.llm_v_config
    config.pop("llm_v", None)
    config.pop("agents", None)
    config.setdefault("logging", {})
    config["logging"]["log_dir"] = os.path.join(exp_dir, "logs")
    config["logging"]["instance_name"] = runtime_client_id
