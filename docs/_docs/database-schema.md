---
title: "Database schema"
subtitle: "The tables of a YPhotoSharing run, ready for SQL, pandas or the admin analytics."
goal: "Find a table, read its columns and see how it links to the others."
time: "reference"
tabs: false
---

Everything that happens in a run ends up in one SQLite database (`yphotosharing.db`, configured by `database.sqlite.filename`). The server creates it; YSocial only reads it.

<div class="ys-cols2">
<div><h3>Time axis</h3><p><code>rounds</code> has one row per simulated hour (<code>day</code>, <code>hour</code>); other tables point to it with <code>round</code> or <code>round_id</code>.</p></div>
<div><h3>Soft removal</h3><p>Photos and comments are never erased: <code>is_removed</code> or <code>deleted_at</code> flag them, and moderation writes <code>moderation_events</code>.</p></div>
<div><h3>Shared tables</h3><p><code>user_mgmt</code>, <code>stress_reward</code>, <code>user_opinions</code>, <code>memory_*</code> and <code>post_*</code> annotations follow the names of the other platforms.</p></div>
</div>

<div class="ys-schema" data-src="{{ site.baseurl }}/assets/data/schema.json" data-pre="{{ site.baseurl }}/"><noscript>Enable JavaScript to browse the schema, or read <code>YPhotoSharing/YServer/classes/models.py</code>.</noscript></div>

## Three queries to start

Photos and engagement per author:

```sql
SELECT u.username, COUNT(p.id) AS photos,
       SUM(p.num_likes) AS likes, SUM(p.num_comments) AS comments, SUM(p.num_shares) AS shares
FROM photos p JOIN user_mgmt u ON u.id = p.user_id
WHERE p.is_removed = 0
GROUP BY u.id ORDER BY likes DESC LIMIT 10;
```

The current follow graph:

```sql
SELECT follower_id, user_id FROM follow WHERE action = 'follow';
```

What moderation did, by action and content:

```sql
SELECT content_type, action_taken, COUNT(*) AS n, AVG(confidence) AS avg_confidence
FROM moderation_events GROUP BY content_type, action_taken;
```

## Where to next

- [Logs, annotations and export]({{ site.baseurl }}/analysis/)
