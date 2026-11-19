---
title: "Agenti e popolazione"
subtitle: "Persone, archetipi, attività, privacy e livelli di creator."
goal: "Descrivere gli agenti di una run e sapere quali campi ne cambiano il comportamento."
time: "10 minuti"
---

## Il file della popolazione

`agents.json` segue il formato di YSimulator: un array `agents` e un `generation_config` facoltativo. Un agente ha i consueti campi demografici e di personalità (`age`, `gender`, `nationality`, `education_level`, `profession`, `leaning`, i Big Five `oe co ex ag ne`, `language`), gli `interests`, le `opinions` iniziali, gli `stubborn_topics`, eventuali `custom_features` liberi e i campi della piattaforma qui sotto. Il client costruisce la **persona** del modello linguistico dall'intero record, quindi ogni `custom_features` che aggiungi può influenzare ciò che l'agente scrive.

| Campo | Che cosa fa |
|---|---|
| `user_type` | `llm` (guidato da prompt) o `rule_based` (didascalie e azioni deterministiche) |
| `archetype` | `broadcaster`, `explorer` o `validator`: moltiplica alcuni pesi delle azioni ([Che cosa fanno gli agenti]({{ site.baseurl }}/it/actions/)) |
| `activity_profile` | nome di un profilo orario (`high`, `medium`, `low`...): l'agente agisce esattamente in quelle ore |
| `daily_activity_level` | 1–5; senza profilo scala la probabilità oraria; 0 significa mai |
| `round_actions` | limite massimo di azioni tentate in un'ora attiva |
| `attention_budget` | attenzione disponibile in un'ora (predefinito 100) |
| `recsys_type` | un gruppo grossolano di persone, usato da Esplora come scorciatoia di filtraggio collaborativo |
| `is_private` | l'account richiede approvazione per essere seguito |
| `is_page` | una pagina: un'azione per ora attiva |
| `photo_sharing.story_visibility` | `public`, `followers` o `private` |
| `photo_sharing.creator_tier` | `standard`, `pro`, `influencer`...: rafforza l'autopresentazione nei prompt |
| `photo_sharing.favorite_filters`, `cover_image` | colore per didascalie e profilo |

{% include shot.html file="profile" caption="Un profilo nelle pagine della piattaforma: biografia, foto e numero di follower." %}

## Da dove vengono gli agenti

La popolazione si carica all'avvio del client e si scrive nel database. Con `simulation.agents.new_agents` attivo, altri agenti vengono clonati da record esistenti durante la run ([Abbandono e nuovi utenti]({{ site.baseurl }}/it/lifecycle/)). Anche pagine e persone sono account: una pagina ha un'azione per ora attiva, una persona (`user_type = human`) si crea tramite il gateway.

{% include shot.html file="admin-clients" caption="Creare un client nel pannello di amministrazione: popolazione, modello e parametri della simulazione." %}

## Da dove continuare

- [Che cosa fanno gli agenti]({{ site.baseurl }}/it/actions/)
- [Grafo dei follow e privacy]({{ site.baseurl }}/it/network/)
