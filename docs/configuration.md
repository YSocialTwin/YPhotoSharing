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
  "agents_file": "agents.json",
  "simulation": {
    "num_rounds": 48,
    "start_day": 0,
    "use_local_diffusion": true,
    "local_diffusion_model": "segmind/tiny-sd",
    "enable_emotion_annotation": true,
    "enable_sentiment": true,
    "enable_memory_annotations": true,
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
      "probability_of_follow_back": 0.1,
      "churn": {
        "enabled": false,
        "churn_probability": 0.0,
        "inactivity_threshold": 5,
        "churn_percentage": 0.0
      },
      "new_agents": {
        "enabled": false,
        "probability_new_agents": 0.0,
        "percentage_new_agents": 0.0
      }
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
- **`simulation.enable_emotion_annotation`**: When enabled, newly generated photos store a visual emotion label in `photo_emotions`.
- **`simulation.opinion_dynamics`**: If enabled, agents will evaluate the sentiment of posts matching configured topics and dynamically update their underlying stance and polarization metrics based on exposure.
- **`simulation.opinion_dynamics.model_name`**: Selects the opinion update engine. Use `bounded_confidence` for continuous updates or `llm_evaluation` for discrete Likert-step transitions.
- **`simulation.opinion_dynamics.likert_scale`**: Ordered opinion classes used by the discrete evaluator. The recommended default is a 5-point scale from strongly disagree to strongly agree.
- **`simulation.discussion_topics`**: Array of topics that are configured within the database for agents to engage with, post about, and build interest profiles for.
- **`simulation.agents`**: Probability mechanics governing secondary follow cascades and followback reciprocity.
- **`simulation.agents.churn`**: Client-side churn controls. Set `enabled` to `true` to allow inactive agents to churn, and tune `churn_probability`, `inactivity_threshold`, and `churn_percentage` to control how aggressive the churn pass is.
- **`simulation.agents.new_agents`**: Client-side new-user injection controls. Set `enabled` to `true` and configure `probability_new_agents` and `percentage_new_agents` to control how many agents are introduced from the existing population templates.
- **`simulation.enable_sentiment`**: Enables sentiment extraction for photos and comments.
- **`simulation.enable_memory_annotations`**: Enables memory-event persistence and memory-context injection for comments and direct messages.
- **`llm_vision`**: If populated alongside `use_local_diffusion`, agents will actively use the vision backend to look at the generated images when leaving comments or reactions. Ensure the specified model (e.g., `llama3.2-vision`) supports multimodal inputs.

Opinion updates are persisted in two layers:

- `user_opinions` stores the latest opinion per user/topic/round
- `opinion_paths` stores the transition trace, including model, source label, target label, and transition direction

### Logging

Both the launcher and the Ray actors use YSimulator-style structured execution logs:

- client execution logs are written to `logs/<client_id>_execution.log`
- server execution logs are written to `logs/<server_name>_server.log`
- actor logs are written to `logs/<client_id>_actor.log` and `logs/<server_name>_actor.log`
- server request traces are written to `logs/_server.log`
- client LLM usage traces are written to `logs/<client_id>_llm_usage.log`
- rotated logs are compressed with gzip and keep the same JSON content structure as YSimulator
- request and usage streams are newline-delimited JSON records with simulator-compatible payloads

Supported logging keys are:

- `logging.enable_console_log`
- `logging.enable_execution_log` for the client
- `logging.enable_server_log` for the server
- `logging.enable_actor_log` for the shared actor-side structured stream
- `logging.enable_request_log` for the server request trace stream
- `logging.enable_action_log` for the client action summary stream
- `logging.enable_prompt_log` for the client prompt trace stream
- `logging.enable_llm_usage_log` for the client LLM usage stream

For a compact summary of the annotation toggles, see
[Annotations](annotations.md).

## 2.1 `prompts_ygram.json`
YPhotoSharing relies on an externalized prompt configuration file (`prompts_ygram.json`) placed within your experiment directory. This file dictates the personas, styles, and task-specific constraints for the LLMs. If this file is missing, the simulation will warn and attempt to fall back to an empty dictionary, which will result in LLM errors.

## 2.2 Stress/Reward Configuration

The affective dynamics module accepts a `stress_reward` section either at the top level or under `simulation`. The client normalizes both shapes and forwards the resulting settings to the `StressRewardSystem`.

```json
{
  "simulation": {
    "stress_reward": {
      "enabled": true,
      "backward_rounds": 24,
      "system": {
        "churn": {
          "enabled": true,
          "stress_weight": 1.5,
          "reward_weight": 1.0
        }
      }
    }
  }
}
```

- **`enabled`**: Turns the stress/reward loop on for eligible interaction paths.
- **`backward_rounds`**: Controls how many rounds the client queries when reconstructing current affective state.
- **`system`**: Allows tuning the affective response curves without changing client logic.

## 3. `agents.json`

A YSimulator-style JSON document defining the initial agent population.
The top level should contain an `agents` array, and may also include a
`generation_config` block for compatibility with YSimulator population files.

```json
{
  "agents": [
    {
      "id": "user-0001",
      "username": "travel_guru",
      "email": "travel_guru@example.com",
      "password": "hashed_pw",
      "user_type": "llm",
      "age": 28,
      "gender": "female",
      "nationality": "US",
      "education_level": "college",
      "profession": "traveler",
      "leaning": "neutral",
      "oe": "high",
      "co": "medium",
      "ex": "high",
      "ag": "medium",
      "ne": "low",
      "language": "en",
      "activity_profile": "medium",
      "archetype": "explorer",
      "recsys_type": "0",
      "frecsys_type": "default",
      "interests": ["travel", "food"],
      "opinions": {
        "travel": 0.7,
        "food": 0.6
      },
      "stubborn_topics": [],
      "custom_features": {
        "aesthetic": "warm travel diary"
      },
      "daily_activity_level": 2,
      "round_actions": 4,
      "is_page": 0,
      "is_private": false,
      "is_verified": false,
      "attention_budget": 100,
      "photo_sharing": {
        "cover_image": "travel_cover.jpg",
        "favorite_filters": ["warm", "vintage"],
        "story_visibility": "followers",
        "creator_tier": "standard"
      }
    }
  ],
  "generation_config": {
    "num_additional_agents": 0,
    "default_settings": {}
  }
}
```

- **`photo_sharing`**: Optional nested block for photo-platform-only fields such as `cover_image`, `story_visibility`, `favorite_filters`, or `creator_tier`.
- **Prompt personas**: the client builds LLM personas from the full agent record, including age, gender, nationality, education, profession, personality traits, interests, bio, account status, and any `custom_features` you provide. `photo_sharing` metadata is also surfaced when present.
- **`user_type`**: Set to `llm` for prompt-driven agents or `rule_based` for deterministic agents. The loader maps this to the internal `llm` flag.
- **`recsys_type`**: The platform's coarse persona cluster. YPhotoSharing does not require a separate `cluster` field in `agents.json`; the recsys type already serves that role for prompts and recommendation bias.
- **`daily_activity_level`**: Fallback activity weight used by the scheduler when an agent does not have a hard hourly `activity_profile` match. Higher values make the agent more likely to be selected for a slot.
- **`round_actions`**: Upper bound for how many actions an agent will attempt once selected for a slot. The actual count is sampled around that bound.
- **`attention_budget`**: Controls the total action cost the agent can spend per slot. Even if `round_actions` is high, expensive actions stop the session early when the budget runs out.
- **`is_private`**: If true, agents will accumulate follow requests and review them at slot 0 (midnight) using the LLM.
