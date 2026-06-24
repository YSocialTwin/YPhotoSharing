import asyncio

from YPhotoSharing.YClient.actions.dynamics_helpers import build_memory_context, record_memory_event
from YPhotoSharing.YClient.actions.post_photo import post_photo
from YPhotoSharing.YClient.simulation.bootstrap import normalize_agent_config


class _RemoteMethod:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def remote(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.result


def test_normalize_agent_config_exposes_annotation_flags():
    config = normalize_agent_config(
        {"id": "user-1"},
        {
            "enable_sentiment": True,
            "enable_emotion_annotation": False,
            "enable_memory_annotations": False,
            "activity_profiles": {"day": [8, 9]},
        },
    )

    assert config["enable_sentiment"] is True
    assert config["enable_emotion_annotation"] is False
    assert config["enable_memory_annotations"] is False
    assert config["activity_profile"] == "day"


def test_post_photo_skips_emotion_annotation_when_disabled():
    class FakeServer:
        def __init__(self):
            self.post_photo = _RemoteMethod("photo-1")
            self.add_photo_emotion = _RemoteMethod(None)
            self.update_photo_sentiment = _RemoteMethod(None)
            self.get_following = _RemoteMethod([])
            self.get_user = _RemoteMethod({"username": "follower"})

    class FakeLlm:
        def __init__(self):
            self.generate_caption = _RemoteMethod("A calm scene")
            self.extract_emotion = _RemoteMethod("joy")
            self.extract_sentiment = _RemoteMethod(1.0)

    server = FakeServer()
    llm = FakeLlm()

    result = asyncio.run(
        post_photo(
            server=server,
            llm_service=llm,
            user_id="user-1",
            cluster_id=0,
            round_id="round-1",
            day=0,
            slot=0,
            topic="travel",
            agent_attrs={"enable_emotion_annotation": False, "enable_sentiment": False},
        )
    )

    assert result == "photo-1"
    assert len(server.add_photo_emotion.calls) == 0
    assert len(llm.extract_emotion.calls) == 0
    assert len(llm.extract_sentiment.calls) == 0


def test_memory_helpers_build_and_persist_events():
    class FakeServer:
        def __init__(self):
            self.get_memory_events = _RemoteMethod(
                [
                    {"other_user_id": "peer-1", "event_type": "liked"},
                    {"other_user_id": "peer-2", "event_type": "commented"},
                ]
            )
            self.add_memory_event = _RemoteMethod(None)

    server = FakeServer()

    memory_context = asyncio.run(
        build_memory_context(
            server,
            run_id="default",
            agent_user_id="user-1",
            other_user_id="peer-2",
            label="Past interactions with this user",
        )
    )
    assert memory_context == "Past interactions with this user: commented"

    asyncio.run(
        record_memory_event(
            server,
            enabled=True,
            event_data={"event_type": "sent_dm"},
        )
    )
    assert len(server.add_memory_event.calls) == 1
