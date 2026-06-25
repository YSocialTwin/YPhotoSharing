from types import SimpleNamespace

from YPhotoSharing.YClient.annotation import normalize_annotation_flags
from YPhotoSharing.YClient.LLM_interactions.llm_service import LLMService
from YPhotoSharing.YClient.text_support.text_annotator import (
    EMOTION_LIST,
    EMOTION_SYSTEM_TEMPLATE,
    EMOTION_USER_TEMPLATE,
    annotate_text,
    build_emotion_prompt,
    prepare_sentiment_data,
    prepare_toxicity_data,
)


def test_annotation_flags_are_parsed_from_simulation_block():
    flags = normalize_annotation_flags(
        {
            "simulation": {
                "enable_sentiment": True,
                "enable_emotion_annotation": False,
                "enable_toxicity": True,
            }
        }
    )

    assert flags.enable_sentiment is True
    assert flags.enable_emotion_annotation is False
    assert flags.enable_toxicity is True


def test_annotate_text_exposes_the_same_annotation_slots(monkeypatch):
    monkeypatch.setattr(
        "YPhotoSharing.YClient.text_support.text_annotator.vader_sentiment",
        lambda text: {"neg": 0.0, "pos": 0.1, "neu": 0.9, "compound": 0.1},
    )
    monkeypatch.setattr(
        "YPhotoSharing.YClient.text_support.text_annotator.toxicity",
        lambda text, api_key: {"TOXICITY": 0.0},
    )
    monkeypatch.setattr("YPhotoSharing.YClient.text_support.text_annotator.ray.get", lambda value: value)

    llm_handle = SimpleNamespace(extract_emotions=SimpleNamespace(remote=lambda text: ["joy"]))
    annotations = annotate_text(
        "hello world",
        enable_sentiment=True,
        enable_emotion_annotation=True,
        enable_toxicity=True,
        llm_handle=llm_handle,
    )

    assert set(annotations) == {"hashtags", "mentions", "sentiment", "emotions", "toxicity"}
    assert annotations["sentiment"] is not None
    assert annotations["emotions"] == ["joy"]
    assert annotations["toxicity"] is not None


def test_prepare_annotation_rows_match_expected_schema():
    sentiment = prepare_sentiment_data(
        post_id="post-1",
        user_id="user-1",
        topic_ids=["topic-1", "topic-2"],
        round_id="round-1",
        sentiment_scores={"neg": 0.1, "pos": 0.2, "neu": 0.7, "compound": 0.3},
        sentiment_parent="0.1",
        is_post=True,
    )
    toxicity = prepare_toxicity_data(
        "post-1",
        {
            "TOXICITY": 0.5,
            "SEVERE_TOXICITY": 0.1,
            "IDENTITY_ATTACK": 0.2,
            "INSULT": 0.3,
            "PROFANITY": 0.4,
            "THREAT": 0.0,
            "SEXUALLY_EXPLICIT": 0.0,
            "FLIRTATION": 0.0,
        },
    )

    assert len(sentiment) == 2
    assert sentiment[0]["is_post"] == 1
    assert toxicity["toxicity"] == 0.5


def test_emotion_prompt_matches_ysimulator():
    payload = build_emotion_prompt("Sample text")

    assert payload["system_template"] == EMOTION_SYSTEM_TEMPLATE
    assert payload["user_template"] == EMOTION_USER_TEMPLATE
    assert payload["emotion_list"] == EMOTION_LIST
    assert "trust" in payload["emotion_list"]
    assert "neutral" not in payload["emotion_list"]


def test_standard_llm_extract_emotions_uses_text_and_emotion_list_variables(monkeypatch):
    service_cls = LLMService.__ray_metadata__.modified_class
    service = object.__new__(service_cls)
    service.prompts_config = {
        "extract_emotions": {
            "system_template": "system",
            "user_template": "{text} / {emotion_list}",
        }
    }
    service._parser = object()
    service.llm = object()
    service.prompt_logger = None
    service.usage_tracker = None

    class _FakeChain:
        def __init__(self):
            self.payload = None

        def invoke(self, payload):
            self.payload = payload
            return "joy, trust"

    fake_chain = _FakeChain()

    class _FakePrompt:
        def __or__(self, other):
            return self

    class _FakePromptTemplate:
        @staticmethod
        def from_messages(messages):
            return _FakePrompt()

    class _FakePromptWithLlm:
        def __or__(self, other):
            return fake_chain

    monkeypatch.setattr(
        "YPhotoSharing.YClient.LLM_interactions.llm_service.ChatPromptTemplate",
        _FakePromptTemplate,
    )
    _FakePrompt.__or__ = lambda self, other: _FakePromptWithLlm()
    emotions = service.extract_emotions("Sample text")

    assert emotions == ["joy", "trust"]
    assert fake_chain.payload["text"] == "Sample text"
    assert "trust" in fake_chain.payload["emotion_list"]
