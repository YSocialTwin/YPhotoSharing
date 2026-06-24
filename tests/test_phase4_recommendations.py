import tempfile
from pathlib import Path

from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware
from YPhotoSharing.YServer.classes.models import Photo
from YPhotoSharing.YServer.recsys.explore_recsys import ExploreRecsys
from YPhotoSharing.YServer.recsys.feed_ranking_service import FeedRankingService


def _make_db(tmpdir: str) -> DatabaseMiddleware:
    return DatabaseMiddleware(
        {"type": "sqlite", "sqlite": {"filename": "recsys.db"}},
        config_path=Path(tmpdir),
    )


def _set_photo_state(db: DatabaseMiddleware, photo_id: str, **values):
    with db.session_scope() as session:
        photo = session.query(Photo).filter_by(id=photo_id).one()
        for key, value in values.items():
            setattr(photo, key, value)


def test_home_feed_ranking_uses_topic_overlap_and_annotations():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _make_db(tmpdir)
        round_id = db.get_or_create_round(0, 0)
        author_id = db.create_user({"username": "author", "password": "secret", "recsys_type": 1})
        follower_id = db.create_user({"username": "follower", "password": "secret", "recsys_type": 1})
        travel_id = db.get_or_create_interest("travel")
        food_id = db.get_or_create_interest("food")
        db.set_user_interests(follower_id, [travel_id], round_id)
        db.add_follow(author_id, follower_id, round_id)

        photo_positive = db.create_photo(
            {
                "user_id": author_id,
                "round": round_id,
                "image_url": "https://example.com/a.jpg",
                "caption": "Shared morning light",
                "topics": ["travel"],
            }
        )
        photo_negative = db.create_photo(
            {
                "user_id": author_id,
                "round": round_id,
                "image_url": "https://example.com/b.jpg",
                "caption": "Shared morning light",
                "topics": ["food"],
            }
        )

        db.add_photo_emotion(photo_positive, "joy")
        db.add_photo_emotion(photo_negative, "sadness")
        db.update_photo_sentiment(photo_positive, 1.0)
        db.update_photo_sentiment(photo_negative, -1.0)
        _set_photo_state(db, photo_positive, viral_score=0.2, aesthetic_score=0.6, num_likes=0, num_comments=0, num_shares=0)
        _set_photo_state(db, photo_negative, viral_score=0.2, aesthetic_score=0.6, num_likes=0, num_comments=0, num_shares=0)

        feed = db.get_home_feed(follower_id, limit=2)
        assert [item["id"] for item in feed][:2] == [photo_positive, photo_negative]


def test_explore_ranking_uses_topic_overlap_in_addition_to_caption_similarity(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _make_db(tmpdir)
        round_id = db.get_or_create_round(0, 0)
        user_id = db.create_user({"username": "viewer", "password": "secret", "recsys_type": 2})
        author_id = db.create_user({"username": "creator", "password": "secret", "recsys_type": 2})
        travel_id = db.get_or_create_interest("travel")
        food_id = db.get_or_create_interest("food")
        db.set_user_interests(user_id, [travel_id], round_id)

        photo_travel = db.create_photo(
            {
                "user_id": author_id,
                "round": round_id,
                "image_url": "https://example.com/c.jpg",
                "caption": "a beautiful post",
                "topics": ["travel"],
            }
        )
        photo_food = db.create_photo(
            {
                "user_id": author_id,
                "round": round_id,
                "image_url": "https://example.com/d.jpg",
                "caption": "a beautiful post",
                "topics": ["food"],
            }
        )

        _set_photo_state(db, photo_travel, viral_score=0.2, sentiment_score=1.0)
        _set_photo_state(db, photo_food, viral_score=0.2, sentiment_score=1.0)

        with db.session_scope() as session:
            candidates = [
                {c.name: getattr(p, c.name) for c in p.__table__.columns}
                for p in session.query(Photo).filter(Photo.id.in_([photo_travel, photo_food])).all()
            ]

        monkeypatch.setattr("random.uniform", lambda *args, **kwargs: 0.0)
        explorer = ExploreRecsys()
        with db.session_scope() as session:
            ranked = explorer.evaluate(user_id, round_id, session, candidates, limit=2)

        assert [item["id"] for item in ranked][:2] == [photo_travel, photo_food]
