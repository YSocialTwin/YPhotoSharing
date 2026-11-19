---
title: "Agents and population"
subtitle: "Personas, archetypes, activity, privacy and creator tiers."
goal: "Describe the agents of a run and know which fields change their behaviour."
time: "10 minutes"
---

## The population file

`agents.json` follows the YSimulator layout: an `agents` array and an optional `generation_config`. An agent has the usual demographic and personality fields (`age`, `gender`, `nationality`, `education_level`, `profession`, `leaning`, the Big Five `oe co ex ag ne`, `language`), `interests`, initial `opinions`, `stubborn_topics`, free `custom_features`, and the platform fields below. The client builds the language-model **persona** from the whole record, so any `custom_features` you add can influence what the agent writes.

| Field | What it does |
|---|---|
| `user_type` | `llm` (prompt-driven) or `rule_based` (deterministic captions and actions) |
| `archetype` | `broadcaster`, `explorer` or `validator`: multiplies some action weights ([What agents do]({{ site.baseurl }}/actions/)) |
| `activity_profile` | name of an hourly profile (`high`, `medium`, `low`...): the agent acts exactly in those hours |
| `daily_activity_level` | 1–5; without a profile it scales the hourly probability; 0 means never |
| `round_actions` | upper bound of actions attempted in one active hour |
| `attention_budget` | attention available per hour (default 100) |
| `recsys_type` | a coarse persona cluster, used by Explore as a cheap collaborative-filtering bias |
| `is_private` | the account needs approval to be followed |
| `is_page` | a page: one action per active hour |
| `photo_sharing.story_visibility` | `public`, `followers` or `private` |
| `photo_sharing.creator_tier` | `standard`, `pro`, `influencer`...: strengthens self-presentation in prompts |
| `photo_sharing.favorite_filters`, `cover_image` | flavour for captions and the profile |

{% include shot.html file="profile" caption="A profile in the platform pages: bio, photos and the follower counts." %}

## Where agents come from

The population is loaded when the client starts and written to the database. With `simulation.agents.new_agents` enabled, further agents are cloned from existing records during the run ([Churn and new users]({{ site.baseurl }}/lifecycle/)). Pages and people are accounts too: a page gets one action per active hour, a person (`user_type = human`) is created through the gateway.

{% include shot.html file="admin-clients" caption="Creating a client in the admin panel: the population, the model and the simulation parameters." %}

## Where to next

- [What agents do]({{ site.baseurl }}/actions/)
- [Follow graph and privacy]({{ site.baseurl }}/network/)
