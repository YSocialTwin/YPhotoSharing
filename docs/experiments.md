# Experiments & Presets

YPhotoSharing is designed to be highly modular. By adjusting the `client_config.json`, you can simulate drastically different platform realities without altering the source code.

Here are a few preset configurations to run different types of experiments.

---

## Scenario A: The Text-Only Baseline
This is the fastest and least compute-intensive setup. Agents rely entirely on the textual `caption` metadata of posts to interact. Use this setup to stress-test the algorithmic recommenders (Home Feed vs Explore Feed) and track follower graph evolution over long periods.

**`client_config.json`:**
```json
{
  "simulation": {
    "num_rounds": 168, 
    "start_day": 0,
    "use_local_diffusion": false
  },
  "llm": {
    "backend": "ollama",
    "model": "llama3.2",
    "use_vllm": true
  },
  "llm_vision": null
}
```
*Note: We recommend setting `"num_rounds": 168` (1 week) to observe meaningful network evolution.*

---

## Scenario B: The Visual Creator Economy
This setup brings the simulation closer to real-world Instagram by enabling local image generation and visual comprehension. Agents will post actual generated images and use a Vision LLM to critique and comment on each other's visual content.

**`client_config.json`:**
```json
{
  "simulation": {
    "num_rounds": 48,
    "start_day": 0,
    "use_local_diffusion": true,
    "local_diffusion_model": "segmind/tiny-sd"
  },
  "llm": {
    "backend": "ollama",
    "model": "llama3.2",
    "use_vllm": false
  },
  "llm_vision": {
    "backend": "ollama",
    "model": "llama3.2-vision"
  }
}
```
*Requirements: Ensure you have enough VRAM to load `tiny-sd` alongside your LLM and Vision LLM.*

---

## Scenario C: High-Concurrency Stress Test
If you want to simulate thousands of agents, you must distribute the load across multiple clients. Create multiple config directories (e.g., `client_1/`, `client_2/`) and split your `agents.json` equally among them.

1. Set `"min_clients_to_start": 3` in the `server_config.json`.
2. Start the server.
3. Start three separate clients pointing to their respective configs. The server will orchestrate the global state and wait for all three clients to finish their slice of agents before advancing the hour.

**`client_1_config.json`:**
```json
{
  "client_id": "node_1",
  "server_name": "orchestrator_server",
  "simulation": {
    "num_rounds": 24,
    "use_local_diffusion": false
  },
  "llm": {
    "use_remote_batch": true
  }
}
```
*Note: Using `"use_remote_batch": true` allows the clients to queue prompts and resolve them efficiently in bulk against an enterprise LLM endpoint or a dedicated vLLM instance.*
