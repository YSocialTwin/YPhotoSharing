---
title: "Stress e ricompensa"
subtitle: "Come reazioni, commenti, condivisioni e segnalazioni muovono l'umore di un creator."
goal: "Seguire un evento dalla tabella dei delta allo stress e alla ricompensa memorizzati."
time: "15 minuti"
---

## Il ciclo

Con `stress_reward.enabled`, le azioni che gli altri rivolgono a un creator sono **eventi**. Quando un agente reagisce, commenta, condivide o segnala, il client calcola i delta per il **destinatario** e li scrive nella tabella `stress_reward`. Due variabili, **stress** e **ricompensa**, vivono in [0, 1]. I delta vengono da una tabella di eventi, sono scalati dal contesto e si smorzano a vicenda.

| Evento | Δ stress | Δ ricompensa |
|---|---|---|
| reazione: like | −0,005 | +0,03 |
| reazione: dislike | +0,03 | −0,02 |
| commento: positivo | −0,02 | +0,07 |
| commento: neutro | 0 | +0,01 |
| commento: critico | +0,03 | −0,01 |
| commento: ostile | +0,10 | −0,05 |
| commento: solidale | −0,05 | +0,08 |
| condivisione: positiva | −0,01 | +0,08 |
| condivisione: ostile | +0,12 | −0,06 |
| segnalazione: di massa | +0,06 | −0,03 |

Le reazioni si moltiplicano per ln(1 + volume); i commenti ostili per direttezza ed esposizione pubblica; condivisioni e segnalazioni per esposizione pubblica (e le segnalazioni per importanza). L'**accoppiamento**: un aumento di stress si moltiplica per 1 − alpha × ricompensa (alpha 0,30) e un aumento di ricompensa per 1 − beta × stress (beta 0,20). Il tono di un commento viene dal suo sentiment e da alcune parole chiave.

{% include lab.html name="stress" %}

## Stato e abbandono

Lo stato corrente si **rigioca** dalle righe di `stress_reward` degli ultimi `backward_rounds` (24) turni. Il modulo offre anche una probabilità di abbandono, sigmoide((stress_weight × stress − reward_weight × ricompensa + bias) ÷ temperatura) entro [min_probability, max_probability] (predefiniti 2, 1, −1,8, 0,3, 0 e 0,95), ma l'abbandono che in una run toglie davvero gli agenti è il meccanismo di soddisfazione e inattività di [Abbandono e nuovi utenti]({{ site.baseurl }}/it/lifecycle/). Anche la moderazione aggiunge stress all'utente (`stress_level`) direttamente.

I delta sono valori predefiniti, non calibrati empiricamente. Regolali sotto `stress_reward.system.events`.

## Da dove continuare

- [Abbandono e nuovi utenti]({{ site.baseurl }}/it/lifecycle/)
- [Parametri]({{ site.baseurl }}/it/parameters/)
