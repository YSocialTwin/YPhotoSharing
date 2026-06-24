from YPhotoSharing.YServer.repositories.social_action_repository import SocialActionRepository
from YPhotoSharing.YServer.services.social_action_service import SocialActionService


class FakeDbAdapter:
    def __init__(self):
        self.calls = []

    def create_photo(self, photo_data):
        self.calls.append(("create_photo", photo_data))
        return "photo-1"

    def add_comment(self, user_id, photo_id, body, round_id, parent_comment_id):
        self.calls.append(("add_comment", user_id, photo_id, body, round_id, parent_comment_id))
        return "comment-1"

    def add_report(self, reporter_id, content_id, content_type, reason, round_id):
        self.calls.append(("add_report", reporter_id, content_id, content_type, reason, round_id))
        return "report-1"


def test_social_action_service_uses_repository_abstraction():
    db = FakeDbAdapter()
    repository = SocialActionRepository(db)
    service = SocialActionService(repository=repository)

    assert service.post_photo({"caption": "hello"}) == "photo-1"
    assert service.post_comment("u1", "p1", "nice", "r1") == "comment-1"
    assert service.add_report("u1", "p1", "photo", "spam", "r1") == "report-1"

    assert db.calls[0][0] == "create_photo"
    assert db.calls[1][0] == "add_comment"
    assert db.calls[2][0] == "add_report"
