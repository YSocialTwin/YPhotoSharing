# Annotation Controls

YPhotoSharing supports several optional annotation streams that enrich the
simulation with photo-specific metadata and interaction history.

## Supported Toggles

Place these keys under `simulation` in `client_config.json`:

```json
{
  "simulation": {
    "enable_emotion_annotation": true,
    "enable_sentiment": true,
    "enable_memory_annotations": true
  }
}
```

That same block can be combined with the logging flags that expose the
debugging streams used by the client:

```json
{
  "logging": {
    "enable_action_log": true,
    "enable_prompt_log": true,
    "enable_llm_usage_log": true
  }
}
```

- `enable_emotion_annotation`: stores the dominant visual emotion for new
  photos in `photo_emotions`
- `enable_sentiment`: stores a numeric sentiment score for photos and
  comments
- `enable_memory_annotations`: writes memory events and makes the client load
  memory context into comments and DMs

## Practical Guidance

- Keep `enable_emotion_annotation` on when you want the platform to preserve
  visual labels attached to generated photos.
- Keep `enable_sentiment` on if you want downstream analytics or moderation to
  exploit text polarity.
- Keep `enable_memory_annotations` on if you want agents to condition comments
  and direct messages on prior interactions.

## Related Settings

- `logging.enable_action_log` enables per-client action summaries
- `logging.enable_prompt_log` enables per-client prompt traces
- `logging.enable_llm_usage_log` enables per-client LLM usage accounting
- `stress_reward.enabled` enables the affective feedback loop
- `simulation.opinion_dynamics.enabled` enables bounded-confidence or
  discrete LLM opinion updates

These toggles are orthogonal. You can enable them independently depending on
how much annotation detail you want in an experiment.
