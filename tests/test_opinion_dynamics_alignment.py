import tempfile
from pathlib import Path
import sys
import types

from YPhotoSharing.YClient.opinion_dynamics.llm_evaluation import llm_evaluation
from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware
from YPhotoSharing.YServer.classes.models import OpinionPath, UserOpinion


def _make_db(tmpdir: str) -> DatabaseMiddleware:
    return DatabaseMiddleware(
        {"type": "sqlite", "sqlite": {"filename": "opinion.db"}},
        config_path=Path(tmpdir),
    )


def test_llm_likert_evaluation_moves_only_one_adjacent_step(monkeypatch):
    class FakeLlmManager:
        def evaluate_opinion_transition(self, *args, **kwargs):
            class Result:
                pass

            return "AGREE"

    monkeypatch.setitem(sys.modules, "ray", types.SimpleNamespace(get=lambda value: value))

    group_classes = {
        "Strongly disagree": [0.0, 0.2],
        "Disagree": [0.2, 0.4],
        "Neutral": [0.4, 0.6],
        "Agree": [0.6, 0.8],
        "Strongly agree": [0.8, 1.0],
    }

    value = llm_evaluation(
        x=0.3,
        y=0.9,
        text="A photo caption",
        topic="travel",
        author_name="alice",
        group_classes=group_classes,
        llm_manager=FakeLlmManager(),
    )

    assert value == 0.5


def test_discrete_opinion_paths_are_persisted():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _make_db(tmpdir)
        round_id = db.get_or_create_round(0, 0)
        user_id = db.create_user({"username": "alice", "password": "secret"})
        topic_id = db.get_or_create_interest("travel")

        db.update_user_opinion(
            user_id=user_id,
            topic="travel",
            topic_id=topic_id,
            opinion_score=0.7,
            round_id=round_id,
            opinion_label="Agree",
            model_name="llm_evaluation",
        )
        path_id = db.record_opinion_path(
            user_id=user_id,
            topic="travel",
            topic_id=topic_id,
            round_id=round_id,
            model_name="llm_evaluation",
            source_score=0.5,
            source_label="Neutral",
            target_score=0.7,
            target_label="Agree",
            transition="agree",
            direction="toward",
            evaluation_scope="interlocutor_only",
            parent_post_id="post-1",
            actor_user_id=user_id,
        )

        assert path_id
        assert db.get_latest_agent_opinion(user_id, "travel") == 0.7

        with db.session_scope() as session:
            opinion = session.query(UserOpinion).filter_by(user_id=user_id, topic="travel").one()
            path = session.query(OpinionPath).filter_by(id=path_id).one()
            opinion_topic_id = opinion.topic_id
            opinion_label = opinion.opinion_label
            opinion_model = opinion.model_name
            path_transition = path.transition
            path_target_label = path.target_label

        assert opinion_topic_id == topic_id
        assert opinion_label == "Agree"
        assert opinion_model == "llm_evaluation"
        assert path_transition == "agree"
        assert path_target_label == "Agree"
