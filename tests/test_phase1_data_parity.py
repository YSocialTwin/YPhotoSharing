from pathlib import Path
import tempfile

from YPhotoSharing.YClient.simulation.bootstrap import (
    normalize_agent_config,
    normalize_agent_population_document,
)
from YPhotoSharing.YClient.simulation.lifecycle_manager import LifecycleManager
from YPhotoSharing.YClient.LLM_interactions.llm_service import _format_persona_context
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


def test_photo_sharing_fields_can_be_embedded_in_agent_population_records():
    record = normalize_agent_config(
        {
            "id": "user-1",
            "username": "alice",
            "photo_sharing": {
                "cover_image": "alice_cover.jpg",
                "favorite_filters": ["warm"],
                "story_visibility": "followers",
                "creator_tier": "pro",
            },
        },
        simulation_config={},
    )

    assert record["cover_image"] == "alice_cover.jpg"
    assert record["favorite_filters"] == ["warm"]
    assert record["story_visibility"] == "followers"
    assert record["creator_tier"] == "pro"
    assert record["photo_sharing"]["creator_tier"] == "pro"


def test_legacy_string_recsys_type_is_coerced_to_numeric_cluster():
    record = normalize_agent_config(
        {
            "id": "user-1",
            "username": "alice",
            "recsys_type": "random",
        },
        simulation_config={},
    )

    assert record["recsys_type"] == 0


def test_legacy_list_population_is_normalized_to_agents_document():
    population = normalize_agent_population_document(
        [{"id": "user-1", "username": "alice"}]
    )

    assert population["agents"][0]["username"] == "alice"
    assert population["generation_config"]["num_additional_agents"] == 0


def test_nested_interests_normalization():
    record1 = normalize_agent_config(
        {
            "id": "user-1",
            "username": "alice",
            "interests": [["gym", "chess"], 2],
        },
        simulation_config={},
    )
    assert record1["interests"] == ["gym", "chess"]

    record2 = normalize_agent_config(
        {
            "id": "user-2",
            "username": "bob",
            "interests": ["gym", "chess"],
        },
        simulation_config={},
    )
    assert record2["interests"] == ["gym", "chess"]



def test_persona_context_uses_profile_and_photo_sharing_details():
    persona = _format_persona_context(
        {
            "age": 29,
            "gender": "female",
            "nationality": "US",
            "education_level": "college",
            "profession": "traveler",
            "leaning": "neutral",
            "activity_profile": "high",
            "archetype": "explorer",
            "language": "en",
            "oe": "high",
            "co": "medium",
            "ex": "high",
            "ag": "medium",
            "ne": "low",
            "is_verified": True,
            "is_private": False,
            "is_page": 0,
            "bio": "Travel and food lover",
            "interests": ["travel", "food"],
            "custom_features": {
                "aesthetic": "warm travel diary",
                "tone": "curious and friendly",
            },
            "photo_sharing": {
                "favorite_filters": ["warm", "vintage"],
                "story_visibility": "followers",
                "creator_tier": "standard",
            },
        }
    )

    assert "29-year-old" in persona
    assert "female" in persona
    assert "from US" in persona
    assert "verified account" in persona
    assert "Interests: travel, food." in persona
    assert "favorite filters: warm, vintage" in persona
    assert "Additional personal details: aesthetic: warm travel diary; tone: curious and friendly." in persona


def test_lifecycle_manager_defaults_are_disabled_and_zero():
    manager = LifecycleManager(
        server=None,
        client_id="client_1",
        config_path=".",
        simulation_config={"agents": {}},
        logger=None,
        add_agent_from_record_func=lambda *args, **kwargs: None,
        existing_usernames_func=lambda: [],
    )

    assert manager.churn_enabled is False
    assert manager.churn_probability == 0.0
    assert manager.churn_percentage == 0.0
    assert manager.new_agents_enabled is False
    assert manager.probability_new_agents == 0.0
    assert manager.percentage_new_agents == 0.0


def test_lifecycle_manager_builds_new_agent_from_template():
    manager = LifecycleManager(
        server=None,
        client_id="client_1",
        config_path=".",
        simulation_config={
            "agents": {
                "new_agents": {
                    "enabled": True,
                    "probability_new_agents": 1.0,
                    "percentage_new_agents": 1.0,
                }
            }
        },
        logger=None,
        add_agent_from_record_func=lambda *args, **kwargs: None,
        existing_usernames_func=lambda: ["template_user"],
    )

    record = manager._make_new_agent_user_data(
        {
            "id": "template-id",
            "username": "template_user",
            "user_type": "llm",
            "photo_sharing": {"creator_tier": "pro"},
            "is_private": False,
            "is_verified": True,
            "attention_budget": 100,
        },
        day=4,
        round_id="round-4",
    )

    assert record["username"] != "template_user"
    assert record["left_on"] is None
    assert record["is_churned"] is False
    assert record["last_active_day"] == 4
    assert record["photo_sharing"]["creator_tier"] == "pro"
