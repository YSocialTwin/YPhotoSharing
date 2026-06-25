from YPhotoSharing.YClient.text_processing import annotate_content
from YPhotoSharing.YServer.annotation_processor import AnnotationProcessor


def test_annotation_pipeline_follows_config_flags():
    config = {
        "simulation": {
            "enable_sentiment": True,
            "enable_emotion_annotation": True,
            "enable_toxicity": True,
        }
    }

    annotations = annotate_content("A sample post", config)
    processor = AnnotationProcessor(
        enable_sentiment=True,
        enable_emotion_annotation=True,
        enable_toxicity=True,
    )

    stored = processor.process_post("post-1", annotations)

    assert set(annotations) == {"sentiment", "emotions", "toxicity"}
    assert "sentiment" in stored
    assert "emotions" in stored
    assert "toxicity" in stored


def test_disabled_flags_do_not_persist_missing_annotations():
    annotations = annotate_content(
        "A sample post",
        {"simulation": {"enable_sentiment": False, "enable_emotion_annotation": False, "enable_toxicity": False}},
    )
    processor = AnnotationProcessor()

    stored = processor.process_post("post-2", annotations)

    assert stored == {"post_id": "post-2"}

