# Getting Started

This guide walks you through setting up the YPhotoSharing simulation environment, initializing the Orchestrator Server, and launching your first client node.

## Prerequisites

- **Python 3.9+**
- **Ray** for distributed execution.
- **SQLite** for the server database.
- *(Optional)* **vLLM** and a CUDA-capable GPU for running local LLMs efficiently.
- *(Optional)* **Ollama** installed locally if you want to use it as the default LLM backend.

## Installation

1. Clone the repository and install the requirements:
```bash
git clone https://github.com/GiulioRossetti/YPhotoSharing.git
cd YPhotoSharing
pip install -r requirements.txt
```

2. (Optional) For local multimodal/vision processing, ensure you have Hugging Face `diffusers` installed. Use the following versions to avoid conflicts with older PyTorch installations:
```bash
pip install "huggingface-hub<0.26.0" "transformers<4.45.0" "diffusers<0.28.0" "accelerate<0.30.0" torch torchvision
```

## Running the Baseline Simulation

YPhotoSharing requires at least two separate processes: the central **Orchestrator Server** and one or more **Simulation Clients**.

### 1. Configure the Experiment
Navigate to the `example/` directory. You will find:
- `server_config.json`: Server port and logic flags.
- `client_config.json`: Agent population settings, rounds, and LLM backend choice.
- `users.json`: A static list defining the personas of the simulated agents.

### 2. Start the Orchestrator Server
Open a terminal and start the server. This automatically starts a local Ray cluster.
```bash
# Terminal 1
cd YPhotoSharing
python run_server.py --config example
```
*You should see output indicating that the SQLite database has initialized and the server is listening for clients.*

### 3. Start the Simulation Client
Open a second terminal and start the client. The client will connect to the existing Ray cluster, load the agents, and begin executing actions (posting, commenting, liking) round by round.
```bash
# Terminal 2
cd YPhotoSharing
python run_client.py --config example
```

### 4. Viewing Results
As the simulation progresses, you will see output logging the agent actions. At any time, you can query the `example/yphotosharing.db` SQLite database to view the generated posts, comments, follower graphs, and analytical metrics.

If you are running the aligned Ray actors, also inspect:

- `example/logs/execution_client.log`
- `example/logs/execution_server.log`

Those files capture the runtime events emitted from inside the actors rather than just launcher output.
