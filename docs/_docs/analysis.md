---
title: "Logs, annotations and export"
subtitle: "What is recorded, which annotations you can switch on and how to take the data out."
goal: "Choose the annotations and export the network and the cascades."
time: "10 minutes"
---

## Annotations

Under `simulation` in the client file (and the server file):

| Switch | Stored in | Notes |
|---|---|---|
| `enable_emotion_annotation` | `photo_emotions`, `emotions` | dominant visual emotion of each new photo (default on in the client) |
| `enable_sentiment` | `post_sentiment`, `sentiment_score` | numeric sentiment for photos and comments |
| `enable_toxicity` (+ `perspective_api_key`) | `post_toxicity` | toxicity scores from the Perspective API |
| `enable_memory_annotations` | `memory_interaction_events`, `memory_social_cards` | memory of interactions, put into comments and DMs |

The switches are independent. Sentiment and emotion also feed the rankings slightly ([Home and Explore feeds]({{ site.baseurl }}/feeds/)).

## Export

```bash
python scripts/export_network.py --db example/yphotosharing.db --out example/exports/
python scripts/export_content_cascade.py --db example/yphotosharing.db --out example/exports/
python scripts/export_feed_logs.py --help
```

`export_network.py` writes `nodes.csv` (id, shadow-ban flag, stress level) and `edges.csv` (follow edges). The other scripts export cascades and interactions and the feeds served. The database itself is plain SQLite: see [Database schema]({{ site.baseurl }}/database-schema/).

{% include shot.html file="admin-analytics" caption="The follow-network analysis of an experiment in the admin panel: nodes, edges, density and components over time." %}

## Logs

The logging switches are `enable_console_log`, `enable_execution_log`, `enable_server_log`, `enable_actor_log`, `enable_request_log`, `enable_action_log`, `enable_prompt_log` and `enable_llm_usage_log`. Records are JSON lines (`timestamp`, `level`, `message`, `module`, `function`, `line`), compatible with the other platforms.

## Where to next

- [Database schema]({{ site.baseurl }}/database-schema/)
