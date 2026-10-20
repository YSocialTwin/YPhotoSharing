# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
