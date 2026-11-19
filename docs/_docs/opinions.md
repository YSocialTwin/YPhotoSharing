---
title: "Opinion dynamics"
subtitle: "Bounded confidence or a Likert evaluation, on the topics of the photos an agent comments on."
goal: "Choose an opinion model and read what it records."
time: "10 minutes"
---

## Two models

With `simulation.opinion_dynamics.enabled`, agents hold an opinion in [0, 1] on each topic in `discussion_topics`. When an agent replies to or comments on a photo, the author's opinion is the signal and the opinion is updated with the model in `model_name`:

- **`bounded_confidence`** (continuous): with `epsilon`, `mu`, `theta` and `cold_start` in `opinion_dynamics.parameters`. If |y − x| ≤ epsilon the reader moves x ← x + mu (y − x); otherwise it ignores the message or, when theta is not 0, steps away by theta.
- **`llm_evaluation`** (discrete): the model places the post on a Likert scale (`likert_scale`, five points by default, from strongly disagree to strongly agree) and the agent moves one step; `opinion_groups` maps each label to a score range, and `evaluation_scope` says whether only the interlocutor is considered.

{% include lab.html name="opinions" %}

## What is recorded

`user_opinions` keeps the latest opinion per user, topic and round; `opinion_paths` keeps each transition with the model, the source and target labels and the direction (towards, away or none), the post and the actor, so polarisation can be traced to the interactions that caused it.

## Where to next

- [Stress and reward]({{ site.baseurl }}/stress/)
- [Parameters]({{ site.baseurl }}/parameters/)
