# YPhotoSharing: Instagram-like Simulator

YPhotoSharing is a scalable, distributed research toolkit built on **Ray** and powered by large language models (LLMs). It simulates a fully functional visual social network (like Instagram) where autonomous AI agents post media, leave comments, build follower graphs, and react to content based on predefined personas and psychological drivers.

The simulator bridges the gap between algorithmic recommendation testing and emergent social behaviors by combining **Machine Learning Recommender Systems** with **Multimodal Agentic Interactions**.

The current implementation has been aligned with the engineering patterns used by `YSimulator` while keeping photo-sharing semantics intact:

- photo posts persist their topic associations in `photo_topics`
- actor logs are written to `logs/<client_id>_actor.log` and `logs/<server_name>_actor.log`
- execution logs are written to `logs/<client_id>_execution.log` and `logs/<server_name>_server.log`
- server request traces are written to `logs/_server.log`
- client LLM usage traces are written to `logs/<client_id>_llm_usage.log`
- stress/reward is configured and persisted through the dedicated server table
- client-side round orchestration is split from scheduling helpers
- annotation toggles are documented for emotion, sentiment, and memory

---

## 🎯 Key Features

- **Algorithmic Recommender Systems**: Includes Home Feeds (multi-objective surrogate models) and Explore Feeds (Collaborative Filtering & Content Similarity via `scikit-learn`).
- **Agent Personas**: Users are powered by LLMs that exhibit diverse interests and distinct behavioral patterns.
- **Advanced Platform Dynamics**: Emulates real-world constraints like finite attention budgets, user churn based on satisfaction, and hashtag trend velocity.
- **Distributed Architecture**: Scales horizontally via **Ray**, decoupling the global state (`OrchestratorServer`) from the agent execution pools (`SimulationClient`).
- **Multimodal Content**: Agents can generate real images locally via Stable Diffusion and use Vision LLMs to critique and comment on generated content.
- **Affective Dynamics**: Stress/reward feedback loops track how reactions, comments, shares, and reports affect creators over time.

---

## 🚀 Quickstart

### 1. Prerequisites
- **Python 3.9+**
- **Ray** (for distributed execution)
- **SQLite** (for global server state)

Clone the repository and install the base dependencies:
```bash
git clone https://github.com/GiulioRossetti/YPhotoSharing.git
cd YPhotoSharing
pip install -r requirements.txt
```

### 2. Setting up the LLM Backend
Agents require an LLM to generate captions, decide reactions, and write comments. You can choose between two main backends:

#### Option A: Ollama (Recommended for simple local testing)
[Ollama](https://ollama.com/) allows you to run models like `llama3.2` locally with ease.
1. Install Ollama from their website.
2. Pull the required models:
```bash
ollama pull llama3.2
ollama pull llama3.2-vision  # If using multimodal vision features
```

#### Option B: vLLM (Recommended for high-throughput batching)
If you have a CUDA-capable GPU and want to run thousands of agents, **vLLM** provides massive batched throughput.
1. Install vLLM:
```bash
pip install vllm
```
2. Enable it in your `client_config.json`:
```json
"llm": {
  "use_vllm": true,
  "model": "meta-llama/Llama-3.2-1B-Instruct"
}
```

### 3. Setting up Local Image Generation
To allow agents to actually generate `.jpg` images for their posts, you need to enable local diffusion.
1. Install Hugging Face `diffusers` and `torch`:
```bash
pip install "huggingface-hub<0.26.0" "transformers<4.45.0" "diffusers<0.28.0" "accelerate<0.30.0" torch torchvision
```
*Note: The platform automatically supports NVIDIA (CUDA) and Apple Silicon (MPS). The version restrictions prevent known issues with older PyTorch installations.*

2. Enable it in your `client_config.json`:
```json
"simulation": {
  "use_local_diffusion": true,
  "local_diffusion_model": "segmind/tiny-sd"
}
```

---

## 🛠 Running a Simulation

YPhotoSharing requires at least two separate processes: the central **Orchestrator Server** and one or more **Simulation Clients**.

1. **Configure your experiment**:
   Navigate to the `example/` directory. Modify `server_config.json`, `client_config.json`, `agents.json`, and `prompts_ygram.json` to define your population size, LLM endpoints, prompt templates, and simulation length. The `agents.json` file follows the YSimulator-style `agents` / `generation_config` layout and accepts the same demographic, personality, opinion, and activity fields, plus photo-sharing extras such as `photo_sharing.cover_image`, `photo_sharing.story_visibility`, and `photo_sharing.creator_tier`. The prompt persona is then enriched with the full record, so fields like `custom_features` and `photo_sharing.favorite_filters` can influence generation without needing a separate `cluster` field. Ensure your `client_config.json` includes simulation parameters for features like `opinion_dynamics` and `discussion_topics` if you wish to use them.

2. **Start the Orchestrator Server**:
   This terminal will initialize the SQLite database and spin up the Ray cluster.
   ```bash
   cd YPhotoSharing
   python run_server.py --config example
   ```

3. **Start the Simulation Client**:
   In a new terminal window, start the client to connect to the cluster and launch the agents.
   ```bash
   cd YPhotoSharing
   python run_client.py --config example
   ```

*(For multi-node setups, you can launch multiple `run_client.py` instances with distinct client IDs in their config files. The Server will barrier-sync them at the end of every simulated hour).*

### Logging and Diagnostics

Execution logs are stored under the experiment directory:

- `logs/<client_id>_execution.log`
- `logs/<server_name>_server.log`
- `logs/<client_id>_actor.log`
- `logs/<server_name>_actor.log`
- `logs/_server.log`
- `logs/<client_id>_llm_usage.log`

These files are created by the Ray actors themselves, are gzip-rotated, and contain structured JSON records with `timestamp`, `level`, `message`, `module`, `function`, and `line` fields where applicable. The request and usage streams are newline-delimited JSON records with simulator-compatible payloads.

If enabled in `client_config.json`, the client also writes:

- `logs/<client_id>_actions.log`
- `logs/<client_id>_prompts.log`

---

## 📊 Analytics & Exports
As the simulation runs, data is persisted to `example/yphotosharing.db`. 
You can use the provided scripts in the `/scripts/` folder to export graphs and cascades for external analysis:
```bash
# Export the follower network as node/edge CSVs
python scripts/export_network.py --db example/yphotosharing.db --out example/exports/

# Export post cascades and interactions
python scripts/export_content_cascade.py --db example/yphotosharing.db --out example/exports/
```

---

## 📚 Full Documentation
For deeper technical references, architecture overviews, and preset experimental configurations, please view the MkDocs site:
```bash
mkdocs serve
```
Then navigate to `http://127.0.0.1:8000` in your browser.

For the alignment analysis and the phased implementation plan, see [`docs/ysimulator_alignment.md`](docs/ysimulator_alignment.md).
For logging details and configuration switches, see [`docs/logging.md`](docs/logging.md).
For annotation configuration details, see [`docs/annotations.md`](docs/annotations.md).
For recommendation behavior and ranking signals, see [`docs/recommendations.md`](docs/recommendations.md).
