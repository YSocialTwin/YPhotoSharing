---
title: "Build on it"
subtitle: "Where to extend the simulator, how to test it and how this site is built."
goal: "Extend YPhotoSharing without breaking the checks."
time: "15 minutes"
---

## Extension points

- **Ranking.** The home ranking is in `YServer/recsys/feed_ranking_service.py`, Explore in `explore_recsys.py`, trends in `trend_service.py`, virality in `services/virality_service.py`. Add a signal only if it comes from an existing photo-sharing behaviour, is cheap to compute each round and explains an observed effect.
- **Actions.** Each action is a module in `YClient/actions/` with a handler in `agent.py` and a cost in the attention table.
- **Moderation.** Replace the keyword stub in `services/moderation_service.py` with a real classifier.
- **Models.** `YClient/LLM_interactions/` holds the language, vision, batch and image services.
- **Prompts.** Personas and tasks live in `prompts_ygram.json` and the internal prompt packs (English and Italian).
- **Admin and participant pages.** The platform brings its own pages, routes, templates and styles as a plug-in of YSocial (`ysocial_platform/`), so the core does not change.

## Tests

```bash
python -m pytest -q
```

The suite covers the repository layer, annotations, recommendations, stress and reward, logging, schema parity, the gateway and the platform bindings; it does not replace a long multi-client soak test against a real Ray cluster and a real model.

## This site

It lives in `docs/` next to the MkDocs pages of the repository (which Jekyll ignores) and is built by the *Documentation* workflow. The Parameters and Database schema pages are generated:

```bash
python scripts/make_parameters_data.py
python scripts/make_schema_data.py
python scripts/make_schema_data.py --check
```

## More

- [Repository](https://github.com/YSocialTwin/YPhotoSharing) · [Alignment with YSimulator](https://github.com/YSocialTwin/YPhotoSharing/blob/main/docs/ysimulator_alignment.md) · [Remaining gaps](https://github.com/YSocialTwin/YPhotoSharing/blob/main/docs/remaining_gaps.md) · [Platform requirements](https://github.com/YSocialTwin/YPhotoSharing/blob/main/docs/platform_requirements.md)
