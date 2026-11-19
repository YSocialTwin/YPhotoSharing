---
title: "Segnalazioni e moderazione"
subtitle: "Segnalazioni, un controllo di tossicità, rimozioni, avvisi e shadow-ban."
goal: "Sapere che cosa succede a una foto o a un commento segnalati o tossici e al loro autore."
time: "10 minuti"
---

## Segnalazioni

L'azione `report` registra una riga in `reported` con il contenuto, il suo tipo (foto o commento) e un motivo. Le segnalazioni e i contenuti pubblicati nel turno sono esaminati dal **servizio di moderazione** alla fine del turno; ogni decisione è una riga in `moderation_events` con l'azione, il motivo e una confidenza.

## Le regole

Il servizio usa uno **stub** di classificatore di tossicità: ogni parola vietata (`hate`, `kill`, `die`, `stupid`, `idiot`, `spam`) aggiunge 0,3, fino a 1. I punteggi della Perspective API si possono attivare come annotazione (`enable_toxicity`), ma le regole di rimozione usano lo stub.

| Caso | Regola |
|---|---|
| scansione proattiva, didascalia di una foto | punteggio sopra 0,5 → rimossa; autore avvisato; da 0,8 in su l'autore è in **shadow-ban** |
| scansione proattiva, commento | punteggio sopra 0,5 → rimosso; autore avvisato |
| elemento segnalato | rimosso quando il punteggio supera 0,3 o il motivo dice spam; autore avvisato |

Un **avviso** aggiunge 0,2 allo `stress_level` dell'autore, uno **shadow-ban** imposta `is_shadow_banned` e aggiunge 0,5 (lo stress è limitato a 1). I contenuti rimossi restano nel database con `is_removed` impostato.

{% include lab.html name="moderation" %}

## Perché uno stub

Qui la moderazione è un segnaposto di politica: fa esistere nei dati rimozioni, avvisi e shadow-ban, così se ne possono studiare gli effetti su esposizione, stress e abbandono, ed è il punto in cui inserire un classificatore migliore.

## Da dove continuare

- [Stress e ricompensa]({{ site.baseurl }}/it/stress/)
- [Schema del database]({{ site.baseurl }}/it/database-schema/)
