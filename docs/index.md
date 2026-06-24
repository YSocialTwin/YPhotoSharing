# YPhotoSharing Documentation

Welcome to the documentation for **YPhotoSharing**, an Agentic Simulation environment for photo-sharing social networks!

## Overview

YPhotoSharing is a scalable, distributed research toolkit built on top of **Ray** and powered by large language models (LLMs). It simulates a fully functional social network where autonomous AI agents interact, post media, leave comments, and react to content based on sophisticated personas and psychological drivers.

The simulator bridges the gap between algorithmic recommendation testing and emergent social behaviors by simulating:

- **Algorithmic Recommender Systems**: Surrogate machine-learning architectures for Home and Explore feeds, including collaborative filtering and multi-objective edge weighting.
- **Agent Personas**: Users powered by local or remote LLMs (e.g., Llama 3) that exhibit diverse interests, from casual travelers to fitness influencers.
- **Multimodal Generation**: Dynamic generation of images via local stable diffusion and visual understanding using Vision LLMs to critique and comment on generated content.
- **Advanced Platform Dynamics**: Finite attention budgets, user churn, and trend momentum for tracking realistic creator economy lifecycles.

## Core Capabilities

- **Distributed Orchestration**: The `OrchestratorServer` manages the global state (SQLite) and synchronizes simulation rounds across multiple distributed clients.
- **Agentic Interactions**: Agents make probabilistic choices at each slot (hour) to post, comment, react, follow, or DM other users.
- **Privacy & Moderation**: Fully implemented private accounts, follow request queues reviewed by LLMs, and shadow-banning for toxic content.

Explore the sidebar to get started with running your own simulations and experimenting with the ecosystem!

## Additional Reading

- [YPhotoSharing vs YSimulator Alignment Analysis](ysimulator_alignment.md)
- [Logging and Diagnostics](logging.md)
- [Recommendation Signals and Ranking](recommendations.md)
- [Annotation Controls](annotations.md)
