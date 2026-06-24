# Logging

YPhotoSharing now mirrors the YSimulator logging layout more closely while
preserving the photo-sharing semantics of the platform.

## File Streams

The runtime writes the following rotating JSON logs under `logs/`:

- `logs/<client_id>_execution.log`
- `logs/<server_name>_server.log`
- `logs/<client_id>_actor.log`
- `logs/<server_name>_actor.log`
- `logs/_server.log`
- `logs/<client_id>_llm_usage.log`

Optional auxiliary streams remain available when enabled:

- `logs/<client_id>_actions.log`
- `logs/<client_id>_prompts.log`

## What Each Stream Contains

- `*_execution.log` records the high-level component runtime lifecycle.
- `*_actor.log` captures the shared actor-side structured logger output.
- `_server.log` records server request traces with:
  - `request_id`
  - `client_name`
  - `path`
  - `status_code`
  - `duration`
  - `time`
  - `tid`
  - `day`
  - `hour`
  - optional `error`
- `*_llm_usage.log` records one JSON line per LLM call with:
  - `timestamp`
  - `method`
  - `input_tokens`
  - `output_tokens`
  - `total_tokens`
  - `cumulative_calls`
  - `cumulative_tokens`
  - optional `cost` and `cumulative_cost`
  - `event: "gpu_selection"` records when a GPU/backend assignment is logged

All of these streams use gzip rotation and flush each record immediately.

## Configuration Flags

The following keys live under `logging` in the relevant config file:

```json
{
  "logging": {
    "enable_console_log": true,
    "enable_execution_log": true,
    "enable_server_log": true,
    "enable_actor_log": true,
    "enable_request_log": true,
    "enable_prompt_log": false,
    "enable_action_log": false,
    "enable_llm_usage_log": true
  }
}
```

- `enable_execution_log` controls the client execution stream.
- `enable_server_log` controls the server execution stream.
- `enable_actor_log` controls the actor-side structured stream.
- `enable_request_log` controls the server request trace stream.
- `enable_llm_usage_log` controls the client LLM usage stream.
- `enable_prompt_log` controls the optional prompt trace stream.
- `enable_action_log` controls the optional action summary stream.

## Practical Notes

- Keep `enable_llm_usage_log` on when you want YSimulator-style usage
  accounting and reproducible LLM trace files.
- Keep `enable_request_log` on when you need to correlate platform actions with
  the server-side timing and round context.
- Disable `enable_prompt_log` only if you do not need per-prompt debugging.

