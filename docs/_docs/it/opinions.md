---
title: "Dinamica delle opinioni"
subtitle: "Fiducia limitata o una valutazione Likert, sugli argomenti delle foto che un agente commenta."
goal: "Scegliere un modello di opinione e leggere che cosa registra."
time: "10 minuti"
---

## Due modelli

Con `simulation.opinion_dynamics.enabled`, gli agenti hanno un'opinione in [0, 1] su ogni argomento di `discussion_topics`. Quando un agente risponde a una foto o la commenta, l'opinione dell'autore è il segnale e l'opinione si aggiorna con il modello in `model_name`:

- **`bounded_confidence`** (continuo): con `epsilon`, `mu`, `theta` e `cold_start` in `opinion_dynamics.parameters`. Se |y − x| ≤ epsilon il lettore si muove x ← x + mu (y − x); altrimenti ignora il messaggio oppure, quando theta non è 0, si allontana di theta.
- **`llm_evaluation`** (discreto): il modello colloca il post su una scala Likert (`likert_scale`, cinque punti per impostazione predefinita, da fortemente in disaccordo a fortemente d'accordo) e l'agente si muove di un passo; `opinion_groups` associa ogni etichetta a un intervallo di punteggio ed `evaluation_scope` dice se si considera solo l'interlocutore.

{% include lab.html name="opinions" %}

## Che cosa si registra

`user_opinions` conserva l'ultima opinione per utente, argomento e turno; `opinion_paths` conserva ogni transizione con il modello, le etichette di partenza e di arrivo e la direzione (verso, lontano o nessuna), il post e l'attore, così la polarizzazione si può far risalire alle interazioni che l'hanno causata.

## Da dove continuare

- [Stress e ricompensa]({{ site.baseurl }}/it/stress/)
- [Parametri]({{ site.baseurl }}/it/parameters/)
