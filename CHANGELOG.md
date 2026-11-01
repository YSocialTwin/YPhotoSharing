# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- Federation: sharing another agent's photo on other platforms (F8, opt-in, `agent_action`): a marked share leaves as `crosspost.v1` with `quoted` (original author, caption, reference; null identity outside the identity map) and the destination writes the caption with an attribution line and keeps the structured reference in `federation_quoted`. The client draws once per platform when it shares (nothing is drawn otherwise).
- Cross-post as an agent action (opt-in, `federation.crosspost_mode: agent_action`): after choosing the caption the agent draws once per platform where it is also active (`get_federation_destinations`) with `crosspost_propensity` and sends `crosspost_to` ([{member, text}]) with the photo, with the model's version of the caption (prompts `crosspost_adapt_<platform>`, EN and IT; `LLMService.adapt_crosspost`) or the rule text; the server adapter sends one `crosspost.v1` per chosen destination instead of `content.v1`. Default mode unchanged.
- Federation local churn (F4.5, opt-in): `churned_agents(day)` gives the accounts whose `left_on` round is in the days up to the given one and that the federation still sees as active, so the coordinator records them as left with reason churn.
- Federation exposures (F4.4b, opt-in `federation.exposures`): with `federation.exposures` the adapter also hands `exposure.v1` to the bus: recommended photos that are materialised cross-posts are views (approximate), reactions and comments are interactions (exact); tie from the follow table; table `federation_exposure_log`, fixed per tick.
- Federation attention (opt-in): `apply_attention` stores the multiplier of the day per account (table `federation_attention`); `get_federation_attention` serves it and the round planner scales the chance that an agent acts in a round; with the federation off or multiplier 1 nothing changes.
- Federation affective report (opt-in): `affective_report(day)` of the adapter gives the native stress/reward of the active accounts at the end of the day, read from the runtime's own tables without writing.
- Federation (opt-in): `YPhotoSharing/YServer/federation/` (adapter `photo_sharing`, gate wrapper); the server advances a round only when the coordinator allows it, and the client waits for the round by polling `round_pending`. Enabled by the `federation` section of the server configuration; standalone behaviour is unchanged.
- Federation (opt-in), bus and membership: tables `federation_membership`, `federation_ref`, `federation_export`, `federation_state` (created only when the federation is on); photos the agents mark with `crosspost` are exported as `content.v1` and incoming `crosspost.v1` become photos of the author with their image (text-only cross-posts are skipped); accounts that are not active are left out of feeds, recommendations and follow suggestions (`get_federation_inactive_agents`); the client skips them and draws the cross-post choice with `federation.crosspost_propensity`.

## [2.1.0] - 2026-10-20

### Added
- Hashtags in canonical form: no leading `#`, apostrophes and accents kept, case-insensitive identity.
- Localized in-code prompts for photos, without wrapping quotes; a shared photo is commented instead of quoting an identifier.
- The prompt language is active in `run_client`, Ray workers included.
- Prompts i18n: prompts moved out of the code into `prompts_internal.json`, read through `prompt_store` with language support.
- Prompts i18n: protocol tokens and tolerant parsers (no `eval`); Italian internal prompt pack.
- Prompts i18n: localized follow action and reciprocal-follow verb; persona fragments moved into the packs.

### Changed
- Dependencies aligned with YWeb (SQLAlchemy >= 2.0, langchain >= 0.3); the local image generation dependencies stay in `requirements.txt`.
- Shorter, purpose-oriented plugin description in `meta/info.json`.
- License: GPL-3.0-only (`LICENSE` added, `meta/info.json`, README).
- README restructured on the common layout; citation updated to the published YSocial reference (Big Data & Society, 2026).

### Removed
- Unused copy of `protocol_tokens`.

### Fixed
- Caption prompts no longer mention the simulation day and slot.

[Unreleased]: https://github.com/YSocialTwin/YPhotoSharing/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/YSocialTwin/YPhotoSharing/releases/tag/v2.1.0
