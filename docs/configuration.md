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
    "local_diffusion_model": "segmind/tiny-sd",
    "enable_sentiment": true,
    "discussion_topics": [
      "travel", "food", "fitness", "art", "nature", "fashion", "technology"
    ],
    "opinion_dynamics": {
      "enabled": true,
      "opinion_groups": {
        "Neutral": [0.4, 0.6],
        "Positive": [0.6, 1.0],
        "Negative": [0.0, 0.4]
      }
    },
    "agents": {
      "probability_of_secondary_follow": 0.1,
      "probability_of_follow_back": 0.1
    },
    "actions_likelihood": {
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
    },
    "activity_profiles": {
        "high": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23],
        "medium": [8, 9, 12, 13, 18, 19, 20, 21],
        "low": [19, 20, 21]
    },
    "hourly_activity": {
        "0": 0.2, "1": 0.1, "2": 0.05, "3": 0.05, "4": 0.1, "5": 0.2,
        "6": 0.4, "7": 0.6, "8": 0.8, "9": 0.9, "10": 0.8, "11": 0.8,
        "12": 0.9, "13": 0.9, "14": 0.8, "15": 0.8, "16": 0.8, "17": 0.9,
        "18": 1.0, "19": 1.0, "20": 1.0, "21": 0.9, "22": 0.6, "23": 0.4
    }
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
  "logging": {
    "enable_console_log": true
  }
}
```

### Key Parameters:

- **`simulation.num_rounds`**: How many hours the simulation should run for. E.g., `48` equals exactly 2 in-simulation days.
- **`simulation.use_local_diffusion`**: Setting this to `true` enables dynamic image generation via Hugging Face `diffusers`. It will download and load the model specified in `local_diffusion_model`.
- **`simulation.opinion_dynamics`**: If enabled, agents will evaluate the sentiment of posts matching configured topics and dynamically update their underlying stance and polarization metrics based on exposure.
- **`simulation.discussion_topics`**: Array of topics that are configured within the database for agents to engage with, post about, and build interest profiles for.
- **`simulation.agents`**: Probability mechanics governing secondary follow cascades and followback reciprocity.
- **`llm_vision`**: If populated alongside `use_local_diffusion`, agents will actively use the vision backend to look at the generated images when leaving comments or reactions. Ensure the specified model (e.g., `llama3.2-vision`) supports multimodal inputs.

## 2.1 `prompts_ygram.json`
YPhotoSharing relies on an externalized prompt configuration file (`prompts_ygram.json`) placed within your experiment directory. This file dictates the personas, styles, and task-specific constraints for the LLMs. If this file is missing, the simulation will warn and attempt to fall back to an empty dictionary, which will result in LLM errors.

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
