# System Architecture

YPhotoSharing is designed to emulate the complex interactions of a photo-centric social network. To handle the scale of simulating numerous LLM-powered agents simultaneously, the platform relies on a distributed architecture.

## Core Components

### 1. The Orchestrator Server (`YServer`)
The server acts as the centralized source of truth for the platform. It is implemented as a Ray actor (`OrchestratorServer`) to handle concurrent requests from multiple clients safely.

**Responsibilities:**
- **Database Operations**: Wraps an SQLite database (`yphotosharing.db`) through SQLAlchemy (`db_middleware.py`) to store Users, Photos, Comments, Follows, and Metrics.
- **Round Synchronization**: Enforces a barrier sync at the end of each hour/slot. It waits for all registered clients to signal readiness via `ready_for_next_round()` before triggering global state updates (e.g., calculating trending hashtags or virality scores).
- **Recommendation Systems**: Computes and caches personalized feeds.
  - **Home Feed**: Uses a surrogate multi-objective model (P(like) + P(comment)) to rank content from followed users.
  - **Explore Feed**: Uses Collaborative Filtering via `scikit-learn`'s `TfidfVectorizer` and Cosine Similarity to surface relevant content to users based on their historical interactions.

### 2. The Simulation Client (`YClient`)
Clients host the simulated agents. The architecture supports running multiple `SimulationClient` processes (or Ray actors) across a cluster to distribute the heavy LLM workload.

**Responsibilities:**
- **Agent Loop**: Iterates through the loaded agents (`Agent` class) for each hour/slot of the 24-slot day.
- **LLM Integration**: Exposes a unified API (`llm_service.py`) to connect the agents to backend LLM providers. It currently supports:
  - `ollama` for simple local inference.
  - `vllm` for high-throughput, batched local inference.
  - Vision endpoints for multimodal interactions.

### 3. Modalities & Media Generation
The platform optionally supports dynamic asset creation to mimic visual stimuli.

- **Image Generation**: If enabled, the `ImageGenerationService` leverages Hugging Face `diffusers` to spin up a local pipeline (e.g., `segmind/tiny-sd` or `Stable Diffusion v1.5`). It generates actual images based on the LLM's captions and topic tags.
- **Vision Models**: When viewing posts to comment or react, agents can optionally pass the generated image URL to a Vision-capable LLM to "see" the image, yielding much higher fidelity behaviors.

## Advanced Platform Dynamics

YPhotoSharing captures macro-level phenomena often missed by simple static simulations:

- **Finite Attention Budget**: Instead of a flat limit on actions, agents have a decaying attention budget that drains based on the cognitive load of their actions (e.g., posting drains more than scrolling).
- **User Churn**: If an agent experiences low engagement or fails to gain followers, their satisfaction score decays until they permanently leave the platform.
- **Hashtag Velocity**: Trend momentum is artificially boosted during the early-adoption phase on the Explore page.
