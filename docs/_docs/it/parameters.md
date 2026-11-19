---
title: "Parametri"
subtitle: "Ogni impostazione di una run, con il suo significato, i suoi valori e il suo valore predefinito."
goal: "Trovare un'impostazione, sapere che cosa fa e quale file la contiene."
time: "riferimento"
tabs: false
---

Una run si configura con due file JSON nella cartella dell'esperimento, più la popolazione.

<div class="ys-cols2">
<div><h3>1 · Server</h3><p><code>server_config.json</code>: nome, client necessari, timeout, database, annotazioni e log dell'orchestratore.</p></div>
<div><h3>2 · Client</h3><p><code>client_config.json</code>: la simulazione (tempo, immagini, annotazioni, argomenti, opinioni, ciclo di vita, azioni, attività), i modelli di linguaggio e visione, stress e ricompensa, log.</p></div>
<div><h3>3 · Popolazione</h3><p><code>agents.json</code>: chi sono gli agenti. Vedi <a href="{{ site.baseurl }}/it/agents/">Agenti e popolazione</a>.</p></div>
</div>

Tutto ciò che non è scritto prende il valore predefinito, quindi un file elenca solo ciò che cambi.

<div class="ys-params" data-src="{{ site.baseurl }}/assets/data/parameters.json"><noscript>Abilita JavaScript per sfogliare i parametri, oppure leggi <a href="https://github.com/YSocialTwin/YPhotoSharing/blob/main/docs/configuration.md">docs/configuration.md</a>.</noscript></div>

## Da dove continuare

- [Configurazione]({{ site.baseurl }}/it/configuration/)
- [Schema del database]({{ site.baseurl }}/it/database-schema/)
