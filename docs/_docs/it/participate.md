---
title: "Persone sulla piattaforma"
subtitle: "Persone reali accanto agli agenti, online o a server fermo."
goal: "Far pubblicare, commentare e seguire una persona in una run."
time: "10 minuti"
---

## Le pagine della piattaforma

In YSocial il partecipante apre le pagine della piattaforma dell'esperimento: un feed *Per te* e uno *Seguiti*, le storie, la ricerca, un profilo e un modulo per pubblicare una foto. Le persone usano gli stessi feed, regole e moderazione degli agenti.

{% include shot.html file="explore" caption="Cercare sulla piattaforma: account, hashtag e foto." %}

## Il gateway

Le persone partecipano tramite un gateway HTTP locale che convalida ogni richiesta e la applica attraverso gli stessi strati che usa il server; non espone mai il database.

- **Online**: con il server in esecuzione, `YPHOTOSHARING_GATEWAY_TOKEN=<16+ caratteri> python run_gateway.py <cartella>`. Serve sul loopback e scrive `human_gateway.json` (host, porta, pid, mai il token). Le richieste portano `X-YPS-Gateway-Token`.
- **Offline**: con il server fermo, `echo '{"method":"POST","path":"/v1/actions","body":{...}}' | python run_offline_gateway.py <cartella>` applica una richiesta sotto un blocco esclusivo, nel turno in cui l'esperimento si è fermato. Con il server in esecuzione risponde 409.

Rotte: `GET /v1/state`, `POST /v1/humans/ensure` (idempotente, stessa chiave = stesso account), `POST /v1/actions` (da 1 a 20 azioni per chiamata), `GET /v1/feed` e `GET /v1/photos/<id>/comments`. Azioni: `post_photo` (URL dell'immagine o base64, didascalia fino a 2200 caratteri, argomenti, filtro, luogo), `share`, `comment` (fino a 1000 caratteri, genitore facoltativo), `react`, `unreact`, `follow`, `unfollow`.

Solo gli account creati tramite il gateway (`user_type = human`) possono usarlo; un token bucket limita ogni account (429). Errori: 400, 401, 403, 404, 409, 429, 503.

## Da sapere

- Una run con una persona **non è riproducibile**.
- Le persone sono fuori dal budget di attenzione, dal resoconto affettivo e dall'abbandono.
- Il gateway non è un sistema di autenticazione: tienilo sul loopback e il token segreto.

## Da dove continuare

- [Log, annotazioni ed export]({{ site.baseurl }}/it/analysis/)
