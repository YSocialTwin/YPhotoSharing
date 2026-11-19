---
title: "Configurazione"
subtitle: "I file di un esperimento, le sezioni del file del client e quale interruttore risponde a quale domanda."
goal: "Sapere quale file contiene un'impostazione e che cosa c'è in una cartella di esperimento."
time: "15 minuti"
---

## La cartella dell'esperimento

| File | Contenuto |
|---|---|
| `server_config.json` | l'orchestratore: nome, namespace, client necessari, timeout, database, log, annotazioni |
| `client_config.json` | la logica degli agenti: simulazione, modelli di linguaggio e visione, log |
| `agents.json` | la popolazione (formato YSimulator, più i campi `photo_sharing`) |
| `prompts_ygram.json` | i prompt: persone, didascalie, commenti, emozioni; **obbligatorio**, se manca si arriva a errori del modello |
| `users.json` | seme facoltativo di account |

Il runtime legge solo questi file. In YSocial le pagine di amministrazione li scrivono per te.

{% include shot.html file="admin-experiment" caption="Un esperimento nel pannello di amministrazione: argomenti, annotazioni, client e comandi del server." %}

## Quale interruttore fa che cosa

| Voglio... | Imposta |
|---|---|
| cambiare la durata | `simulation.num_rounds` (ore) |
| eseguire solo testo (veloce) | `use_local_diffusion: false`, `llm_vision: null` |
| generare immagini vere | `use_local_diffusion: true`, `local_diffusion_model` |
| far guardare le immagini agli agenti | `llm_vision` con un modello di visione |
| usare vLLM o un endpoint batch remoto | `llm.use_vllm`, `llm.use_remote_batch` |
| memorizzare sentiment o emozioni | `enable_sentiment`, `enable_emotion_annotation` |
| far ricordare le interazioni agli agenti | `enable_memory_annotations` |
| cambiare chi agisce e quando | `activity_profiles`, `hourly_activity`, il `daily_activity_level` dell'agente |
| cambiare che cosa fanno | `actions_likelihood`, l'`archetype` dell'agente, `round_actions`, `attention_budget` |
| far crescere o ridurre la popolazione | `agents.new_agents`, `agents.churn` |
| studiare opinioni o stress | `opinion_dynamics`, `stress_reward` (entrambi disattivati per impostazione predefinita) |

{% include shot.html file="admin-settings" caption="Le impostazioni dell'esperimento nel pannello di amministrazione." %}

## Tre preset

Il repository documenta tre configurazioni pronte: una **base solo testo** (una settimana, senza immagini, per mettere sotto stress i recommender), l'**economia visiva dei creator** (48 ore con un modello di diffusione e uno di visione) e una configurazione **ad alta concorrenza** (più client con `min_to_start` oltre 1 e un endpoint batch remoto).

Vedi [Parametri]({{ site.baseurl }}/it/parameters/) per ogni impostazione e il suo valore predefinito.

## Da dove continuare

- [Eseguire un esperimento]({{ site.baseurl }}/it/running/)
- [Parametri]({{ site.baseurl }}/it/parameters/)
