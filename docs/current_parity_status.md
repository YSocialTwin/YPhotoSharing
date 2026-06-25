# Current YPhotoSharing vs YSimulator Parity Status

Date: 2026-06-25

## Scope

This note re-checks the parity-sensitive areas that were previously identified
as regression-prone after the recent rebases:

- distributed Ray runtime
- client/server coordination surface
- logging and request tracing
- content annotation: sentiment, emotion, toxicity
- stress/reward persistence
- opinion dynamics and opinion-path persistence
- topic persistence for generated photos

The target is behavioral parity where the two simulators share the same
engineering concept, while preserving YPhotoSharing's photo-first and
Instagram-like semantics.

## Executive Summary

The critical parity regressions previously documented are now fixed.

Current status:

- runtime actor parity: restored
- server API surface used by actions: restored
- annotation pipeline parity: restored for posts, comments, and replies
- generic sentiment/emotion/toxicity persistence: restored
- opinion dynamics runtime parity: restored for bounded-confidence and
  LLM-evaluation paths
- stress/reward persistence path: reachable again through the live server actor
- logging file layout parity: aligned, including `_server.log`,
  `*_actor.log`, and `*_llm_usage.log`

Remaining caution:

- the test suite now covers the repaired runtime surfaces and key parity paths,
  but it still does not replace a long multi-client simulation soak test
  against a real Ray cluster and real LLM backend.

## Fixed Regressions

### 1. Distributed Runtime

Status: fixed

- `OrchestratorServer` is again exposed as a Ray actor.
- `SimulationClient` is again exposed as a Ray actor.
- `run_server.py` and `run_client.py` now target matching actor surfaces.
- server methods required by the action layer are reachable again.

### 2. Client Synchronization and Server API Reachability

Status: fixed

- the live server now exposes the API required by:
  - photo posting
  - comments and replies
  - reactions
  - follows and follow requests
  - recommendations
  - stress/reward updates
  - opinion updates and opinion-path recording
  - topic lookup and user-interest updates

This restores end-to-end reachability for the previously stranded
coordination, opinion, and stress/reward modules.

### 3. Annotation Behavior

Status: fixed

The runtime action layer now follows one shared annotation contract instead of
mixing action-local shortcuts with helper-level processing.

Current behavior:

- `post_photo`, `post_comment`, and `reply_comment` call the shared
  `annotate_content(...)` helper
- annotations are forwarded to `server.process_annotations(...)`
- topic IDs and round IDs are attached before persistence
- photo and comment aggregate sentiment fields are still updated using the
  shared annotation result's `compound` score

This aligns YPhotoSharing with YSimulator's annotation integration pattern
while preserving the platform-specific photo/comment fields used elsewhere.

### 4. Annotation Persistence

Status: fixed

The following YSimulator-style generic metadata tables are now present and used:

- `post_emotions`
- `post_sentiment`
- `post_toxicity`

The middleware persists generic annotation rows while still preserving the
photo-specific topic and emotion relations used by YPhotoSharing.

### 5. Emotion Taxonomy and LLM Backends

Status: fixed

The LLM backends now expose `extract_emotions(...)` with GoEmotions-compatible
output parsing across:

- standard LLM service
- vLLM service
- remote batch service

The older single-emotion helper remains only as a compatibility wrapper.

### 6. Opinion Dynamics

Status: fixed

The LLM-evaluation path no longer references out-of-scope variables inside
`OpinionCalculator._calculate_llm_evaluation(...)`.

Current parity state:

- bounded-confidence updates work
- LLM-evaluation uses discrete ordered Likert classes
- transitions remain restricted to adjacent classes
- opinion paths are persisted
- neighbor-scope aggregation is reachable through the server actor

### 7. Stress/Reward

Status: fixed

The server actor again exposes the stress/reward persistence and lookup methods
used by the client action layer, so the previously integrated YSimulator-style
stress/reward path is reachable in live execution.

### 8. Logging

Status: fixed

The logging layout now matches the documented YSimulator-aligned structure:

- `logs/<client_id>_execution.log`
- `logs/<server_name>_server.log`
- `logs/<client_id>_actor.log`
- `logs/<server_name>_actor.log`
- `logs/_server.log`
- `logs/<client_id>_llm_usage.log`

The server execution log naming no longer strips the `_server` suffix from the
instance name, so a server called `orchestrator_server` correctly writes to:

- `logs/orchestrator_server_server.log`

## Test Evidence

The repaired areas are covered by targeted tests for:

- runtime actor exposure
- logging file generation and request log shape
- annotation flags and annotation persistence
- action-layer routing through `process_annotations(...)`
- discrete opinion-path persistence
- LLM-evaluation opinion updates
- stress/reward aggregation helpers

Most recent validation during this repair cycle:

- focused parity suites passed
- full repository suite should still be rerun after any further changes

## Bottom Line

YPhotoSharing is now back to parity with YSimulator for the previously
documented regression areas, while keeping its photo-sharing-specific data
model and behaviors intact.

Residual risk is operational rather than structural: a real multi-client
simulation run should still be used as the final validation step before
considering the recovery complete.
