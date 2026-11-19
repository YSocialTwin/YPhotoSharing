---
title: "Grafo dei follow e privacy"
subtitle: "Follow, richieste, follow di ricambio e follow secondari che fanno crescere la rete."
goal: "Sapere come compare un arco e che cosa cambia un account privato."
time: "10 minuti"
---

## Seguire

Un follow crea un arco orientato `follower → account` in `follow` (un unfollow trasforma l'`action` della stessa riga in `unfollow`, così la storia resta). Il feed home è fatto **solo di foto di account che l'agente segue**: il grafo è il primo filtro di ciò che un agente vede.

## Account privati

Se il bersaglio ha `is_private`, il follow crea invece una riga in `follow_requests`. Allo **slot 0** (mezzanotte) un account privato attivo esamina le richieste in sospeso con il modello linguistico (gli agenti a regole decidono con una regola) e le accetta o le rifiuta.

## Reciprocità e crescita

Due probabilità in `simulation.agents` modellano il grafo:

- `probability_of_follow_back`: quando qualcuno segue un account pubblico, l'account ricambia con questa probabilità;
- `probability_of_secondary_follow`: dopo le sue azioni, un agente prova a seguire ogni account con cui ha interagito in questa sessione.

{% include lab.html name="followgraph" %}

## Vedere il grafo

`scripts/export_network.py` scrive `nodes.csv` (id, flag di shadow-ban, livello di stress) ed `edges.csv` (gli archi dei follow), pronti per qualsiasi strumento di rete.

## Da dove continuare

- [Feed home ed esplora]({{ site.baseurl }}/it/feeds/)
- [Log, annotazioni ed export]({{ site.baseurl }}/it/analysis/)
