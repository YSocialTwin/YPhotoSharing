from __future__ import annotations

from typing import List, Optional


class SocialActionRepository:
    """Repository wrapper around social-content DB helpers.

    The repository does not own persistence; it gives the server-side service
    layer a narrower, intent-focused API over the broad database middleware.
    """

    def __init__(self, db_adapter):
        self.db = db_adapter

    def post_photo(self, photo_data: dict) -> str:
        return self.db.create_photo(photo_data)

    def add_photo_emotion(self, photo_id: str, emotion: str) -> bool:
        return self.db.add_photo_emotion(photo_id, emotion)

    def get_photo(self, photo_id: str) -> Optional[dict]:
        return self.db.get_photo(photo_id)

    def get_photo_topics(self, photo_id: str) -> list:
        return self.db.get_photo_topics(photo_id)

    def get_user_photos(self, user_id: str, limit: int = 20, offset: int = 0) -> List[dict]:
        return self.db.get_user_photos(user_id, limit=limit, offset=offset)

    def delete_photo(self, photo_id: str) -> bool:
        return self.db.delete_photo(photo_id)

    def react_to_photo(self, user_id: str, photo_id: str, reaction_type: str, round_id: str) -> str:
        return self.db.add_reaction(user_id, photo_id, reaction_type, round_id)

    def remove_reaction(self, user_id: str, photo_id: str) -> bool:
        return self.db.remove_reaction(user_id, photo_id)

    def post_comment(
        self,
        user_id: str,
        photo_id: str,
        body: str,
        round_id: str,
        parent_comment_id: str = None,
    ) -> str:
        return self.db.add_comment(user_id, photo_id, body, round_id, parent_comment_id)

    def get_comments(self, photo_id: str, limit: int = 50) -> List[dict]:
        return self.db.get_comments(photo_id, limit=limit)

    def post_story(self, story_data: dict) -> str:
        return self.db.create_story(story_data)

    def view_story(self, story_id: str, viewer_id: str) -> bool:
        return self.db.record_story_view(story_id, viewer_id)

    def get_recent_stories(self, user_id: str, limit: int = 50) -> List[dict]:
        return self.db.get_recent_stories(user_id, limit)

    def save_photo(self, user_id: str, photo_id: str) -> str:
        return self.db.save_photo(user_id, photo_id)

    def get_saved_photos(self, user_id: str, limit: int = 30) -> List[dict]:
        return self.db.get_saved_photos(user_id, limit)

    def send_dm(self, sender_id: str, recipient_id: str, content: str, photo_id: str = None) -> str:
        return self.db.send_dm(sender_id, recipient_id, content, photo_id)

    def get_dms(self, user_id: str, limit: int = 50) -> List[dict]:
        return self.db.get_dms(user_id, limit)

    def add_report(
        self, reporter_id: str, content_id: str, content_type: str, reason: str, round_id: str
    ):
        return self.db.add_report(reporter_id, content_id, content_type, reason, round_id)
