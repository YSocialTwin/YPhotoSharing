from YPhotoSharing.YServer.services.social_action_service import SocialActionService


class FakeDbAdapter:
    def __init__(self):
        self.calls = []

    def create_photo(self, photo_data):
        self.calls.append(("create_photo", photo_data))
        return "photo-1"

    def add_photo_emotion(self, photo_id, emotion):
        self.calls.append(("add_photo_emotion", photo_id, emotion))
        return True

    def get_photo(self, photo_id):
        self.calls.append(("get_photo", photo_id))
        return {"id": photo_id, "caption": "test"}

    def get_photo_topics(self, photo_id):
        self.calls.append(("get_photo_topics", photo_id))
        return ["topic-1"]

    def get_user_photos(self, user_id, limit=20, offset=0):
        self.calls.append(("get_user_photos", user_id, limit, offset))
        return [{"id": "photo-1"}]

    def delete_photo(self, photo_id):
        self.calls.append(("delete_photo", photo_id))
        return True

    def add_reaction(self, user_id, photo_id, reaction_type, round_id):
        self.calls.append(("add_reaction", user_id, photo_id, reaction_type, round_id))
        return "reaction-1"

    def remove_reaction(self, user_id, photo_id):
        self.calls.append(("remove_reaction", user_id, photo_id))
        return True

    def add_comment(self, user_id, photo_id, body, round_id, parent_comment_id=None):
        self.calls.append(("add_comment", user_id, photo_id, body, round_id, parent_comment_id))
        return "comment-1"

    def get_comments(self, photo_id, limit=50):
        self.calls.append(("get_comments", photo_id, limit))
        return [{"id": "comment-1"}]

    def create_story(self, story_data):
        self.calls.append(("create_story", story_data))
        return "story-1"

    def record_story_view(self, story_id, viewer_id):
        self.calls.append(("record_story_view", story_id, viewer_id))
        return True

    def get_recent_stories(self, user_id, limit=50):
        self.calls.append(("get_recent_stories", user_id, limit))
        return [{"id": "story-1"}]

    def save_photo(self, user_id, photo_id):
        self.calls.append(("save_photo", user_id, photo_id))
        return "saved-1"

    def get_saved_photos(self, user_id, limit=30):
        self.calls.append(("get_saved_photos", user_id, limit))
        return [{"id": "photo-1"}]

    def send_dm(self, sender_id, recipient_id, content, photo_id=None):
        self.calls.append(("send_dm", sender_id, recipient_id, content, photo_id))
        return "dm-1"

    def get_dms(self, user_id, limit=50):
        self.calls.append(("get_dms", user_id, limit))
        return [{"id": "dm-1"}]

    def add_report(self, reporter_id, content_id, content_type, reason, round_id):
        self.calls.append(("add_report", reporter_id, content_id, content_type, reason, round_id))
        return "report-1"


def test_social_action_service_delegates_domain_operations():
    db = FakeDbAdapter()
    service = SocialActionService(db)

    assert service.post_photo({"caption": "hello"}) == "photo-1"
    assert service.add_photo_emotion("photo-1", "joy") is True
    assert service.get_photo("photo-1")["id"] == "photo-1"
    assert service.get_photo_topics("photo-1") == ["topic-1"]
    assert service.get_user_photos("user-1", limit=10, offset=2) == [{"id": "photo-1"}]
    assert service.delete_photo("photo-1") is True
    assert service.react_to_photo("user-1", "photo-1", "LIKE", "round-1") == "reaction-1"
    assert service.remove_reaction("user-1", "photo-1") is True
    assert service.post_comment("user-1", "photo-1", "Nice", "round-1") == "comment-1"
    assert service.get_comments("photo-1") == [{"id": "comment-1"}]
    assert service.post_story({"caption": "story"}) == "story-1"
    assert service.view_story("story-1", "user-1") is True
    assert service.get_recent_stories("user-1") == [{"id": "story-1"}]
    assert service.save_photo("user-1", "photo-1") == "saved-1"
    assert service.get_saved_photos("user-1") == [{"id": "photo-1"}]
    assert service.send_dm("user-1", "user-2", "hi") == "dm-1"
    assert service.get_dms("user-1") == [{"id": "dm-1"}]
    assert service.add_report("user-1", "photo-1", "photo", "spam", "round-1") == "report-1"

    assert ("create_photo", {"caption": "hello"}) in db.calls
    assert ("add_report", "user-1", "photo-1", "photo", "spam", "round-1") in db.calls
