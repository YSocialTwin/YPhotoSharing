# Opinion Dynamics Module

Modular opinion management system for agent opinions in YSimulator.

## Quick Start

```python
from YSimulator.YServer.opinion_dynamics import OpinionHandler

# Initialize handler
opinion_handler = OpinionHandler(
    db_adapter=db,
    simulation_config=simulation_config,
    agent_profiles_cache=agent_profiles,
    current_round_id_getter=lambda: current_round_id,
    logger=logger
)

# Ensure agent has opinion on topic
opinion_handler.ensure_agent_opinion_exists(
    agent_id="agent_uuid",
    topic_id="topic_uuid",
    topic_name="Politics"
)

# Get latest opinion
opinion = opinion_handler.get_latest_opinion("agent_uuid", "topic_uuid")

# Add/update opinion
opinion_handler.add_opinion(
    agent_id="agent_uuid",
    topic_id="topic_uuid",
    opinion=0.75,
    id_interacted_with="other_agent",
    id_post="post_uuid"
)

# Get neighbor opinions for BC models
neighbor_opinions = opinion_handler.get_neighbors_opinions(
    agent_id="agent_uuid",
    topic_id="topic_uuid"
)
```

## Features

- **Profile-based initialization** - Uses agent profiles for default opinions
- **Configurable** - Enable/disable via simulation_config
- **Multi-backend** - Supports both SQL and Redis
- **Agent type awareness** - Different handling for regular vs page agents
- **Case-insensitive** - Topic name matching

## Documentation

See [OPINION_DYNAMICS_HANDLER.md](../../docs/architecture/OPINION_DYNAMICS_HANDLER.md) for detailed documentation.

## Testing

```bash
pytest YSimulator/tests/test_opinion_handler.py -v
```
