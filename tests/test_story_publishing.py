import asyncio
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace

from YPhotoSharing.YClient.actions.post_story import post_story
from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware
from YPhotoSharing.YServer.classes.models import Follow


class AsyncRemoteStub:
    def __init__(self, value):
        self.value = value
        self.calls = []

    async def remote(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.value


def _make_db(tmpdir: str) -> DatabaseMiddleware:
    return DatabaseMiddleware(
        {"type": "sqlite", "sqlite": {"filename": "story.db"}},
        config_path=Path(tmpdir),
    )


def test_post_story_uses_existing_user_photos_and_builds_story_metadata():
    server = SimpleNamespace(
        get_user_photos=AsyncRemoteStub(
            [
                {"id": "photo-1", "image_url": "https://cdn.example/photo-1.jpg"},
                {"id": "photo-2", "media_url": "https://cdn.example/photo-2.jpg"},
                {"id": "photo-3", "url": "https://cdn.example/photo-3.jpg"},
                {"id": "photo-4", "image_url": "https://cdn.example/photo-4.jpg"},
                {"id": "photo-5", "image_url": "https://cdn.example/photo-5.jpg"},
            ]
        ),
        post_story=AsyncRemoteStub("story-1"),
    )
    llm_service = SimpleNamespace(generate_caption=AsyncRemoteStub("A small story about the day"))

    result = asyncio.run(
        post_story(
            server=server,
            llm_service=llm_service,
            user_id="user-1",
            cluster_id=2,
            round_id="round-1",
            day=1,
            slot=8,
            topic="travel",
            agent_attrs={"username": "alice", "llm": True},
        )
    )

    assert result == "story-1"
    story_data = server.post_story.calls[0][0][0]
    assert story_data["user_id"] == "user-1"
    assert story_data["media_url"] == "https://cdn.example/photo-1.jpg"
    assert story_data["media_type"] == "carousel"
    assert json.loads(story_data["image_urls"]) == [
        "https://cdn.example/photo-1.jpg",
        "https://cdn.example/photo-2.jpg",
        "https://cdn.example/photo-3.jpg",
        "https://cdn.example/photo-4.jpg",
        "https://cdn.example/photo-5.jpg",
    ]
    assert story_data["title"]
    assert story_data["description"] == "A small story about the day"


def test_post_story_aborts_when_user_has_no_existing_photos():
    server = SimpleNamespace(get_user_photos=AsyncRemoteStub([]), post_story=AsyncRemoteStub("story-1"))
    llm_service = SimpleNamespace(generate_caption=AsyncRemoteStub("unused"))

    result = asyncio.run(
        post_story(
            server=server,
            llm_service=llm_service,
            user_id="user-1",
            cluster_id=2,
            round_id="round-1",
            day=1,
            slot=8,
            topic="travel",
            agent_attrs={"username": "alice", "llm": True},
        )
    )

    assert result is None
    assert server.post_story.calls == []


def test_story_rows_store_and_return_image_collections():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _make_db(tmpdir)
        author_id = db.create_user({"username": "author", "password": "secret"})
        viewer_id = db.create_user({"username": "viewer", "password": "secret"})
        round_id = db.get_or_create_round(0, 0)

        with db.session_scope() as session:
            session.add(
                Follow(
                    id="follow-1",
                    user_id=author_id,
                    follower_id=viewer_id,
                    action="follow",
                    round=round_id,
                )
            )

        story_id = db.create_story(
            {
                "user_id": author_id,
                "round": round_id,
                "media_url": "https://cdn.example/story-cover.jpg",
                "image_urls": [
                    "https://cdn.example/story-cover.jpg",
                    "https://cdn.example/story-2.jpg",
                ],
                "title": "Weekend recap",
                "description": "A short visual diary from the weekend.",
            }
        )

        stories = db.get_recent_stories(viewer_id, limit=10)
        assert stories and stories[0]["id"] == story_id
        assert stories[0]["title"] == "Weekend recap"
        assert stories[0]["description"] == "A short visual diary from the weekend."
        assert stories[0]["image_urls"] == [
            "https://cdn.example/story-cover.jpg",
            "https://cdn.example/story-2.jpg",
        ]
