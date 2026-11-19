---
title: "Stress and reward"
subtitle: "How reactions, comments, shares and reports move the mood of a creator."
goal: "Follow an event from the delta table to the stored stress and reward."
time: "15 minutes"
---

## The loop

With `stress_reward.enabled`, the actions that others direct at a creator are **events**. When an agent reacts, comments, shares or reports, the client computes the deltas for the **target** and writes them to the `stress_reward` table. Two variables, **stress** and **reward**, live in [0, 1]. The deltas come from an event table, are scaled by the context, and are damped by each other.

| Event | Δ stress | Δ reward |
|---|---|---|
| reaction: like | −0.005 | +0.03 |
| reaction: dislike | +0.03 | −0.02 |
| comment: positive | −0.02 | +0.07 |
| comment: neutral | 0 | +0.01 |
| comment: critical | +0.03 | −0.01 |
| comment: hostile | +0.10 | −0.05 |
| comment: supportive | −0.05 | +0.08 |
| share: positive | −0.01 | +0.08 |
| share: hostile | +0.12 | −0.06 |
| report: mass report | +0.06 | −0.03 |

Reactions are multiplied by ln(1 + volume); hostile comments by directness and public exposure; shares and reports by public exposure (and reports by importance). The **coupling**: a rise of stress is multiplied by 1 − alpha × reward (alpha 0.30) and a rise of reward by 1 − beta × stress (beta 0.20). The tone of a comment comes from its sentiment and a few keywords.

{% include lab.html name="stress" %}

## State and churn

The current state is **replayed** from the `stress_reward` rows of the last `backward_rounds` (24) rounds. The module also offers a churn probability, sigmoid((stress_weight × stress − reward_weight × reward + bias) ÷ temperature) within [min_probability, max_probability] (defaults 2, 1, −1.8, 0.3, 0 and 0.95), but the churn that actually removes agents in a run is the satisfaction and inactivity mechanism of [Churn and new users]({{ site.baseurl }}/lifecycle/). Moderation also adds stress to the user (`stress_level`) directly.

The deltas are defaults, not empirically calibrated. Tune them under `stress_reward.system.events`.

## Where to next

- [Churn and new users]({{ site.baseurl }}/lifecycle/)
- [Parameters]({{ site.baseurl }}/parameters/)
