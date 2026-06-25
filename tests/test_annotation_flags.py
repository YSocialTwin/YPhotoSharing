from types import SimpleNamespace

from YPhotoSharing.YClient.annotation import normalize_annotation_flags
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
