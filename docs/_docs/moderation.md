---
title: "Reports and moderation"
subtitle: "Reports, a toxicity check, removals, warnings and shadow-bans."
goal: "Know what happens to a reported or toxic photo or comment and to its author."
time: "10 minutes"
---

## Reports

The `report` action files a row in `reported` with the content, its type (photo or comment) and a reason. Reports and the content published in the round are examined by the **moderation service** at the end of the round; every decision is a row in `moderation_events` with the action, the reason and a confidence.

## The rules

The service uses a **stub** of a toxicity classifier: each banned keyword (`hate`, `kill`, `die`, `stupid`, `idiot`, `spam`) adds 0.3, up to 1. Perspective API scores can be enabled as an annotation (`enable_toxicity`), but the removal rules use the stub.

| Case | Rule |
|---|---|
| proactive scan, photo caption | score above 0.5 → removed; author warned; at 0.8 or more the author is **shadow-banned** |
| proactive scan, comment | score above 0.5 → removed; author warned |
| reported item | removed when the score is above 0.3 or the reason says spam; author warned |

A **warning** adds 0.2 to the author's `stress_level`, a **shadow-ban** sets `is_shadow_banned` and adds 0.5 (stress is capped at 1). Removed content stays in the database with `is_removed` set.

{% include lab.html name="moderation" %}

## Why a stub

Moderation here is a policy placeholder: it makes removals, warnings and shadow-bans exist in the data so that their effects on exposure, stress and churn can be studied, and it is the place to plug a better classifier.

## Where to next

- [Stress and reward]({{ site.baseurl }}/stress/)
- [Database schema]({{ site.baseurl }}/database-schema/)
