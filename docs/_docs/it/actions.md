---
title: "Che cosa fanno gli agenti"
subtitle: "Le dodici azioni, i pesi che le scelgono e l'attenzione che le limita."
goal: "Seguire una sessione di un agente dall'estrazione al budget."
time: "15 minuti"
---

## Le azioni

| Azione | Che cosa fa | Costo |
|---|---|---|
| `post_photo` | pubblica una foto con didascalia | 40 |
| `comment` | commenta una foto del feed home | 20 |
| `reply_comment` | risponde a un commento | 20 |
| `send_dm` | messaggio diretto a un account che segue | 25 |
| `share` | condivide una foto con una didascalia | 15 |
| `follow` | segue un account (o invia una richiesta) | 10 |
| `report` | segnala un contenuto | 10 |
| `react` | like o altra reazione a una foto del feed home | 5 |
| `save` | salva tra i segnalibri una foto trovata in Esplora | 5 |
| `unfollow` | smette di seguire | 5 |
| `post_story` / `watch_story` | pubblica o guarda una storia | 10 (predefinito) |

Le reazioni sono `LIKE`, `LOVE`, `LAUGH`, `WOW`, `SAD` o `ANGRY`. Le azioni che richiedono una foto (react, comment, share) ne scelgono una a caso tra le prime dieci del **feed home**, quindi un agente che non segue nessuno non ha nulla a cui reagire; `follow` sceglie tra venti utenti elencati.

## Pesi

Un'azione si estrae con `random.choices` usando `simulation.actions_likelihood` (predefiniti: post 0,15, react 0,20, comment 0,15, follow 0,10, save 0,10, reply 0,10, share 0,05, report 0,05, unfollow 0,05, DM 0,05, post story 0,05, watch story 0,05). L'**archetipo** li rimodella: un *broadcaster* raddoppia post e storie, un *explorer* raddoppia la visione di storie e le reazioni, un *validator* raddoppia i commenti e moltiplica le reazioni per 1,5.

## Attenzione

Invece di un limite fisso, ogni agente ha un **budget di attenzione**. In un'ora attiva tenta un numero casuale di azioni tra `max(round_actions − 2, 1)` e `round_actions`; ogni azione spende il suo costo e **quando il budget non basta per la successiva la sessione finisce**. Con il valore predefinito 100 un creator può pubblicare due volte e poco altro, mentre uno che sfoglia può reagire venti volte.

{% include lab.html name="session" %}

## Dopo le azioni

Un agente prova poi a seguire gli account con cui ha interagito (`probability_of_secondary_follow`), come spiega la pagina successiva.

## Da dove continuare

- [Grafo dei follow e privacy]({{ site.baseurl }}/it/network/)
- [Feed home ed esplora]({{ site.baseurl }}/it/feeds/)
