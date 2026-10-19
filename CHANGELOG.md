# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

Changes made since the last published state of `main`, newest first:

- Docs: README citation updated to the published YSocial reference (Big Data & Society, 2026)
- Hashtags: canonical form without '#', apostrophes and accents kept in the tag, case-insensitive identity
- Photo: caption prompts no longer mention simulation day and slot
- Photo: localized in-code prompts, no wrapping quotes, share commentary instead of an identifier
- Prompts i18n step 5: localize the follow action and the reciprocal-follow verb
- Prompts i18n step 5: move the remaining English persona fragments into the packs
- Prompts i18n step 5: run_client activates the prompt language (Ray workers too)
- Prompts i18n step 4: Italian internal prompt pack
- Prompts i18n step 3: prompt_store language support
- Prompts i18n: remove unused protocol_tokens copy
- Prompts i18n step 2: renderer update
- Prompts i18n step 1: move in-code prompts to prompts_internal.json
- i18n: shorter, purpose-oriented plugin descriptions
- Keep the local image generation dependencies in requirements.txt
- Align requirements with the library versions shipped by YWeb
- update .gitignore
- deps: bump SQLAlchemy>=2.0, langchain>=0.3
