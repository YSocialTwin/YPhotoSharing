from pathlib import Path
import tempfile

from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware


def _make_db(tmpdir: str) -> DatabaseMiddleware:
    return DatabaseMiddleware(
        {"type": "sqlite", "sqlite": {"filename": "phase1.db"}},
        config_path=Path(tmpdir),
    )


def test_photo_topics_are_persisted_and_resolved():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _make_db(tmpdir)
        round_id = db.get_or_create_round(0, 0)
        user_id = db.create_user({"username": "alice", "password": "secret"})

        photo_id = db.create_photo(
            {
                "user_id": user_id,
                "round": round_id,
                "image_url": "https://example.com/image.jpg",
                "caption": "A travel photo",
                "topic": "travel",
                "topics": ["travel", "adventure"],
            }
        )

        topic_ids = db.get_photo_topics(photo_id)

        assert len(topic_ids) == 2
        assert db.get_topic_name_from_id(topic_ids[0]) in {"travel", "adventure"}
        assert db.get_topic_name_from_id(topic_ids[1]) in {"travel", "adventure"}


def test_missing_opinion_returns_none():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _make_db(tmpdir)
        db.get_or_create_round(0, 0)
        user_id = db.create_user({"username": "bob", "password": "secret"})

        assert db.get_latest_agent_opinion(user_id, "missing-topic") is None

