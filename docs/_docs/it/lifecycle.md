---
title: "Abbandono e nuovi utenti"
subtitle: "Agenti che perdono interesse e se ne vanno, e nuovi utenti clonati dalla popolazione."
goal: "Capire i due modi in cui un agente se ne va e come compaiono i nuovi arrivati."
time: "10 minuti"
---

## Soddisfazione

A ogni turno attivo un agente confronta i suoi follower con il turno precedente: **+5 per ogni follower guadagnato, altrimenti −1**. La soddisfazione vive in [0, 100] e parte da 100; a **10 o meno** l'account è segnato come uscito (`is_churned`) e lo scheduler lo salta da quel momento. Un creator che non guadagna mai follower se ne va dopo circa 90 turni attivi; uno popolare non se ne va mai.

{% include lab.html name="satisfaction" %}

## Abbandono per inattività (disattivato per impostazione predefinita)

`simulation.agents.churn` aggiunge un passaggio alla fine di ogni giorno (slot 23): gli agenti inattivi da almeno `inactivity_threshold` giorni sono candidati; ne viene campionata una quota `churn_percentage` e ciascuno se ne va con `churn_probability`. Il turno si registra in `left_on`. Con `enabled: false` (il predefinito) non accade nulla.

## Nuovi utenti (disattivati per impostazione predefinita)

`simulation.agents.new_agents`: nello stesso momento una quota `percentage_new_agents` della popolazione attiva (arrotondata per difetto) ha una probabilità `probability_new_agents` di generare un nuovo arrivato **clonato da un record esistente scelto a caso**, con nuovo id e nome utente, `joined_on` impostato al turno e nessuna storia. La crescita della popolazione segue quindi la miscela delle persone esistenti.

## Da dove continuare

- [Stress e ricompensa]({{ site.baseurl }}/it/stress/)
- [Configurazione]({{ site.baseurl }}/it/configuration/)
