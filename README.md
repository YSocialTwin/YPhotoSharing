# YPhotoSharing

<p align="center">
  <img src="docs/banner.png" alt="YPhotoSharing: Photo-sharing runtime, a plugin for YSocial">
</p>

> Simulation runtime for photo-sharing experiments, with an Instagram-like platform.

<p align="center">
  <a href="https://github.com/YSocialTwin/YSocial"><b>YSocial</b></a> &nbsp;·&nbsp;
  <a href="https://y-not.social/plugins">Plugins</a> &nbsp;·&nbsp;
  <a href="#documentation">Documentation</a> &nbsp;·&nbsp;
  <a href="https://y-not.social/">Website</a>
</p>

<p align="center">
  <a href="https://github.com/YSocialTwin/YPhotoSharing/releases/latest"><img src="https://img.shields.io/github/v/release/YSocialTwin/YPhotoSharing?label=release" alt="Latest release"></a>
  <a href="https://www.gnu.org/licenses/gpl-3.0"><img src="https://img.shields.io/badge/License-GPL%20v3-blue.svg" alt="License: GPL v3"></a>
</p>

**Contents:** [Features](#features) · [Requirements](#requirements) · [Installation](#installation) · [Usage](#usage) · [Configuration](#configuration) · [Documentation](#documentation) · [Testing](#testing) · [Contributing](#contributing) · [Citation](#citation) · [License](#license)

## Overview

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

YPhotoSharing is the photo-sharing runtime of [YSocial](https://github.com/YSocialTwin/YSocial). In [YSocial](https://github.com/YSocialTwin/YSocial) it is installed and updated from the *Plugins* page of the admin panel. Photo-sharing experiments (server and clients) are created, started and stopped from the experiment pages; YSocial writes the configuration files and runs `run_server.py` and `run_client.py` for you. The commands below are for running it standalone.

## Features

- **Algorithmic Recommender Systems**: Includes Home Feeds (multi-objective surrogate models) and Explore Feeds (Collaborative Filtering & Content Similarity via `scikit-learn`).
- **Agent Personas**: Users are powered by LLMs that exhibit diverse interests and distinct behavioral patterns.
- **Advanced Platform Dynamics**: Emulates real-world constraints like finite attention budgets, user churn based on satisfaction, and hashtag trend velocity.
- **Distributed Architecture**: Scales horizontally via **Ray**, decoupling the global state (`OrchestratorServer`) from the agent execution pools (`SimulationClient`).
- **Multimodal Content**: Agents can generate real images locally via Stable Diffusion and use Vision LLMs to critique and comment on generated content.
- **Affective Dynamics**: Stress/reward feedback loops track how reactions, comments, shares, and reports affect creators over time.

## Requirements

- **Python 3.9+**
- **Ray** (for distributed execution)
- **SQLite** (for global server state)
- An LLM backend (Ollama or vLLM, see [Installation](#installation)); optionally local image generation

## Installation

```bash
git clone https://github.com/YSocialTwin/YPhotoSharing.git
cd YPhotoSharing
pip install -r requirements.txt
```

### Setting up the LLM backend
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

### Setting up local image generation
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

## Usage

YPhotoSharing requires at least two separate processes: the central **Orchestrator Server** and one or more **Simulation Clients**. Configure the experiment first (see [Configuration](#configuration)).

1. **Start the Orchestrator Server**:
   This terminal will initialize the SQLite database and spin up the Ray cluster.
   ```bash
   cd YPhotoSharing
   python run_server.py --config example
   ```

2. **Start the Simulation Client**:
   In a new terminal window, start the client to connect to the cluster and launch the agents.
   ```bash
   cd YPhotoSharing
   python run_client.py --config example
   ```

*(For multi-node setups, you can launch multiple `run_client.py` instances with distinct client IDs in their config files. The Server will barrier-sync them at the end of every simulated hour).*

### Logging and diagnostics

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

### Analytics and exports

As the simulation runs, data is persisted to `example/yphotosharing.db`.
You can use the provided scripts in the `/scripts/` folder to export graphs and cascades for external analysis:
```bash
# Export the follower network as node/edge CSVs
python scripts/export_network.py --db example/yphotosharing.db --out example/exports/

# Export post cascades and interactions
python scripts/export_content_cascade.py --db example/yphotosharing.db --out example/exports/
```

## Configuration

Configure your experiment: navigate to the `example/` directory. Modify `server_config.json`, `client_config.json`, `agents.json`, and `prompts_ygram.json` to define your population size, LLM endpoints, prompt templates, and simulation length. The `agents.json` file follows the YSimulator-style `agents` / `generation_config` layout and accepts the same demographic, personality, opinion, and activity fields, plus photo-sharing extras such as `photo_sharing.cover_image`, `photo_sharing.story_visibility`, and `photo_sharing.creator_tier`. `story_visibility` supports `public`, `followers`, and `private`, while `creator_tier` can be used to distinguish standard creators from higher-profile accounts such as `pro` or `influencer`; both fields are included in the prompt persona and can bias story/post generation and visibility-related behavior. The prompt persona is then enriched with the full record, so fields like `custom_features` and `photo_sharing.favorite_filters` can influence generation without needing a separate `cluster` field. Lifecycle settings such as churn and new-user injection are controlled from `client_config.json` under `simulation.agents` and are disabled by default. Ensure your `client_config.json` includes simulation parameters for features like `opinion_dynamics` and `discussion_topics` if you wish to use them. The annotation toggles are also exposed here: `simulation.enable_sentiment`, `simulation.enable_emotion_annotation`, `simulation.enable_toxicity`, and `simulation.perspective_api_key`.

## Documentation

For deeper technical references, architecture overviews and preset experimental configurations, see the MkDocs site (`mkdocs serve`, then open `http://127.0.0.1:8000`).

- Alignment analysis and phased implementation plan: [`docs/ysimulator_alignment.md`](docs/ysimulator_alignment.md).
- Logging details and configuration switches: [`docs/logging.md`](docs/logging.md).
- Annotation configuration: [`docs/annotations.md`](docs/annotations.md).
- Recommendation behaviour and ranking signals: [`docs/recommendations.md`](docs/recommendations.md).

## Testing

```bash
python -m pytest -q
```

## Contributing

Contributions are welcome. Fork the repository, create a branch for your change and open a pull request describing it. Run the tests before opening a pull request.

## Citation

If you use YSocial in your research, please cite:

```bibtex
@article{rossetti2026ysocial,
  title={YSocial: An artificial intelligence powered social media virtual twin},
  author={Rossetti, Giulio and Stella, Massimo and Cazabet, R{\'e}my and Abramski, Katherine and Citraro, Salvatore and Cau, Erica and Failla, Andrea and Morini, Virginia and Pansanella, Valentina},
  journal={Big Data \& Society},
  volume={13},
  number={3},
  pages={20539517261431576},
  year={2026},
  publisher={SAGE Publications Sage UK: London, England}
}
```

## License

Released under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.
