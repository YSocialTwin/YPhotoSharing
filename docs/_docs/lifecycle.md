---
title: "Churn and new users"
subtitle: "Agents that lose interest and leave, and new users cloned from the population."
goal: "Understand the two ways an agent leaves and how newcomers appear."
time: "10 minutes"
---

## Satisfaction

Every active turn an agent compares its followers with the previous turn: **+5 for every follower gained, otherwise −1**. Satisfaction lives in [0, 100] and starts at 100; at **10 or less** the account is marked churned (`is_churned`) and the scheduler skips it from then on. A creator who never gains followers leaves after about 90 active turns; a popular one never does.

{% include lab.html name="satisfaction" %}

## Inactivity churn (off by default)

`simulation.agents.churn` adds a pass at the end of every day (slot 23): agents inactive for at least `inactivity_threshold` days are candidates; `churn_percentage` of them are sampled, and each leaves with `churn_probability`. The round is recorded in `left_on`. With `enabled: false` (the default) nothing happens.

## New users (off by default)

`simulation.agents.new_agents`: at the same moment `percentage_new_agents` of the active population (rounded down) get a chance of `probability_new_agents` to spawn a newcomer **cloned from a random existing record** with a new id and username, `joined_on` set to the round and no history. Population growth therefore follows the mix of the existing personas.

## Where to next

- [Stress and reward]({{ site.baseurl }}/stress/)
- [Configuration]({{ site.baseurl }}/configuration/)
