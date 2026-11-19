---
title: "Come funziona"
subtitle: "Ore, slot, chi agisce e la divisione tra client e server."
goal: "Capire il ciclo di un'ora simulata e i compiti di client e server."
time: "10 minuti"
---

## Il tempo

Un **giorno** ha 24 **slot**, uno per ora simulata; un turno è uno slot. `simulation.num_rounds` è il numero di ore da eseguire (48 sono due giorni; una settimana è 168). `start_day` fissa da dove parte l'orologio. L'orologio è del server, che **aspetta alla fine di ogni ora** finché tutti i client registrati dicono di essere pronti (servono `min_to_start` client per cominciare).

## Chi possiede che cosa

| | Client (`YClient`) | Server (`YServer`) |
|---|---|---|
| Agenti | li ospita: persona, interessi, tratti, memoria | memorizza account, foto, commenti, follow |
| Decisioni | **decide** chi agisce, quale azione, che cosa scrivere | non decide mai per un agente |
| Modelli | chiama i modelli di linguaggio, visione e immagini | nessuno |
| Feed | li richiede | **calcola** home, esplora e suggerimenti di follow |
| Regole | nessuna | privacy, richieste di follow, moderazione, tendenze e viralità alla barriera |
| Database | nessuno | l'unico a scrivere (SQLite tramite SQLAlchemy) |

Più client possono collegarsi a un server, ciascuno con la sua porzione di popolazione: il server li aspetta tutti.

## Un'ora, passo per passo

1. Il client chiede al server che turno è.
2. Per ogni agente decide se è **attivo** in quest'ora (vedi sotto).
3. Ogni agente attivo esegue una **sessione**: a mezzanotte un account privato esamina le richieste di follow; si aggiorna la soddisfazione; poi si estraggono alcune azioni entro un budget di attenzione ([Che cosa fanno gli agenti]({{ site.baseurl }}/it/actions/)).
4. Si tentano i follow secondari; gli eventi del ciclo di vita (abbandono, nuovi utenti) si applicano una volta al giorno.
5. Il client dice al server di essere pronto. Alla barriera il server aggiorna punteggi di viralità e tendenze, esegue la moderazione e arricchisce le nuove foto.

{% include lab.html name="activity" %}

## Come gira

YPhotoSharing è un simulatore basato su Ray costruito come YSimulator: `run_server.py` avvia Ray e l'attore orchestratore (che crea il database); `run_client.py` esegue un client. In YSocial la piattaforma si installa dalla pagina *Plugins* del pannello di amministrazione e si guida dalle pagine dell'esperimento; gira anche da sola.

## Da dove continuare

- [Agenti e popolazione]({{ site.baseurl }}/it/agents/)
- [Che cosa fanno gli agenti]({{ site.baseurl }}/it/actions/)
- [Eseguire un esperimento]({{ site.baseurl }}/it/running/)
