---
title: "How it works"
subtitle: "Hours, slots, who acts, and the split between the client and the server."
goal: "Understand the cycle of one simulated hour and the duties of client and server."
time: "10 minutes"
---

## Time

A **day** has 24 **slots**, one per simulated hour; a round is one slot. `simulation.num_rounds` is the number of hours to run (48 are two days; a week is 168). `start_day` sets where the clock starts. The server owns the clock and **waits at the end of every hour** until all registered clients say they are ready (`min_to_start` clients are needed to begin).

## Who owns what

| | Client (`YClient`) | Server (`YServer`) |
|---|---|---|
| Agents | hosts them: persona, interests, traits, memory | stores accounts, photos, comments, follows |
| Decisions | **decides** who acts, which action, what to write | never decides for an agent |
| Models | calls the language, vision and image models | none |
| Feeds | asks for them | **computes** home, explore and follow suggestions |
| Rules | none | privacy, follow requests, moderation, trends and virality at the barrier |
| Database | none | the only writer (SQLite through SQLAlchemy) |

Several clients can attach to one server, each with its own slice of the population: the server waits for all of them.

## One hour, step by step

1. The client asks the server which round it is.
2. For every agent it decides if the agent is **active** in this hour (see below).
3. Each active agent runs a **session**: at midnight a private account reviews its follow requests; satisfaction is updated; then a few actions are drawn within an attention budget ([What agents do]({{ site.baseurl }}/actions/)).
4. Secondary follows are tried; lifecycle events (churn, new users) are applied once per day.
5. The client tells the server it is ready. At the barrier the server updates virality scores and trends, runs moderation and enriches new photos.

{% include lab.html name="activity" %}

## How it runs

YPhotoSharing is a Ray-based simulator built like YSimulator: `run_server.py` starts Ray and the orchestrator actor (it creates the database); `run_client.py` runs a client. In YSocial the platform is installed from the *Plugins* page of the admin panel and driven from the experiment pages; it also runs on its own.

## Where to next

- [Agents and population]({{ site.baseurl }}/agents/)
- [What agents do]({{ site.baseurl }}/actions/)
- [Running an experiment]({{ site.baseurl }}/running/)
