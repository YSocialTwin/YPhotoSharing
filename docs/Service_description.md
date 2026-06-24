# Instagram Digital Twin Specification

## Overview

Instagram can be modeled as a **visual social network** in which users create, consume, and interact with static visual content while recommendation systems mediate content exposure and network evolution.

A digital twin of Instagram should capture:

1. User actions
2. Recommendation systems
3. Platform dynamics
4. State evolution of users, content, and social networks

---

# 1. User Actions

## 1.1 Content Creation

Actions that generate new static content objects.

| Action          | Description                              | Object Created |
| --------------- | ---------------------------------------- | -------------- |
| Upload photo    | Publish one or more images               | Feed Post      |
| Create carousel | Publish multiple images in a single post | Feed Post      |
| Add caption     | Attach textual description               | Metadata       |
| Add hashtags    | Associate topical labels                 | Metadata       |
| Add location    | Associate geographic information         | Metadata       |
| Tag users       | Mention users in content                 | Social Edge    |

### Associated State Variables

* Content topic
* Content quality
* Number of images
* Posting time
* Caption length
* Hashtag set
* Tagged users

---

## 1.2 Content Consumption

Actions through which users consume content.

| Action                  | Description                             |
| ----------------------- | --------------------------------------- |
| View post               | Open a feed post                        |
| Browse profile          | Visit another user's profile            |
| Search content          | Search for users, hashtags, or posts    |
| Explore recommendations | Browse recommended content              |
| Open hashtag page       | Browse posts associated with a hashtag  |
| Open location page      | Browse posts associated with a location |

### Associated State Variables

* Dwell time
* Number of viewed posts
* Session duration
* Scroll depth
* Content diversity

---

## 1.3 Social Interactions

Actions that create engagement.

| Action                   | Description                      |
| ------------------------ | -------------------------------- |
| Like                     | Express appreciation for content |
| Comment                  | Add textual feedback             |
| Reply to comment         | Respond to another comment       |
| Share via direct message | Forward content to another user  |
| Save content             | Bookmark content                 |
| Mention user             | Reference another user           |

### Engagement Metrics

* Likes
* Comments
* Replies
* Shares
* Saves

---

## 1.4 Network Formation

Actions that modify the social graph.

| Action                | Description                           |
| --------------------- | ------------------------------------- |
| Follow account        | Create a follower relationship        |
| Unfollow account      | Remove a follower relationship        |
| Accept follow request | Approve a private account request     |
| Reject follow request | Deny a follow request                 |
| Block account         | Prevent interactions                  |
| Restrict account      | Limit interactions                    |
| Mute account          | Reduce visibility without unfollowing |

### Graph Representation

Users are represented as nodes:

```text
User_i → User_j
```

where the directed edge indicates a follow relationship.

---

## 1.5 Profile Management

| Action                  | Description                       |
| ----------------------- | --------------------------------- |
| Edit profile            | Modify profile information        |
| Change privacy settings | Configure account visibility      |
| Manage highlights       | Curate persistent profile content |
| Link external accounts  | Connect external platforms        |

---

# 2. Recommendation Systems

Instagram uses multiple recommendation systems targeting different user surfaces.

---

## 2.1 Feed Ranking System

Ranks candidate feed posts.

### Candidate Sources

* Followed accounts
* Suggested accounts

### Input Signals

* Relationship strength
* Historical engagement
* User interests
* Content popularity
* Content recency

### Predicted Outcomes

* Probability of like
* Probability of comment
* Probability of save
* Probability of share
* Expected dwell time

### Objective

Maximize user engagement and retention.

---

## 2.2 Explore Recommendation System

Provides content discovery beyond the follower graph.

### Input Signals

* Similar users
* Similar content
* Topic embeddings
* Historical engagement patterns

### Recommendation Methods

* Collaborative filtering
* Content-based filtering
* Embedding similarity

### Objective

Maximize content discovery and session duration.

