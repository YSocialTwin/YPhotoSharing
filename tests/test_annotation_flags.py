from YPhotoSharing.YClient.annotation import annotate_text, normalize_annotation_flags


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


def test_annotate_text_exposes_the_same_annotation_slots():
    annotations = annotate_text(
        "hello world",
        enable_sentiment=True,
        enable_emotion_annotation=True,
        enable_toxicity=True,
    )

    assert set(annotations) == {"sentiment", "emotions", "toxicity"}
    assert annotations["sentiment"] is not None
    assert annotations["emotions"] is not None
    assert annotations["toxicity"] is not None

