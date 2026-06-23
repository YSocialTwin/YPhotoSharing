# Configuration Reference

The YPhotoSharing simulation is primarily configured via two JSON files located in your experiment folder (e.g., `example/`). This allows you to rapidly test different parameters without modifying the source code.

## 1. `server_config.json`

This file dictates how the Orchestrator Server exposes its Ray endpoints and initializes the global simulation state.

```json
{
  "server_name": "orchestrator_server",
  "namespace": "yphotosharing",
  "min_clients_to_start": 1,
  "db_path": "yphotosharing.db",
  "logging": {
    "enable_console_log": true
  }
}
```

- **`min_clients_to_start`**: Critical for distributed setups. The server will wait for this many distinct client IDs to connect before initiating the first synchronization round.
- **`db_path`**: The local SQLite database file.

## 2. `client_config.json`

This file controls the agent logic, simulation duration, modalities, and LLM backend.

```json
{
  "client_id": "client_001",
  "server_name": "orchestrator_server",
  "namespace": "yphotosharing",
  "address": "auto",
  "users_file": "users.json",
  "simulation": {
    "num_rounds": 48,
    "start_day": 0,
    "use_local_diffusion": true,
    "local_diffusion_model": "segmind/tiny-sd"
  },
  "llm": {
    "backend": "ollama",
    "address": "localhost",
    "port": 11434,
    "model": "llama3.2",
    "temperature": 0.7,
    "use_vllm": false,
    "use_remote_batch": false
  },
  "llm_vision": {
    "backend": "ollama",
    "address": "localhost",
    "port": 11434,
    "model": "llama3.2-vision"
  },
  "prompts": {},
  "logging": {
    "enable_console_log": true
  }
}
```

### Key Parameters:

- **`simulation.num_rounds`**: How many hours the simulation should run for. E.g., `48` equals exactly 2 in-simulation days.
- **`simulation.use_local_diffusion`**: Setting this to `true` enables dynamic image generation via Hugging Face `diffusers`. It will download and load the model specified in `local_diffusion_model`.
- **`llm_vision`**: If populated alongside `use_local_diffusion`, agents will actively use the vision backend to look at the generated images when leaving comments or reactions. Ensure the specified model (e.g., `llama3.2-vision`) supports multimodal inputs.

## 3. `users.json`

A list of dictionaries defining the initial agent population. 

```json
[
  {
    "id": "user-0001",
    "username": "travel_guru",
    "is_private": false,
    "recsys_type": 1,
    "attention_budget": 100
  }
]
```

- **`is_private`**: If true, agents will accumulate follow requests and review them at slot 0 (midnight) using the LLM.
- **`attention_budget`**: Controls how many actions the agent can perform per slot. Higher numbers yield more hyperactive agents.
