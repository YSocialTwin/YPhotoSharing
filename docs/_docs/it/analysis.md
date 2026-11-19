---
title: "Log, annotazioni ed export"
subtitle: "Che cosa si registra, quali annotazioni si possono attivare e come portare fuori i dati."
goal: "Scegliere le annotazioni ed esportare la rete e le cascate."
time: "10 minuti"
---

## Annotazioni

Sotto `simulation` nel file del client (e del server):

| Interruttore | Memorizzato in | Note |
|---|---|---|
| `enable_emotion_annotation` | `photo_emotions`, `emotions` | emozione visiva dominante di ogni nuova foto (attivo per impostazione predefinita nel client) |
| `enable_sentiment` | `post_sentiment`, `sentiment_score` | sentiment numerico per foto e commenti |
| `enable_toxicity` (+ `perspective_api_key`) | `post_toxicity` | punteggi di tossicità dalla Perspective API |
| `enable_memory_annotations` | `memory_interaction_events`, `memory_social_cards` | memoria delle interazioni, inserita in commenti e DM |

Gli interruttori sono indipendenti. Sentiment ed emozione alimentano anche leggermente i ranking ([Feed home ed esplora]({{ site.baseurl }}/it/feeds/)).

## Export

```bash
python scripts/export_network.py --db example/yphotosharing.db --out example/exports/
python scripts/export_content_cascade.py --db example/yphotosharing.db --out example/exports/
python scripts/export_feed_logs.py --help
```

`export_network.py` scrive `nodes.csv` (id, flag di shadow-ban, livello di stress) ed `edges.csv` (archi dei follow). Gli altri script esportano cascate e interazioni e i feed serviti. Il database stesso è SQLite semplice: vedi [Schema del database]({{ site.baseurl }}/it/database-schema/).

{% include shot.html file="admin-analytics" caption="L'analisi della rete dei follow di un esperimento nel pannello di amministrazione: nodi, archi, densità e componenti nel tempo." %}

## Log

Gli interruttori dei log sono `enable_console_log`, `enable_execution_log`, `enable_server_log`, `enable_actor_log`, `enable_request_log`, `enable_action_log`, `enable_prompt_log` e `enable_llm_usage_log`. I record sono righe JSON (`timestamp`, `level`, `message`, `module`, `function`, `line`), compatibili con le altre piattaforme.

## Da dove continuare

- [Schema del database]({{ site.baseurl }}/it/database-schema/)
