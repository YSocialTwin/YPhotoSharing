#!/usr/bin/env python3
"""Write docs/assets/data/schema.json (the data of the page "Database schema") from the models of the runtime.

``python scripts/make_schema_data.py``           rewrite the file
``python scripts/make_schema_data.py --check``   exit 1 when the file is not up to date

Tables, columns, types, keys, foreign keys and constraints are read from the SQLAlchemy models, so they cannot drift.
The descriptions are in this file: ``NOTES`` for tables, ``COLUMNS`` (by name, for every table) and ``TABLE_COLUMNS``
(one table only).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from YPhotoSharing.YServer.classes import models  # noqa: E402

OUTPUT = ROOT / "docs" / "assets" / "data" / "schema.json"

GROUPS = [
    ("run", "The run and its clock", "La run e il suo orologio", ["rounds", "analytics_snapshots"]),
    ("people", "Accounts and the follow graph", "Account e grafo dei follow", ["user_mgmt", "follow", "follow_requests"]),
    ("content", "Photos, stories and comments", "Foto, storie e commenti", ["photos", "stories", "story_views", "comments", "saved_photos", "mentions", "messages", "direct_messages"]),
    ("reactions", "Reactions", "Reazioni", ["reactions", "emotions"]),
    ("feeds", "Feeds, hashtags and trends", "Feed, hashtag e tendenze", ["recommendations", "hashtags", "photo_hashtags", "trending_hashtags", "photo_topics", "interests", "user_interest"]),
    ("annotations", "Annotations", "Annotazioni", ["photo_emotions", "post_emotions", "post_sentiment", "post_toxicity"]),
    ("moderation", "Moderation", "Moderazione", ["reported", "moderation_events"]),
    ("opinions", "Opinions", "Opinioni", ["user_opinions", "opinion_paths"]),
    ("behaviour", "Stress and reward", "Stress e ricompensa", ["stress_reward"]),
    ("memory", "Agent memory", "Memoria degli agenti", ["memory_interaction_events", "memory_social_cards"]),
]

#: page of the site that explains the table (id of a file in _docs/)
DOCS = {
    "rounds": "how-it-works", "analytics_snapshots": "analysis",
    "user_mgmt": "agents", "follow": "network", "follow_requests": "network",
    "photos": "content", "stories": "content", "story_views": "content", "comments": "content", "saved_photos": "actions", "mentions": "content",
    "messages": "actions", "direct_messages": "actions",
    "reactions": "actions", "emotions": "content",
    "recommendations": "feeds", "hashtags": "feeds", "photo_hashtags": "feeds", "trending_hashtags": "feeds", "photo_topics": "feeds",
    "interests": "agents", "user_interest": "agents",
    "photo_emotions": "analysis", "post_emotions": "analysis", "post_sentiment": "analysis", "post_toxicity": "analysis",
    "reported": "moderation", "moderation_events": "moderation",
    "user_opinions": "opinions", "opinion_paths": "opinions",
    "stress_reward": "stress",
    "memory_interaction_events": "agents", "memory_social_cards": "agents",
}

PAGES = {
    "how-it-works": ("How it works", "Come funziona"), "agents": ("Agents and population", "Agenti e popolazione"),
    "content": ("Photos, stories and comments", "Foto, storie e commenti"), "actions": ("What agents do", "Che cosa fanno gli agenti"),
    "network": ("The follow graph", "Il grafo dei follow"), "feeds": ("Feeds, hashtags and trends", "Feed, hashtag e tendenze"),
    "moderation": ("Moderation", "Moderazione"), "opinions": ("Opinion dynamics", "Dinamica delle opinioni"),
    "stress": ("Stress, reward and satisfaction", "Stress, ricompensa e soddisfazione"), "analysis": ("Export and analysis", "Export e analisi"),
}

NOTES = {
    "rounds": "The time axis: one row per round (one simulated hour), with day and hour; every `round` column points here.",
    "analytics_snapshots": "Hourly totals (active users, photos, reactions, comments, follows) written at the end of each round.",
    "user_mgmt": "One row per account (agent, page or human): persona, Big Five, archetype, activity profile, profile data, influence and satisfaction scores, churn flag.",
    "follow": "Every follow and unfollow as an event: one row per pair, with the action and the round of the last change.",
    "follow_requests": "Requests to follow a private account, with their status.",
    "photos": "Every published photo: author, caption, image, filter, location, counters, scores and the rounds of creation and removal.",
    "stories": "Stories (24 hours): media, sticker, caption, view counter and expiry.",
    "story_views": "Who watched which story, and when.",
    "comments": "Comments and replies to photos, with sentiment, likes and soft-delete flags.",
    "saved_photos": "Photos saved by an account.",
    "mentions": "Accounts mentioned in a photo caption or comment.",
    "messages": "Legacy message table (kept for compatibility).",
    "direct_messages": "Private messages between two accounts, optionally attaching a photo.",
    "reactions": "The reaction of an account to a photo (like or an emotion), one row each.",
    "emotions": "Catalogue of the emotions that can be attached to reactions and photos.",
    "recommendations": "The list of photos the recommender offered to an account in a round.",
    "hashtags": "Distinct hashtags of the run.",
    "photo_hashtags": "Links a photo to its hashtags.",
    "trending_hashtags": "Ranking of hashtags per round, with the number of photos that used them.",
    "photo_topics": "Topics assigned to a photo, with the confidence of the assignment.",
    "interests": "Catalogue of interests.",
    "user_interest": "Interests of an account, with the round in which they were recorded.",
    "photo_emotions": "Dominant visual emotion of a photo (annotation), with score and viral score.",
    "post_emotions": "Emotions attached to a post by the annotators.",
    "post_sentiment": "Sentiment (negative, positive, neutral, compound) of posts, comments and reactions.",
    "post_toxicity": "Perspective API scores of a post or comment.",
    "reported": "Reports filed by accounts against a photo or comment, with the reason.",
    "moderation_events": "Decisions of the moderation stub: the action taken, reason and confidence.",
    "user_opinions": "Opinion of an account on a topic in a round (score and label), per model.",
    "opinion_paths": "Every change of opinion: from, to, direction, the post that caused it and the model.",
    "stress_reward": "Variations of stress and reward of each account, with the event that caused them and the round.",
    "memory_interaction_events": "Interactions recorded for the agent memory (only with memory on).",
    "memory_social_cards": "Social cards of the agent memory: affinity, conflict, humour and trust towards another account (only with memory on).",
}

COLUMNS = {
    "id": "Primary key.", "user_id": "Account concerned (user_mgmt.id).", "photo_id": "Photo concerned (photos.id).",
    "round": "Round in which it happened (rounds.id).", "round_id": "Round in which it happened (rounds.id).",
    "created_at": "When the row was written.", "follower_id": "Account that follows (user_mgmt.id).",
    "emotion_id": "Emotion (emotions.id).", "topic_id": "Topic concerned.", "hashtag_id": "Hashtag (hashtags.id).",
    "sender_id": "Account that sends.", "recipient_id": "Account that receives.", "reporter_id": "Account that reported.",
    "content_id": "Photo or comment concerned.", "content_type": "photo or comment.", "reason": "Reason given.",
    "sentiment_score": "Sentiment score of the text.", "deleted_at": "When it was soft-deleted; empty while live.",
    "run_id": "Run it belongs to.", "model_name": "Opinion model that wrote the row.", "topic": "Topic label.",
    "interest_id": "Interest (interests.iid).", "post_id": "Post concerned.", "uid": "Account (user_mgmt.id).",
}

TABLE_COLUMNS = {
    "rounds": {"day": "Simulated day.", "hour": "Hour of the day (0-23)."},
    "analytics_snapshots": {"active_users": "Accounts active in the round.", "total_photos": "Photos in the run so far.", "total_reactions": "Reactions so far.", "total_comments": "Comments so far.", "total_follows": "Follows so far."},
    "user_mgmt": {"username": "Unique name.", "email": "Address of the account.", "password": "Password of a human account (hashed).", "user_type": "Kind of model that drives the agent.", "leaning": "Political leaning.", "age": "Age.", "oe": "Big Five: openness.", "co": "Big Five: conscientiousness.", "ex": "Big Five: extraversion.", "ag": "Big Five: agreeableness.", "ne": "Big Five: neuroticism.", "recsys_type": "Recommender of the content feed.", "frecsys_type": "Recommender of the follow suggestions.", "language": "Language.", "owner": "Account that owns a page.", "education_level": "Education.", "joined_on": "Round of arrival.", "round_actions": "Actions per round (legacy setting).", "gender": "Gender.", "nationality": "Nationality.", "toxicity": "Toxicity level of the persona.", "is_page": "1 for a page.", "left_on": "Round of departure; empty while active.", "daily_activity_level": "Level 1-5 that scales the hourly probability of acting.", "profession": "Profession.", "activity_profile": "Named profile of active hours.", "archetype": "broadcaster, explorer or validator.", "bio": "Profile biography.", "website": "Profile website.", "profile_picture_url": "Profile picture.", "cover_image": "Cover image.", "is_private": "1 when follows need approval.", "is_verified": "1 for a verified account.", "last_active_day": "Last day with an action (used for inactivity churn).", "influence_score": "Network influence score.", "broker_score": "Network brokerage score.", "stress_level": "Current stress.", "is_shadow_banned": "1 when the moderation reduced the reach of the account.", "satisfaction_score": "Satisfaction that drives churn.", "is_churned": "1 once the account has left."},
    "follow": {"user_id": "Account that is followed.", "follower_id": "Account that follows.", "action": "follow or unfollow (the last action of the pair)."},
    "follow_requests": {"user_id": "Private account asked.", "status": "pending, accepted or rejected."},
    "photos": {"user_id": "Author.", "image_url": "Image of the photo.", "thumbnail_url": "Thumbnail.", "caption": "Caption.", "alt_text": "Alternative text.", "filter_name": "Filter applied.", "location_name": "Place.", "latitude": "Latitude.", "longitude": "Longitude.", "is_carousel": "1 for a carousel.", "carousel_index": "Position in the carousel.", "parent_photo_id": "First photo of the carousel.", "num_likes": "Reactions counter.", "num_comments": "Comments counter.", "num_shares": "Shares counter.", "is_sponsored": "1 for a sponsored post.", "embedding": "Embedding of the photo.", "aesthetic_score": "Aesthetic score.", "viral_score": "Score used for virality.", "is_removed": "1 when the moderation removed it.", "media_url": "Media URL."},
    "stories": {"media_url": "Media.", "media_type": "image or video.", "duration_seconds": "Length shown.", "sticker_type": "Kind of sticker.", "sticker_data": "Sticker data (JSON).", "caption": "Caption.", "title": "Title.", "description": "Description.", "image_urls": "Images (JSON).", "view_count": "Views.", "expires_at": "When it expires."},
    "story_views": {"story_id": "Story watched.", "viewer_id": "Account that watched.", "viewed_at": "When."},
    "comments": {"parent_comment_id": "Comment it answers.", "body": "Text.", "num_likes": "Likes.", "is_deleted": "1 if deleted by the author.", "timestamp": "Timestamp.", "is_removed": "1 if removed by the moderation."},
    "saved_photos": {},
    "mentions": {"comment_id": "Comment containing the mention.", "user_id": "Account mentioned."},
    "messages": {"content": "Text.", "photo_id": "Attached photo."},
    "direct_messages": {"body": "Text.", "photo_id": "Attached photo.", "is_read": "1 once read."},
    "reactions": {"reaction_type": "like or an emotion.", "emotion_id": "Emotion attached, if any."},
    "emotions": {"emotion": "Name.", "icon": "Icon."},
    "recommendations": {"photo_ids": "Photos offered, in order (JSON)."},
    "hashtags": {"hashtag": "The hashtag."},
    "trending_hashtags": {"photo_count": "Photos that used it in the window.", "rank": "Position in the ranking."},
    "photo_topics": {"confidence": "Confidence of the assignment."},
    "interests": {"iid": "Primary key.", "interest": "Name."},
    "photo_emotions": {"score": "Score of the emotion.", "viral_score": "Viral score."},
    "post_sentiment": {"neg": "Negative.", "pos": "Positive.", "neu": "Neutral.", "compound": "Compound score.", "sentiment_parent": "Sentiment of the parent.", "is_post": "1 for a post.", "is_comment": "1 for a comment.", "is_reaction": "1 for a reaction."},
    "post_toxicity": {"toxicity": "Toxicity.", "severe_toxicity": "Severe toxicity.", "identity_attack": "Identity attack.", "insult": "Insult.", "profanity": "Profanity.", "threat": "Threat.", "sexually_explicit": "Sexually explicit.", "flirtation": "Flirtation."},
    "moderation_events": {"action_taken": "Action decided.", "confidence": "Confidence of the decision."},
    "user_opinions": {"opinion_score": "Opinion in [0, 1].", "opinion_label": "Class of the opinion."},
    "opinion_paths": {"evaluation_scope": "Messages considered.", "source_score": "Score before.", "source_label": "Class before.", "target_score": "Score after.", "target_label": "Class after.", "transition": "From and to.", "direction": "Direction of the change.", "parent_post_id": "Post that was answered.", "actor_user_id": "Account that wrote the message.", "payload_json": "Details (JSON)."},
    "stress_reward": {"variable": "stress or reward.", "value": "Variation.", "type": "Kind of event.", "action": "Event that caused it.", "tid": "Round."},
    "memory_interaction_events": {"actor_user_id": "Who acted.", "target_user_id": "Who was addressed.", "target_photo_id": "Photo addressed.", "actor_photo_id": "Photo of the actor.", "event_type": "Kind of interaction.", "relation_label": "Relationship label.", "tone_label": "Tone.", "topics_json": "Topics (JSON).", "salient_claim": "Main claim.", "event_text": "Text of the event.", "weight": "Weight.", "importance": "Importance.", "last_accessed_round": "Last recall.", "access_count": "Recalls."},
    "memory_social_cards": {"agent_user_id": "Owner of the card.", "other_user_id": "Other person.", "affinity": "Affinity.", "conflict": "Conflict.", "humor": "Humour.", "trust": "Trust.", "last_relation_label": "Last label.", "last_round_id": "Last round.", "last_updated_round": "Round of the update.", "event_count": "Events summarised.", "summary_text": "Summary.", "evidence_tail_json": "Recent evidence (JSON)."},
}


def rules(table) -> list:
    out = []
    for c in table.constraints:
        if isinstance(c, CheckConstraint):
            out.append(f"check {c.name}: {c.sqltext}")
        elif isinstance(c, UniqueConstraint):
            out.append(f"unique {c.name}: ({', '.join(col.name for col in c.columns)})")
    for idx in sorted(table.indexes, key=lambda i: i.name or ""):
        if idx.unique:
            out.append(f"unique index {idx.name}: ({', '.join(c.name for c in idx.columns)})")
    return sorted(out)


def build() -> dict:
    tables = {}
    for name, t in sorted(models.Base.metadata.tables.items()):
        cols = []
        for col in t.columns:
            fks = sorted(f.target_fullname for f in col.foreign_keys)
            default = None
            if col.default is not None and getattr(col.default, "arg", None) is not None and not callable(col.default.arg):
                default = str(col.default.arg)
            desc = TABLE_COLUMNS.get(name, {}).get(col.name) or COLUMNS.get(col.name, "")
            cols.append({"name": col.name, "type": str(col.type), "pk": bool(col.primary_key), "null": bool(col.nullable) and not col.primary_key,
                         "default": default, "fk": fks[0] if fks else None, "desc": desc})
        tables[name] = {"note": NOTES.get(name, ""), "doc": DOCS.get(name), "columns": cols, "rules": rules(t)}
    placed = {t for _, _, _, ts in GROUPS for t in ts}
    groups = [{"id": g, "title": en, "title_it": it, "tables": [t for t in ts if t in tables]} for g, en, it, ts in GROUPS]
    rest = [t for t in tables if t not in placed]
    if rest:
        groups[-1]["tables"] += rest
    docs = {k: {"en": v[0], "it": v[1]} for k, v in PAGES.items()}
    return {"schema_version": None, "groups": groups, "docs": docs, "tables": tables}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    if args.check:
        return 0 if OUTPUT.is_file() and OUTPUT.read_text(encoding="utf-8") == text else 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
