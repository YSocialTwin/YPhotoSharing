import asyncio

from YPhotoSharing.YClient.actions.post_photo import post_photo
from YPhotoSharing.YClient.simulation.bootstrap import normalize_agent_config


class _RemoteMethod:
    def __init__(self, value):
        self.value = value
        self.calls = []

    async def remote(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.value


class _FailingRemoteMethod:
    def __init__(self, message):
        self.message = message
        self.calls = []

    async def remote(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError(self.message)


class _FakeServer:
    def __init__(self):
        self.get_following = _RemoteMethod([])
        self.get_user = _RemoteMethod({"username": "alice"})
        self.post_photo = _RemoteMethod("photo-123")


class _FailingLLM:
    def __init__(self):
        self.generate_caption = _FailingRemoteMethod("LLM should not be called")
        self.extract_emotion = _FailingRemoteMethod("LLM should not be called")
        self.extract_sentiment = _FailingRemoteMethod("LLM should not be called")


def test_rule_based_user_type_disables_llm_flag():
    agent = normalize_agent_config(
        {
            "id": "user-1",
            "username": "rule_agent",
            "user_type": "rule_based",
        },
        simulation_config={},
    )

    assert agent["llm"] is False
    assert agent["user_type"] == "rule_based"


def test_rule_based_post_photo_uses_deterministic_caption_without_llm():
    server = _FakeServer()
    llm_service = _FailingLLM()

    photo_id = asyncio.run(
        post_photo(
            server=server,
            llm_service=llm_service,
            user_id="user-1",
            cluster_id=0,
            round_id="round-1",
            day=0,
            slot=0,
            topic="travel",
            agent_attrs={
                "llm": False,
                "username": "rule_agent",
                "enable_emotion_annotation": False,
                "enable_sentiment": False,
            },
            image_gen_service=None,
        )
    )

    assert photo_id == "photo-123"
    assert len(llm_service.generate_caption.calls) == 0
    assert len(llm_service.extract_emotion.calls) == 0
    assert len(llm_service.extract_sentiment.calls) == 0
