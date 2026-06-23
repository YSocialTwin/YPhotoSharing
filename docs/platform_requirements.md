# YPhotoSharing – Platform Requirements & Advanced Implementation Plan

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Platform Requirements](#3-platform-requirements)
   - 3.1 [Functional Requirements](#31-functional-requirements)
   - 3.2 [Non-Functional Requirements](#32-non-functional-requirements)
   - 3.3 [LLM Inference Requirements](#33-llm-inference-requirements)
4. [Database Schema](#4-database-schema)
5. [Ray Client-Server Design](#5-ray-client-server-design)
6. [LLM Integration](#6-llm-integration)
   - 6.1 [Standard Inference (Ollama / OpenAI-compatible)](#61-standard-inference-ollama--openai-compatible)
   - 6.2 [Batched Inference (vLLM)](#62-batched-inference-vllm)
   - 6.3 [Remote Batch Service](#63-remote-batch-service)
7. [Simulation Model](#7-simulation-model)
8. [Advanced Extension Plan](#8-advanced-extension-plan)
   - 8.1 [Phase 1 – Core Skeleton (Done)](#81-phase-1--core-skeleton-done)
   - 8.2 [Phase 2 – Recommendation Engine](#82-phase-2--recommendation-engine)
   - 8.3 [Phase 3 – Visual Content Modeling](#83-phase-3--visual-content-modeling)
   - 8.4 [Phase 4 – Influence & Virality Dynamics](#84-phase-4--influence--virality-dynamics)
   - 8.5 [Phase 5 – Moderation & Safety](#85-phase-5--moderation--safety)
   - 8.6 [Phase 6 – Analytics & Observability](#86-phase-6--analytics--observability)
   - 8.7 [Phase 7 – Multi-Modal & Generative Media](#87-phase-7--multi-modal--generative-media)
9. [Configuration Reference](#9-configuration-reference)
10. [Quick Start](#10-quick-start)

---

## 1. Overview

**YPhotoSharing** is a Ray-based distributed simulation platform that models an
Instagram-like social photo-sharing network.  It is designed for social-science
researchers, AI/ML practitioners and platform safety teams who want to:

- Simulate large populations of LLM-driven agents interacting on a visual social
  platform.
- Study emergent phenomena such as filter bubbles, virality, influencer dynamics
  and content moderation.
- Benchmark recommendation algorithms and content-ranking policies at scale.

YPhotoSharing follows the client/server separation established in
[YSimulator](https://github.com/YSocialTwin/YSimulator):

| Component | Responsibility |
|-----------|---------------|
| **Server** | Exclusive database access, social graph, feed generation, round coordination |
| **Client** | Exclusive LLM access, agent persona simulation, action generation |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Ray Cluster                          │
│                                                         │
│  ┌──────────────────┐         ┌──────────────────────┐  │
│  │  SimulationClient│         │  OrchestratorServer  │  │
│  │  (Ray actor)     │──RPC──▶ │  (Ray actor)         │  │
│  │                  │         │                      │  │
│  │  • LLM service   │         │  • DatabaseMiddleware│  │
│  │  • Agent pool    │◀──RPC── │  • Feed generation   │  │
│  │  • Action gen.   │         │  • Recommendation    │  │
│  └──────────────────┘         └──────────────────────┘  │
│           │                            │                 │
│    ┌──────┴──────┐              ┌──────┴──────┐          │
│    │ LLM Service │              │  Database   │          │
│    │  (Ray actor)│              │ (SQLite /   │          │
│    │             │              │  PostgreSQL /│         │
│    │ Ollama/vLLM │              │  MySQL)      │         │
│    └─────────────┘              └─────────────┘          │
└─────────────────────────────────────────────────────────┘
```

**Key design principles:**

1. **Strict separation of concerns** – No database import ever touches the
   client; no LLM import ever touches the server.
2. **Ray-native** – All inter-component calls are Ray remote calls, enabling
   multi-machine deployments with zero code changes.
3. **Pluggable LLM backend** – Switch between Ollama, vLLM or a remote
   OpenAI-compatible endpoint via a single config flag.

---

## 3. Platform Requirements

### 3.1 Functional Requirements

#### User Management
- FR-1  Users have a profile with username, bio, profile picture, Big Five
  personality traits, demographic attributes and activity level.
- FR-2  Users can be marked as verified, private or page accounts.
- FR-3  Users can follow/unfollow other users (directed social graph).

#### Photo Content
- FR-4  Users publish photos with a URL, LLM-generated caption, optional
  filter, hashtags, location tag and alt text.
- FR-5  Photos support carousel format (multiple images in one post).
- FR-6  Photos can be soft-deleted (tombstone, no hard delete of reactions).

#### Reactions & Comments
- FR-7  Users react to photos with one of: LIKE, LOVE, LAUGH, WOW, SAD, ANGRY.
- FR-8  Users leave threaded comments on photos; replies reference a parent
  comment.
- FR-9  @mentions inside captions and comments are persisted and queryable.

#### Stories
- FR-10 Users post ephemeral stories (image or video) that expire after 24 h
  of simulation time.
- FR-11 Stories support interactive stickers: polls, questions, sliders.
- FR-12 Story view counts are tracked per viewer.

#### Feeds & Discovery
- FR-13 A chronological home feed is served to each user based on following.
- FR-14 An algorithmic explore/recommendation feed is served per round.
- FR-15 Trending hashtags are computed and persisted per round.

#### Direct Messages
- FR-16 Users can send private text messages, optionally attaching a photo.
- FR-17 Read/unread status is tracked per message.

### 3.2 Non-Functional Requirements

- NFR-1  **Scalability** – The system must support ≥ 10 000 simulated users
  across multiple client actors without architectural changes.
- NFR-2  **Fault tolerance** – A client crash must not corrupt the server state;
  all DB writes are transactional.
- NFR-3  **Reproducibility** – Simulation runs are identified by a run-ID; all
  events are tagged with round, day and hour for replay.
- NFR-4  **Multi-backend DB** – SQLite (development), PostgreSQL and MySQL are
  supported.
- NFR-5  **Observability** – Structured JSON logs are written for all server and
  client events with millisecond timestamps.

### 3.3 LLM Inference Requirements

- LLM-1  **Standard inference** – Agents call an Ollama or OpenAI-compatible
  endpoint one request at a time (suitable for laptops / small deployments).
- LLM-2  **Batched inference** – A vLLM-backed service processes an entire
  round's prompts in a single GPU kernel dispatch (10–100× throughput gain).
- LLM-3  **Remote batch inference** – A lightweight service proxies batched
  requests to a remote Ollama or OpenAI-compatible server without a local GPU.
- LLM-4  **Vision support** – A second (optionally multimodal) model generates
  alt-text descriptions and visual sentiment for photo content.
- LLM-5  **Transparent switching** – All LLM service actors expose an identical
  Python method surface; switching backends requires only a config change.

---

## 4. Database Schema

The schema extends the YSimulator relational model with Instagram-specific
tables.  All primary keys are UUID strings for distributed compatibility.

### Core tables (from YSimulator)

| Table | Purpose |
|-------|---------|
| `user_mgmt` | User profiles, Big Five traits, activity settings |
| `rounds` | Simulation time (day, hour) |
| `interests` | Topic/interest taxonomy |
| `user_interest` | User↔interest associations |
| `follow` | Directed follow graph |
| `recommendations` | Per-user per-round feed recommendations |
| `memory_interaction_events` | Run-scoped agent memory events |
| `memory_social_cards` | Agent relationship summaries |

### Instagram-specific tables

| Table | Purpose |
|-------|---------|
| `photos` | Photo posts (URL, caption, filter, location, carousel) |
| `stories` | Ephemeral story media |
| `story_views` | Who viewed which story |
| `reactions` | Emoji reactions on photos |
| `comments` | Threaded comments on photos |
| `mentions` | @mentions in captions/comments |
| `hashtags` | Hashtag registry |
| `photo_hashtags` | Photo↔hashtag many-to-many |
| `photo_topics` | LLM-inferred topic tags on photos |
| `photo_emotions` | LLM-inferred emotion distribution |
| `direct_messages` | Private messages |
| `trending_hashtags` | Trending snapshots per round |

### Entity-Relationship overview

```
user_mgmt ──< follow >── user_mgmt
    │
    ├──< photos >──< reactions
    │        └──< comments
    │        └──< photo_hashtags >── hashtags
    │        └──< photo_topics   >── interests
    │        └──< photo_emotions >── emotions
    │
    └──< stories >──< story_views
```

---

## 5. Ray Client-Server Design

### Server actor: `OrchestratorServer`

```python
@ray.remote
class OrchestratorServer:
    # Instantiated once; registered by name in a Ray namespace
    def register_client(client_id, client_info) -> dict
    def heartbeat(client_id) -> dict
    def ready_for_next_round(client_id) -> bool
    # --- User ---
    def create_user(user_data) -> str
    def get_user(user_id) -> dict
    def list_users(limit, offset) -> list[dict]
    # --- Social graph ---
    def follow_user(follower_id, user_id, round_id) -> str
    def unfollow_user(follower_id, user_id, round_id) -> bool
    def get_followers(user_id) -> list[str]
    def get_following(user_id) -> list[str]
    # --- Photos ---
    def post_photo(photo_data) -> str
    def get_photo(photo_id) -> dict
    def delete_photo(photo_id) -> bool
    # --- Reactions & Comments ---
    def react_to_photo(user_id, photo_id, reaction_type, round_id) -> str
    def post_comment(user_id, photo_id, body, round_id, ...) -> str
    def get_comments(photo_id, limit) -> list[dict]
    # --- Stories ---
    def post_story(story_data) -> str
    def view_story(story_id, viewer_id) -> bool
    # --- Feeds ---
    def get_home_feed(user_id, limit) -> list[dict]
    def set_recommendation(user_id, photo_ids, round_id) -> str
    def get_recommendation(user_id, round_id) -> list[str]
    # --- Hashtags & interests ---
    def get_or_create_hashtag(tag) -> str
    def tag_photo(photo_id, hashtag_id) -> None
    def get_or_create_interest(name) -> str
    def set_user_interests(user_id, interest_ids, round_id) -> None
    # --- Memory ---
    def add_memory_event(event_data) -> int
    def get_memory_events(run_id, agent_user_id, limit) -> list[dict]
```

### Client actor: `SimulationClient`

```python
@ray.remote
class SimulationClient:
    def load_agents(user_configs) -> int
    def run_round(day, hour) -> dict      # drives all agents, signals server
    def get_status() -> dict
```

### Round coordination flow

```
Server                       Client
  │                             │
  │◄── register_client ─────────│
  │──► {run_id, config} ────────►│
  │                             │
  │    [round loop]             │
  │◄── get_or_create_round ─────│
  │◄── [agent remote calls] ────│
  │     (feed, photo, react…)   │
  │──► responses ──────────────►│
  │◄── ready_for_next_round ────│
  │    (advance when all ready) │
```

---

## 6. LLM Integration

### 6.1 Standard Inference (Ollama / OpenAI-compatible)

`LLMService` (Ray CPU actor) wraps a LangChain `ChatOllama` model and exposes
named generation methods.  Each method call is a single synchronous request.

**Configuration (`client_config.json`):**

```json
"llm": {
  "backend": "ollama",
  "address": "localhost",
  "port": 11434,
  "model": "llama3.2",
  "temperature": 0.7,
  "use_vllm": false,
  "use_remote_batch": false
}
```

### 6.2 Batched Inference (vLLM)

`VLLMService` (Ray GPU actor, `num_gpus=1`) loads a model with vLLM and
processes entire round batches in one `llm.generate()` call.  Typical speedup
over sequential Ollama: 10–50× for rounds with ≥ 50 agents.

**Configuration:**

```json
"llm": {
  "model": "meta-llama/Llama-3.2-1B-Instruct",
  "temperature": 0.7,
  "max_tokens": 256,
  "tensor_parallel_size": 1,
  "gpu_memory_utilization": 0.90,
  "use_vllm": true
}
```

**Requirements:** CUDA-capable GPU, `pip install vllm`.

### 6.3 Remote Batch Service

`RemoteBatchLLMService` auto-detects whether the target endpoint supports
batched completions (OpenAI `/v1/completions` with array `prompt`, or Ollama
`.batch()`).  No local GPU needed; suitable for HPC setups with a shared
inference server.

```json
"llm": {
  "backend": "vllm_server",
  "address": "gpu-node-01",
  "port": 8000,
  "model": "mistralai/Mistral-7B-Instruct-v0.2",
  "api_format": "openai",
  "llm_api_key": "NULL",
  "use_remote_batch": true
}
```

### LLM method surface (all backends)

| Method | Description |
|--------|-------------|
| `generate_caption(topic, day, slot, cluster_id)` | Generate photo caption + hashtags |
| `batch_generate_captions(requests)` | Batch version |
| `decide_reaction(caption)` | Choose LIKE / LOVE / LAUGH / WOW / SAD / ANGRY / IGNORE |
| `batch_decide_reactions(requests)` | Batch version |
| `generate_comment(caption, author)` | Write a comment |
| `batch_generate_comments(requests)` | Batch version |
| `decide_follow(username, bio, topics)` | Return FOLLOW or SKIP |
| `describe_photo(url)` | Vision model alt-text (optional) |
| `get_capabilities()` | Dict of feature flags |

---

## 7. Simulation Model

### Agent lifecycle

1. **Initialisation** – Agent is created from a user config (personality traits,
   cluster_id, daily_activity_level, round_actions).
2. **Per-round** – Agent selects `round_actions` actions according to
   `action_weights` (post_photo, react, comment, follow).
3. **LLM call** – The chosen action calls the LLM service for content generation
   or decision making.
4. **Server call** – The result is persisted via the OrchestratorServer.
5. **Memory** – Notable events are written to `memory_interaction_events` for
   retrieval in future rounds.

### Default action weights

| Action | Default probability |
|--------|-------------------|
| post_photo | 0.20 |
| react | 0.40 |
| comment | 0.25 |
| follow | 0.15 |

### Simulation time

Each round corresponds to one hour of in-simulation time.  A full simulated day
comprises 24 rounds.  The server tracks day/hour in the `rounds` table and
coordinates client advancement via `ready_for_next_round()`.

---

## 8. Advanced Extension Plan

### 8.1 Phase 1 – Core Skeleton (Done)

- [x] Ray client/server architecture with strict DB/LLM separation
- [x] Instagram-like database schema (photos, stories, reactions, comments,
       hashtags, DMs, memory)
- [x] Standard LLM service (Ollama / LangChain)
- [x] vLLM batched service
- [x] Remote batch service (OpenAI-compatible + Ollama)
- [x] Agent class with per-round action selection
- [x] `run_server.py` and `run_client.py` entry points
- [x] Example config files and user population

---

### 8.2 Phase 2 – Recommendation Engine

**Goal:** Replace the chronological home feed with an algorithm-driven explore
feed that can be swapped at runtime.

**Planned components:**

- `YServer/recsys/` – Recommendation strategy plug-ins:
  - `PopularityRecsys` – score = likes + comments × time_decay
  - `CollaborativeFilteringRecsys` – user-based CF on the follow graph
  - `ContentBasedRecsys` – cosine similarity on LLM topic vectors
  - `HybridRecsys` – weighted ensemble
- `YServer/services/recommendation_service.py` – Calls recsys strategy and
  writes results to `recommendations` table.
- New server method `compute_recommendations(round_id)` – Called by server at
  end of each round.
- `TrendingHashtag` computation task – Writes `trending_hashtags` rows.

**Evaluation hooks:**
- Exposure fairness metrics (Gini coefficient over photo impressions)
- Filter bubble score (topic diversity in a user's feed over time)
- CTR (reaction rate on recommended vs. organic content)

---

### 8.3 Phase 3 – Visual Content Modeling

**Goal:** Use the vision-capable LLM to assign rich metadata to photos,
enabling more realistic agent behaviour.

**Planned components:**

- `YClient/LLM_interactions/vision_service.py` – Dedicated vision actor that
  batches image description requests.
- `YServer/services/photo_enrichment_service.py` – Server-side job that reads
  photos without alt_text and queues description requests to the client's vision
  service via a Ray object store.
- Visual sentiment model – Infer dominant emotion distribution and write to
  `photo_emotions`.
- Aesthetic scoring – Predict a 0–1 aesthetic score per photo (used by
  recommendation engine).
- Visual similarity – Store compact image embeddings (CLIP) for content-based
  recommendation.

---

### 8.4 Phase 4 – Influence & Virality Dynamics

**Goal:** Model cascades, viral content and influencer dynamics.

**Planned components:**

- `YServer/services/virality_service.py` – Compute viral score per photo each
  round (likes velocity, share rate, comment velocity).
- Share action – `YClient/actions/share.py` – Agent reposts a photo to their
  own followers; `photos` table tracks `parent_photo_id` for shares.
- Follower recommendation – `YServer/recsys/follow_recsys.py` – Suggest users
  to follow based on mutual followers and topic overlap.
- Influence graph analytics:
  - PageRank on the follow graph → influence score
  - Betweenness centrality → information broker score
  - Both stored as columns in `user_mgmt`
- Opinion dynamics – Port YSimulator's opinion module to track how visual
  content shifts agent opinions on topics over simulation rounds.

---

### 8.5 Phase 5 – Moderation & Safety

**Goal:** Model platform safety systems and their effect on agent behaviour.

**Planned components:**

- `YServer/services/moderation_service.py` – Policy-enforceable content
  moderation layer:
  - Rule-based filters (keyword, hashtag blocklists)
  - LLM-based toxicity classification (calls a moderation-tuned model)
  - Action: flag, shadow-ban, remove, warn
- `moderation_events` table – Records every moderation decision with reason,
  confidence score and round.
- `Reported` table (from YSimulator) – User-to-user content reports trigger
  moderation review.
- Agent stress/reward model – Moderation events affect agent stress levels,
  altering their future action distribution (ported from YSimulator's
  `stress_reward` module).
- Transparent moderation experiments – Configure moderation intensity and
  policy type (authoritarian, liberal, algorithmic) via `simulation_config`.

---

### 8.6 Phase 6 – Analytics & Observability

**Goal:** Rich simulation telemetry and post-hoc analysis.

**Planned components:**

- Structured JSON logging (rotating, gzip-compressed) for all server and client
  events (mirrors YSimulator's logging pipeline).
- `YServer/services/analytics_service.py`:
  - Per-round aggregate statistics (active users, posts, reactions, follows)
  - Written to an `analytics_snapshots` table for time-series queries
- Export utilities:
  - `scripts/export_network.py` – Export follow graph as GraphML / CSV
  - `scripts/export_feed_logs.py` – Export home feed contents per user per round
  - `scripts/export_content_cascade.py` – Reconstruct share cascades
- Redis integration (optional) – Cache hot feeds and trending data for
  sub-millisecond server response.
- Prometheus metrics endpoint on the server actor for real-time dashboards.

---

### 8.7 Phase 7 – Multi-Modal & Generative Media

**Goal:** Enable fully generative synthetic photo content.

**Planned components:**

- `YClient/LLM_interactions/image_generation_service.py` – Stable Diffusion /
  SDXL actor that generates synthetic photo URLs from captions.
- `YServer/services/media_service.py` – Stores generated images (local disk or
  S3-compatible object store) and returns stable URLs.
- Multimodal agent memory – Agents store visual memories (CLIP embeddings) and
  can recall visually similar past interactions.
- Video stories – Short 3–15 s synthetic video clips via text-to-video models
  (CogVideoX, AnimateDiff).

---

## 9. Configuration Reference

### `server_config.json`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `server_name` | string | `"orchestrator_server"` | Ray actor name |
| `namespace` | string | `"yphotosharing"` | Ray namespace |
| `min_to_start` | int | `1` | Minimum clients before round starts |
| `timeout_seconds` | int | `60` | Stale-client eviction timeout |
| `database.type` | string | `"sqlite"` | `sqlite` / `postgresql` / `mysql` |
| `database.sqlite.filename` | string | `"yphotosharing.db"` | SQLite file name |
| `simulation.num_rounds` | int | `48` | Total simulation rounds |

### `client_config.json`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `client_id` | string | auto-UUID | Unique client identifier |
| `server_name` | string | `"Orchestrator"` | Server Ray actor name |
| `namespace` | string | `"yphotosharing"` | Ray namespace |
| `users_file` | string | `"users.json"` | Path to user population JSON |
| `llm.backend` | string | `"ollama"` | `ollama` / `openai` |
| `llm.address` | string | `"localhost"` | LLM server address |
| `llm.port` | int | `11434` | LLM server port |
| `llm.model` | string | `"llama3.2"` | Model identifier |
| `llm.temperature` | float | `0.7` | Sampling temperature |
| `llm.use_vllm` | bool | `false` | Use embedded vLLM |
| `llm.use_remote_batch` | bool | `false` | Use remote batch service |
| `simulation.num_rounds` | int | `48` | Rounds to simulate |

---

## 10. Quick Start

### Prerequisites

```bash
# Python ≥ 3.10
pip install -r requirements.txt

# Start an Ollama instance (or any OpenAI-compatible server)
ollama serve
ollama pull llama3.2
```

### Run a local simulation

```bash
# Terminal 1 – start the server
cp -r example my_experiment
python run_server.py --config my_experiment

# Terminal 2 – start a client
python run_client.py --config my_experiment
```

### Run with vLLM (requires CUDA GPU)

Edit `my_experiment/client_config.json`:

```json
"llm": {
  "model": "meta-llama/Llama-3.2-1B-Instruct",
  "use_vllm": true,
  "tensor_parallel_size": 1,
  "gpu_memory_utilization": 0.90
}
```

Then start the client as normal.

### Scale to multiple clients

Start additional client processes pointing to the same config directory.
The server coordinates round advancement automatically once all registered
clients signal readiness.

---

*YPhotoSharing is part of the YSocialTwin research toolkit.*
