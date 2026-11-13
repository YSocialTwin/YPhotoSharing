# Human participation gateway

People take part in an experiment through a local HTTP gateway, with the server running or not. The gateway never
exposes the database: it validates the request and applies it through the same layers the server uses.

## Running it

- **Online**: `YPHOTOSHARING_GATEWAY_TOKEN=<>=16 chars> python run_gateway.py <experiment_folder>` after the server. It
  connects to the server actor, serves on loopback (`human.gateway.host`/`port` of `server_config.json`, default a free
  port) and writes `human_gateway.json` (host, port, pid; never the token). Every request needs the header
  `X-YPS-Gateway-Token`.
- **Offline** (server stopped): `echo '{"method":"POST","path":"/v1/actions","body":{...}}' | python run_offline_gateway.py <experiment_folder>`
  applies one request to the experiment database under an exclusive lock (`human_gateway.lock`), in the round where the
  experiment stopped, and prints `{..., "status": N}`. With the server running (`ray_ready.temp` present) it answers
  409 `server_running`: use the online gateway.

## Routes (JSON, same offline with `method` / `path` / `query` / `body`)

| Route | Body / query | Answer |
|---|---|---|
| `GET /v1/state` | | `round_id`, `day`, `hour`, `federated`, `crosspost_mode` |
| `POST /v1/humans/ensure` | `human_key` (no `:`), `username?`, `language?` | `account_id`, `global_agent_id` (`human:<human_key>` with a federation, else null), `created`; idempotent, same key = same account |
| `POST /v1/actions` | `account_id`, `actions` (1..20) | `ok`, `results[]` (one per action) |
| `GET /v1/feed?account_id=&limit=` | | `photos[]` (home feed; accounts not active in the federation are hidden) |
| `GET /v1/photos/<id>/comments?account_id=&limit=` | | `comments[]` |

Actions (`type`): `post_photo` (`image_url` or `image_base64`+`extension`, `caption` ≤ 2200, `topics[]`, `filter_name`,
`location_name`), `share` (`photo_id`, `caption`), `comment` (`photo_id`, `body` ≤ 1000, `parent_comment_id?`), `react`
(`photo_id`, `reaction_type` LIKE/LOVE/LAUGH/WOW/SAD/ANGRY), `unreact`, `follow`, `unfollow` (`user_id`).

Cross-post: `post_photo` and `share` accept `crosspost_to: [{"member", "text"?}]` (text ≤ 300; default the caption), exactly
the field an agent sends. It works with `federation.crosspost_mode = agent_action`: the request is recorded in
`federation_crosspost` and leaves at the first barrier (after a restart when it was made offline). A `share` is exported
with `quoted` (the original author: an agent, another person, or an anonymous account).

Only accounts created through the gateway (`user_type = human`) can use it (403 otherwise); the rate limit is a token
bucket per account (429). Errors: 400 `invalid_request`, 401 `unauthorised`, 403 `not_allowed`, 404 `not_found`,
409 `server_running`, 429 `rate_limited`, 503 `unavailable`.

## Federation

A person's global identity is `human:<human_key>` (table `federation_human`). People never take the local id as identity,
and they are outside attention, the affective report and churn. Joining a federation that is already running needs the
coordinator to know the identity (protocol side, not part of this repository).
