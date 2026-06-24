from pathlib import Path
import tempfile

from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware
from YPhotoSharing.YServer.classes.models import Interest, Round, UserInterest


def _make_db(tmpdir: str) -> DatabaseMiddleware:
    return DatabaseMiddleware(
        {"type": "sqlite", "sqlite": {"filename": "phase2.db"}},
        config_path=Path(tmpdir),
    )


def test_interest_window_counts_are_computed_from_round_history():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = _make_db(tmpdir)
        user_id = db.create_user({"username": "alice", "password": "secret"})
        travel_id = db.add_or_get_interest("travel")
        food_id = db.add_or_get_interest("food")
        round_0 = db.get_or_create_round(0, 0)
        round_1 = db.get_or_create_round(0, 1)
        round_2 = db.get_or_create_round(0, 2)

        with db.session_scope() as session:
            session.add_all(
                [
                    UserInterest(id="ui-1", user_id=user_id, interest_id=travel_id, round_id=round_0),
                    UserInterest(id="ui-2", user_id=user_id, interest_id=travel_id, round_id=round_1),
                    UserInterest(id="ui-3", user_id=user_id, interest_id=food_id, round_id=round_2),
                    Interest(iid="unused", interest="unused"),
                ]
            )

        counts = db.compute_interest_counts_in_window(user_id, round_2, attention_window=2)

        assert counts[travel_id] == 1
        assert counts[food_id] == 1
        assert "unused" not in counts
