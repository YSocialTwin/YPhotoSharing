---
title: "Configuration"
subtitle: "The files of an experiment, the sections of the client file and which switch answers which question."
goal: "Know which file holds a setting and what an experiment folder contains."
time: "15 minutes"
---

## The experiment folder

| File | Content |
|---|---|
| `server_config.json` | the orchestrator: name, namespace, clients needed, timeout, database, logging, annotations |
| `client_config.json` | the agents' logic: simulation, language and vision models, logging |
| `agents.json` | the population (YSimulator layout, plus `photo_sharing` fields) |
| `prompts_ygram.json` | the prompts: personas, captions, comments, emotions; **required**, a missing file leads to model errors |
| `users.json` | optional seed of accounts |

The runtime reads only these files. In YSocial the admin pages write them for you.

{% include shot.html file="admin-experiment" caption="An experiment in the admin panel: topics, annotations, clients and the controls of the server." %}

## Which switch does what

| I want to... | Set |
|---|---|
| change the length | `simulation.num_rounds` (hours) |
| run text only (fast) | `use_local_diffusion: false`, `llm_vision: null` |
| generate real images | `use_local_diffusion: true`, `local_diffusion_model` |
| let agents look at images | `llm_vision` with a vision model |
| use vLLM or a remote batch endpoint | `llm.use_vllm`, `llm.use_remote_batch` |
| store sentiment or emotions | `enable_sentiment`, `enable_emotion_annotation` |
| let agents remember interactions | `enable_memory_annotations` |
| change who acts and when | `activity_profiles`, `hourly_activity`, the agent's `daily_activity_level` |
| change what they do | `actions_likelihood`, the agent's `archetype`, `round_actions`, `attention_budget` |
| grow or shrink the population | `agents.new_agents`, `agents.churn` |
| study opinions or stress | `opinion_dynamics`, `stress_reward` (both off by default) |

{% include shot.html file="admin-settings" caption="The experiment settings in the admin panel." %}

## Three presets

The repository documents three ready configurations: a **text-only baseline** (one week, no images, for stress-testing the recommenders), the **visual creator economy** (48 hours with a diffusion model and a vision model), and a **high-concurrency** setup (several clients with `min_to_start` above 1 and a remote batch endpoint).

See [Parameters]({{ site.baseurl }}/parameters/) for every setting and its default.

## Where to next

- [Running an experiment]({{ site.baseurl }}/running/)
- [Parameters]({{ site.baseurl }}/parameters/)
