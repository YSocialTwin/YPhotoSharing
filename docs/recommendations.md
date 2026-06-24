# Recommendations and Ranking Signals

This page documents the recommendation and discovery behavior currently
implemented in YPhotoSharing. The system is intentionally photo-first, so the
signals are media- and creator-centric rather than text-thread-centric.

## Home Feed

The home feed is produced by the server-side `FeedRankingService` and is used
for followed-account content.

### Behavior

- candidate generation starts from photos published by accounts the user
  follows
- the candidate pool is truncated to keep ranking cheap
- photos are sorted by a learned-like surrogate score rather than strict
  chronology

### Signals

| Signal | Source | Why it matters |
|---|---|---|
| Social affinity | `Reaction`, `Comment`, `SavedPhoto` joins with `Photo` | Captures the user's prior relationship with an author |
| Topic overlap | `UserInterest` + `PhotoTopic` | Boosts posts aligned with declared interests |
| Photo popularity | `num_likes`, `num_comments`, `num_shares` | Reflects local engagement around the post |
| Virality | `viral_score` | Captures broader platform momentum |
| Visual quality | `aesthetic_score` | Rewards stronger media quality |
| Freshness | `created_at` decay | Prevents stale content from dominating |
| Visual emotion | `PhotoEmotion` | Gives a small boost to positive visual signals |
| Sentiment | `sentiment_score` | Slightly rewards positive captions and penalizes negative ones |

The ranking is intentionally multi-signal. This keeps the home feed closer to a
photo-sharing platform than a pure text social network, where engagement and
visual quality both matter.

## Explore Feed

The explore feed is produced by `ExploreRecsys`.

### Behavior

- captions are matched against the user's declared interests using TF-IDF and
  cosine similarity
- the author's `recsys_type` acts as a coarse collaborative-filtering proxy
- virality and trend momentum are used as secondary ranking signals

### Signals

| Signal | Source | Why it matters |
|---|---|---|
| Interest text match | `Interest` + caption TF-IDF | Captures semantic similarity between user preferences and content |
| Topic overlap | `PhotoTopic` + `UserInterest` | Reinforces explicit content labeling |
| Author cluster | `User_mgmt.recsys_type` | Adds a cheap collaborative-filtering style bias |
| Virality | `viral_score` | Keeps momentum visible |
| Trend momentum | `TrendService` over hashtag usage | Surfaces recent hashtag acceleration |
| Sentiment | `sentiment_score` | Slightly adjusts ranking toward healthier content |

## Follow Suggestions

Follow suggestions are produced by `FollowRecsys`.

### Behavior

- users already followed are excluded
- candidate users are ranked by `influence_score`

### Signals

| Signal | Source |
|---|---|
| Influence | `User_mgmt.influence_score` |
| Exclusion of existing graph edges | `Follow` |

This keeps the follow graph simple and stable. More complex mutual-interest
heuristics can be added later if they become necessary.

## Stories and Ephemeral Media

Stories are currently chronological rather than heavily ranked.

### Behavior

- stories are inserted as ephemeral media items
- views are counted in `story_views`
- recent story retrieval uses the follow graph as the main filter

### Signals

| Signal | Source |
|---|---|
| Follow graph | `Follow` |
| Recency | `created_at` |
| Story engagement | `StoryView.view_count` |

## Recommendation Design Choices

1. Prefer direct photo signals over generic social-network abstractions.
2. Keep ranking cheap enough to run every simulated round.
3. Use multiple weak signals rather than a single brittle score.
4. Preserve Instagram-like semantics even when reusing YSimulator patterns.

## When To Extend The Model

Add new ranking signals only when they satisfy one of these conditions:

- they come from an existing photo-sharing behavior
- they are cheap to compute during simulation
- they explain an observed platform effect better than the current signals

Otherwise, keep the model simple and avoid turning the simulator into a
general-purpose recommender system.
