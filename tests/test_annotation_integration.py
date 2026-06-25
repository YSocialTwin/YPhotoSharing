from YPhotoSharing.YClient.text_processing import annotate_content
from YPhotoSharing.YServer.annotation_processor import AnnotationProcessor
from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware
from YPhotoSharing.YServer.classes.models import PostEmotion, PostSentiment, PostToxicity


def test_annotation_pipeline_follows_config_flags(monkeypatch):
    monkeypatch.setattr(
        "YPhotoSharing.YClient.text_processing.annotate_text",
        lambda text, **kwargs: {
            "hashtags": ["tag"],
            "mentions": ["user"],
            "sentiment": {"neg": 0.0, "pos": 0.1, "neu": 0.9, "compound": 0.1},
            "emotions": ["joy"],
            "toxicity": {"TOXICITY": 0.2},
        },
    )

    config = {
        "simulation": {
            "enable_sentiment": True,
            "enable_emotion_annotation": True,
            "enable_toxicity": True,
            "perspective_api_key": None,
        }
    }

    annotations = annotate_content("A sample post", config)
    processor = AnnotationProcessor(
        metadata_service=DatabaseMiddleware(),
        enable_sentiment=True,
        enable_emotion_annotation=True,
        enable_toxicity=True,
    )

    annotations["topics"] = ["topic-1"]
    annotations["emotions"] = ["joy"]
    processor._process_annotations("post-1", "user-1", annotations, is_post=True)

    assert processor.metadata_service.posts_sentiment
    assert processor.metadata_service.posts_toxicity
    assert processor.metadata_service.posts_emotions


def test_disabled_flags_do_not_persist_missing_annotations(monkeypatch):
    monkeypatch.setattr(
        "YPhotoSharing.YClient.text_processing.annotate_text",
        lambda text, **kwargs: {
            "hashtags": [],
            "mentions": [],
            "sentiment": None,
            "emotions": None,
            "toxicity": None,
        },
    )

    annotations = annotate_content(
        "A sample post",
        {
            "simulation": {
                "enable_sentiment": False,
                "enable_emotion_annotation": False,
                "enable_toxicity": False,
            }
        },
    )
    processor = AnnotationProcessor(metadata_service=DatabaseMiddleware())

    processor._process_annotations("post-2", "user-1", annotations, is_post=True)

    assert processor.metadata_service.posts_sentiment == []
    assert processor.metadata_service.posts_toxicity == []
    assert processor.metadata_service.posts_emotions == []


def test_database_middleware_initializes_goemotions():
    db = DatabaseMiddleware()
    db.initialize_emotions_table()

    assert db.get_emotion_by_name("joy") is not None
    assert db.get_emotion_by_name("trust") is not None


def test_annotation_processor_persists_generic_annotation_tables():
    db = DatabaseMiddleware()
    db.initialize_emotions_table()
    round_id = db.get_or_create_round(0, 0)
    user_id = db.create_user({"id": "user-1", "username": "alice", "password": "secret"})
    topic_id = db.get_or_create_interest("travel")
    processor = AnnotationProcessor(
        metadata_service=db,
        enable_sentiment=True,
        enable_emotion_annotation=True,
        enable_toxicity=True,
    )

    annotations = {
        "hashtags": ["sunset"],
        "mentions": [],
        "sentiment": {"neg": 0.1, "pos": 0.3, "neu": 0.6, "compound": 0.2},
        "toxicity": {"TOXICITY": 0.05, "INSULT": 0.01},
        "emotions": ["joy"],
        "topic_ids": [topic_id],
        "round": round_id,
    }

    processor._process_annotations("post-3", user_id, annotations, is_post=True)

    with db.session_scope() as session:
        assert session.query(PostSentiment).filter_by(post_id="post-3").count() == 1
        assert session.query(PostToxicity).filter_by(post_id="post-3").count() == 1
        assert session.query(PostEmotion).filter_by(post_id="post-3").count() == 1
