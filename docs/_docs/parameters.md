---
title: "Parameters"
subtitle: "Every setting of a run, with its meaning, its values and its default."
goal: "Find a setting, know what it does and which file holds it."
time: "reference"
tabs: false
---

A run is configured by two JSON files in the experiment folder, plus the population.

<div class="ys-cols2">
<div><h3>1 · Server</h3><p><code>server_config.json</code>: name, clients needed, timeout, database, annotations and logs of the orchestrator.</p></div>
<div><h3>2 · Client</h3><p><code>client_config.json</code>: the simulation (time, images, annotations, topics, opinions, lifecycle, actions, activity), the language and vision models, stress and reward, logs.</p></div>
<div><h3>3 · Population</h3><p><code>agents.json</code>: who the agents are. See <a href="{{ site.baseurl }}/agents/">Agents and population</a>.</p></div>
</div>

Anything not written takes its default, so a file lists only what you change.

<div class="ys-params" data-src="{{ site.baseurl }}/assets/data/parameters.json"><noscript>Enable JavaScript to browse the parameters, or read <a href="https://github.com/YSocialTwin/YPhotoSharing/blob/main/docs/configuration.md">docs/configuration.md</a>.</noscript></div>

## Where to next

- [Configuration]({{ site.baseurl }}/configuration/)
- [Database schema]({{ site.baseurl }}/database-schema/)
