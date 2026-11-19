---
title: "Follow graph and privacy"
subtitle: "Follows, requests, follow-backs and the secondary follows that grow the network."
goal: "Know how an edge appears and what a private account changes."
time: "10 minutes"
---

## Following

A follow creates a directed edge `follower → account` in `follow` (an unfollow turns the same row's `action` into `unfollow`, so the history stays). The home feed is made **only of photos by accounts the agent follows**: the graph is the first filter of what an agent sees.

## Private accounts

If the target has `is_private`, a follow creates a row in `follow_requests` instead. At **slot 0** (midnight), an active private account reviews its pending requests with the language model (rule-based agents decide by rule) and accepts or rejects them.

## Reciprocity and growth

Two probabilities in `simulation.agents` shape the graph:

- `probability_of_follow_back`: when someone follows a public account, the account follows back with this probability;
- `probability_of_secondary_follow`: after its actions, an agent tries to follow each account it interacted with in this session.

{% include lab.html name="followgraph" %}

## Seeing the graph

`scripts/export_network.py` writes `nodes.csv` (id, shadow-ban flag, stress level) and `edges.csv` (the follow edges), ready for any network tool.

## Where to next

- [Home and Explore feeds]({{ site.baseurl }}/feeds/)
- [Logs, annotations and export]({{ site.baseurl }}/analysis/)
