---
title: "Costruire sopra"
subtitle: "Dove estendere il simulatore, come testarlo e come è costruito questo sito."
goal: "Estendere YPhotoSharing senza rompere i controlli."
time: "15 minuti"
---

## Punti di estensione

- **Ranking.** Il ranking home è in `YServer/recsys/feed_ranking_service.py`, Esplora in `explore_recsys.py`, le tendenze in `trend_service.py`, la viralità in `services/virality_service.py`. Aggiungi un segnale solo se viene da un comportamento esistente delle reti di foto, è economico da calcolare a ogni turno e spiega un effetto osservato.
- **Azioni.** Ogni azione è un modulo in `YClient/actions/` con un gestore in `agent.py` e un costo nella tabella dell'attenzione.
- **Moderazione.** Sostituisci lo stub a parole chiave in `services/moderation_service.py` con un classificatore vero.
- **Modelli.** `YClient/LLM_interactions/` contiene i servizi di linguaggio, visione, batch e immagini.
- **Prompt.** Persone e compiti stanno in `prompts_ygram.json` e nei pacchetti di prompt interni (inglese e italiano).
- **Pagine di amministrazione e dei partecipanti.** La piattaforma porta con sé pagine, rotte, template e stili come plug-in di YSocial (`ysocial_platform/`), così il core non cambia.

## Test

```bash
python -m pytest -q
```

La suite copre il livello dei repository, le annotazioni, i recommender, stress e ricompensa, il logging, la parità dello schema, il gateway e i collegamenti della piattaforma; non sostituisce una lunga prova di carico multi-client su un vero cluster Ray con un vero modello.

## Questo sito

Sta in `docs/` accanto alle pagine MkDocs del repository (che Jekyll ignora) ed è costruito dal workflow *Documentation*. Le pagine Parametri e Schema del database sono generate:

```bash
python scripts/make_parameters_data.py
python scripts/make_schema_data.py
python scripts/make_schema_data.py --check
```

## Altro

- [Repository](https://github.com/YSocialTwin/YPhotoSharing) · [Allineamento con YSimulator](https://github.com/YSocialTwin/YPhotoSharing/blob/main/docs/ysimulator_alignment.md) · [Lacune rimaste](https://github.com/YSocialTwin/YPhotoSharing/blob/main/docs/remaining_gaps.md) · [Requisiti della piattaforma](https://github.com/YSocialTwin/YPhotoSharing/blob/main/docs/platform_requirements.md)