---

## 2.3 People Recommendation System

Generates "Suggested for You" recommendations.

### Input Signals

* Mutual followers
* Shared interests
* Similar engagement patterns
* Existing network structure

### Output

Recommended accounts to follow.

### Objective

Increase graph density and platform retention.

---

# 3. Platform Dynamics

Platform dynamics emerge from the interaction of users, content, social networks, and recommendation systems.

---

## 3.1 Attention Allocation

Users possess a finite attention budget.

For user i:

```math
A_i(t)
```

represents available attention at time t.

Attention is distributed among:

* Feed browsing
* Profile exploration
* Search
* Explore page
* Direct messaging

### Effects

* Exposure opportunities
* Engagement probability
* Session duration

---

## 3.2 Engagement Feedback Loops

Content ranking depends on engagement.

```text
Exposure
    ↓
Engagement
    ↓
Higher Ranking
    ↓
More Exposure
```

### Consequences

* Rich-get-richer dynamics
* Popularity concentration
* Unequal visibility distribution

---

## 3.3 Network Growth

The follower graph evolves continuously.

### Drivers

* Recommendations
* Social influence
* External popularity

### Example Model

```math
P(follow_i) ∝ degree_i^α
```

where:

* degree_i = current number of followers
* α = preferential attachment parameter

### Consequences

* Emergence of influencers
* Heavy-tailed follower distributions

---

## 3.4 Content Diffusion

Content spreads through user exposure and interactions.

```text
Post
 ↓
Initial Exposure
 ↓
Engagement
 ↓
Algorithmic Amplification
 ↓
Broad Diffusion
```

### Diffusion Mechanisms

* Feed ranking
* Explore recommendation
* Direct sharing

---

## 3.5 Creator Competition

Content creators compete for:

* Attention
* Followers
* Engagement

### Creator State Variables

* Audience size
* Posting frequency
* Engagement rate
* Content quality

### Consequences

* Content specialization
* Strategic posting behavior
* Visibility inequality

---

## 3.6 Social Influence

Users influence each other's behavior.

### Influenced Behaviors

* Following decisions
* Content engagement
* Topic adoption

### Modeling Approaches

* Threshold models
* Independent cascade models
* Opinion dynamics models

---

## 3.7 Trend Formation

Trends emerge from collective attention.

### Trend Sources

* Hashtags
* Visual styles
* Memes
* Topics

### Lifecycle

```text
Innovation
 ↓
Early Adoption
 ↓
Algorithmic Amplification
 ↓
Mass Adoption
 ↓
Decline
```

---

## 3.8 Content Lifecycle

Each content item follows a lifecycle.

```text
Creation
 ↓
Initial Exposure
 ↓
Engagement Accumulation
 ↓
Peak Visibility
 ↓
Decay
```

### Typical Metrics

* Reach
* Impressions
* Engagement rate
* Lifetime

---

## 3.9 User Retention Dynamics

Retention is influenced by:

* Content relevance
* Social connections
* Satisfaction
* Novelty

For user i:

```math
R_i(t)
```

represents retention probability at time t.

### Platform Objective

Maximize:

* Daily active users
* Session duration
* Return probability

---

## 3.10 Moderation Dynamics

Content visibility may be modified through moderation.

### Moderation Actions

* Downranking
* Removal
* Fact-checking
* Visibility limitation

### Effects

* Reduced diffusion
* Altered recommendation probabilities
* Changes in user behavior

---

# 4. Formal Representation

At time t:

```math
Platform_t = (U_t, G_t, C_t, R_t)
```

where:

* U_t = user states
* G_t = social graph
* C_t = content ecosystem
* R_t = recommendation systems

The platform evolves according to:

```math
(U_{t+1}, G_{t+1}, C_{t+1})
=
F(U_t, G_t, C_t, R_t)
```

where F represents the combined effects of user behavior, recommendation systems, and platform dynamics.
