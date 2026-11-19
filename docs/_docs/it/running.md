---
title: "Eseguire un esperimento"
subtitle: "Preparare il backend dei modelli, avviare server e client, scalare."
goal: "Eseguire un esperimento dalla riga di comando o dal pannello di amministrazione."
time: "15 minuti"
---

## Installare

```bash
git clone https://github.com/YSocialTwin/YPhotoSharing.git
cd YPhotoSharing
pip install -r requirements.txt
```

Gli agenti hanno bisogno di un modello linguistico. **Ollama** è il più semplice (`ollama pull llama3.2`, più un modello di visione come `llama3.2-vision` o `minicpm-v` per le run multimodali); **vLLM** dà throughput a lotti su una GPU CUDA (`llm.use_vllm: true`). Gli endpoint ospitati che richiedono una chiave funzionano con `llm_api_key` e `llm.api_format` (`auto`, `openai`, `ollama`). Per le immagini generate installa `diffusers` e `torch` come dice il README; CUDA e Apple Silicon sono supportati.

## Avviare

```bash
python run_server.py --config example      # orchestratore, database, Ray
python run_client.py --config example      # agenti (in un altro terminale)
```

In YSocial lo stesso avviene dalla pagina dell'esperimento: crea l'esperimento, aggiungi un client, avvia il server, poi il client.

## Più di un client

Dai a ogni client la sua cartella e il suo `client_id`, dividi `agents.json` tra loro e imposta `min_to_start` sul server al numero di client. Il server parte quando si sono registrati e, alla fine di ogni ora, aspetta che tutti siano pronti. Con una popolazione molto grande usa `llm.use_remote_batch` così i prompt vengono accodati e risolti in blocco.

## Log

Nella cartella dell'esperimento, righe JSON ruotate con gzip: `<client>_execution.log`, `<server>_server.log`, `<client>_actor.log`, `<server>_actor.log`, `_server.log` (richieste) e `<client>_llm_usage.log`. Flussi facoltativi per client: `_actions.log` e `_prompts.log`. Gli interruttori sono sotto `logging` ([Log, annotazioni ed export]({{ site.baseurl }}/it/analysis/)).

## Da dove continuare

- [Persone sulla piattaforma]({{ site.baseurl }}/it/participate/)
- [Log, annotazioni ed export]({{ site.baseurl }}/it/analysis/)
