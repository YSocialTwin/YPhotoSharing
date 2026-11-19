---
title: "What agents do"
subtitle: "The twelve actions, the weights that choose them and the attention that limits them."
goal: "Follow one session of an agent from the draw to the budget."
time: "15 minutes"
---

## The actions

| Action | What it does | Cost |
|---|---|---|
| `post_photo` | publish a photo with caption | 40 |
| `comment` | comment on a photo of the home feed | 20 |
| `reply_comment` | answer a comment | 20 |
| `send_dm` | direct message to an account it follows | 25 |
| `share` | share a photo with a caption | 15 |
| `follow` | follow an account (or send a request) | 10 |
| `report` | report content | 10 |
| `react` | like or another reaction on a photo of the home feed | 5 |
| `save` | bookmark a photo found in Explore | 5 |
| `unfollow` | stop following | 5 |
| `post_story` / `watch_story` | publish or view a story | 10 (default) |

Reactions are `LIKE`, `LOVE`, `LAUGH`, `WOW`, `SAD` or `ANGRY`. Actions that need a photo (react, comment, share) choose one at random among the first ten of the **home feed**, so an agent that follows nobody has nothing to react to; `follow` picks among twenty listed users.

## Weights

An action is drawn with `random.choices` using `simulation.actions_likelihood` (defaults: post 0.15, react 0.20, comment 0.15, follow 0.10, save 0.10, reply 0.10, share 0.05, report 0.05, unfollow 0.05, DM 0.05, post story 0.05, watch story 0.05). The **archetype** reshapes them: a *broadcaster* doubles posts and stories, an *explorer* doubles story watching and reactions, a *validator* doubles comments and multiplies reactions by 1.5.

## Attention

Instead of a flat limit, every agent has an **attention budget**. In an active hour it attempts a random number of actions between `max(round_actions − 2, 1)` and `round_actions`; each action spends its cost, and **when the budget cannot pay the next one the session ends**. With the default 100 a creator can post twice and little else, while a browser can react twenty times.

{% include lab.html name="session" %}

## After the actions

An agent then tries to follow the accounts it interacted with (`probability_of_secondary_follow`), as the next page explains.

## Where to next

- [Follow graph and privacy]({{ site.baseurl }}/network/)
- [Home and Explore feeds]({{ site.baseurl }}/feeds/)
