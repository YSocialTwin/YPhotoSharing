# Remaining Gaps vs YSimulator

This document lists what is still not at YSimulator parity, ordered by impact.
It is meant to drive the next implementation pass without reopening the parts
that are already aligned.

## Status Summary

- Core observability is aligned enough for day-to-day debugging.
- Photo-topic persistence, opinion paths, and stress/reward persistence are in
  place.
- Server decomposition, client bootstrap cleanup, and shared interaction
  helpers are now partially decomposed.
- Annotation toggles for emotion, sentiment, and memory are documented and
  configurable.
- The main remaining gap is platform-specific depth, not basic correctness.
- YPhotoSharing must remain photo-first; some YSimulator concepts should stay
  absent or only be adapted conceptually.

## Priority 0: Server Decomposition

Status: in progress, with a first repository layer now in place.

Why it matters:
- This is the largest structural difference from YSimulator.
- It affects maintainability, testability, and how easy it is to add new
  interaction families.

What is missing:
- A real repository layer around repeated DB access patterns.
- Request/action processor boundaries between the orchestrator and the storage
  code.
- Clear separation between coordination, persistence, and domain policy.

Next implementation steps:
1. Split the broad `db_middleware.py` helpers into focused repository modules.
2. Move action-specific server logic into processor/service units.
3. Keep `OrchestratorServer` as the coordination entrypoint only.
4. Preserve photo-native semantics while extracting shared plumbing.

Validation:
- New server features should be addable without touching unrelated DB helpers.
- Unit tests should target repository/service classes directly.

## Priority 1: Client Orchestration Cleanup

Status: in progress, with user bootstrap logic extracted from the actor.

Why it matters:
- The client is already better structured, but the coordination layer is still
  heavier than YSimulator’s.
- Further extraction reduces risk when adding new action families or tuning
  round scheduling.

What is missing:
- A clearer split between scheduling, agent selection, and action execution.
- Optional per-action generators/processors for the most complex behaviors.

Next implementation steps:
1. Move round-planning and agent selection fully behind a client-side
   orchestration helper.
2. Keep `SimulationClient` as a thin coordinator.
3. Extract per-action helper paths only when the action logic starts to repeat.

Validation:
- The client should be easier to read at a glance.
- Round scheduling should be testable without running the full simulation.

## Priority 2: Cross-Cutting Domain Helpers

Status: implemented for topic recovery, memory annotation, opinion path
recording, and stress/reward persistence.

Why it matters:
- Opinion and stress/reward logic are now correct, but some of the supporting
  code still lives too close to the action handlers.

What is missing:
- More reusable helpers for topic recovery, opinion path persistence, and
  affective-state bookkeeping.
- A stronger boundary around shared policy logic versus per-action glue.

Next implementation steps:
1. Consolidate repeated topic recovery logic.
2. Keep opinion-path recording and stress/reward persistence behind a shared
   helper interface.
3. Avoid reintroducing duplicated logic in `comment`, `react`, and
   `reply_comment`.

Validation:
- The same interaction should not require duplicate policy code in multiple
  action modules.

## Priority 3: Optional YSimulator-Style Secondary Structuring

Status: deferred until a concrete duplication hotspot appears.

Why it matters:
- YSimulator is more deeply modular, but YPhotoSharing does not need a literal
  copy of every submodule.

What is missing:
- Only the extra decomposition that becomes useful once the project grows
  again.

Recommended stance:
- Add new modules only when they remove real duplication.
- Do not create placeholder packages just to mirror YSimulator names.
- Preserve the Instagram-like domain model as the primary design constraint.

Validation:
- Any new package should have a clear responsibility and a test reason.

## Priority 4: Platform-Specific Depth

Status: still open.

Why it matters:
- This is not parity work in the narrow sense, but it is the place where
  YPhotoSharing should differentiate itself.

What is missing:
- Richer story behavior.
- Better media-centric discovery and ranking signals.
- Stronger creator-centric retention signals.

Next implementation steps:
1. Improve the features that are unique to a photo-sharing platform.
2. Prefer changes that affect generated media, stories, or visual discovery.
3. Keep microblogging-specific abstractions out of the core path.

Validation:
- The simulation should feel more like Instagram, not like a renamed microblog.

## Not A Gap

The following items are already handled and should not be reworked unless a
regression appears:

- structured execution logging from the Ray actors
- optional action and prompt logs
- bounded-confidence opinion updates
- discrete LLM-based opinion transitions
- opinion-path persistence
- stress/reward persistence and aggregation
- photo-topic persistence
- phase-level regression tests
- annotation toggles for emotion, sentiment, and memory

## Working Order

If the next pass needs a strict order, use this sequence:

1. Server decomposition
2. Client orchestration cleanup
3. Shared domain helper extraction
4. Optional secondary structuring
5. Instagram-specific depth improvements

That order keeps the current behavior stable while reducing the remaining
coupling in the most expensive areas first.
