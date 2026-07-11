from __future__ import annotations

import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy import and_, create_engine, func, or_, text
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Base,
    Comment,
    DirectMessage,
    Emotion,
    Follow,
    FollowRequest,
    Hashtag,
    Interest,
    MemoryInteractionEvent,
    OpinionPath,
    Photo,
    PhotoEmotion,
    PhotoHashtag,
    PhotoTopic,
    PostEmotion,
    PostSentiment,
    PostToxicity,
    Reaction,
    Recommendation,
    Reported,
    Round,
    SavedPhoto,
    StressReward,
    Story,
    StoryView,
    UserInterest,
    UserOpinion,
    User_mgmt,
)


GOEMOTIONS = [
    ("admiration", None),
    ("amusement", None),
    ("anger", None),
    ("annoyance", None),
    ("approval", None),
    ("caring", None),
    ("confusion", None),
    ("curiosity", None),
    ("desire", None),
    ("disappointment", None),
    ("disapproval", None),
    ("disgust", None),
    ("embarrassment", None),
    ("excitement", None),
    ("fear", None),
    ("gratitude", None),
    ("grief", None),
    ("joy", None),
    ("love", None),
    ("nervousness", None),
    ("optimism", None),
    ("pride", None),
    ("realization", None),
    ("relief", None),
    ("remorse", None),
    ("sadness", None),
    ("surprise", None),
    ("trust", None),
]


class DatabaseMiddleware:
    """SQLAlchemy-backed middleware with the YSimulator-aligned helpers used by YPhotoSharing."""

    def __init__(
        self,
        db_config: Optional[Dict[str, Any]] = None,
        config_path: Any = ".",
        redis_config: Optional[Dict[str, Any]] = None,
        logger: Optional[logging.Logger] = None,
        simulation_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        del redis_config
        self.logger = logger or logging.getLogger(__name__)
        self.config_path = Path(config_path)
        self.db_config = db_config or {"type": "sqlite", "sqlite": {"filename": ":memory:"}}
        self.simulation_config = simulation_config or {}
        self.round_cache: Dict[tuple[int, int], str] = {}
        self.use_redis = False

        self.posts_sentiment: List[Dict[str, Any]] = []
        self.posts_toxicity: List[Dict[str, Any]] = []
        self.posts_emotions: List[Dict[str, Any]] = []
        self.hashtags: Dict[str, str] = {}
        self.post_hashtags: List[Dict[str, Any]] = []

        connection_string = self._build_connection_string(self.db_config)
        engine_kwargs: Dict[str, Any] = {}
        if connection_string.startswith("sqlite:"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        self.engine = create_engine(connection_string, future=True, **engine_kwargs)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)
        self._ensure_story_schema()

    def _build_connection_string(self, db_config: Dict[str, Any]) -> str:
        db_type = (db_config.get("type") or "sqlite").lower()
        if db_type != "sqlite":
            raise ValueError(f"Unsupported database type for current test surface: {db_type}")

        sqlite_config = db_config.get("sqlite", {})
        filename = sqlite_config.get("filename", "simulation.db")
        if filename == ":memory:":
            return "sqlite+pysqlite:///:memory:"
        db_path = self.config_path / filename
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+pysqlite:///{db_path}"

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _table_columns(self, table_name: str) -> set[str]:
        with self.engine.connect() as connection:
            rows = connection.execute(text(f"PRAGMA table_info({table_name})")).mappings().all()
        return {str(row["name"]) for row in rows}

    def _ensure_story_schema(self) -> None:
        if self.engine.url.get_backend_name() != "sqlite":
            return

        existing_columns = self._table_columns("stories")
        pending_statements = [
            ("title", "ALTER TABLE stories ADD COLUMN title VARCHAR(120)"),
            ("description", "ALTER TABLE stories ADD COLUMN description TEXT"),
            ("image_urls", "ALTER TABLE stories ADD COLUMN image_urls TEXT"),
        ]
        with self.engine.begin() as connection:
            for column_name, statement in pending_statements:
                if column_name not in existing_columns:
                    connection.execute(text(statement))

    def initialize_emotions_table(self) -> bool:
        with self.session_scope() as session:
            existing = {name for (name,) in session.query(Emotion.emotion).all()}
            for emotion_name, icon in GOEMOTIONS:
                if emotion_name not in existing:
                    session.add(Emotion(id=str(uuid.uuid4()), emotion=emotion_name, icon=icon))
        return True

    def get_emotion_by_name(self, emotion_name: str) -> Optional[Dict[str, Any]]:
        self.initialize_emotions_table()
        with self.session_scope() as session:
            emotion = session.query(Emotion).filter(Emotion.emotion == emotion_name).first()
            if emotion is None:
                return None
            return {"id": emotion.id, "emotion": emotion.emotion, "icon": emotion.icon}

    def add_post_emotion(self, post_id: str, emotion_id: str) -> bool:
        self.posts_emotions.append({"post_id": post_id, "emotion_id": emotion_id})
        with self.session_scope() as session:
            existing_post_emotion = (
                session.query(PostEmotion)
                .filter(PostEmotion.post_id == post_id, PostEmotion.emotion_id == emotion_id)
                .first()
            )
            if existing_post_emotion is None:
                session.add(
                    PostEmotion(
                        id=str(uuid.uuid4()),
                        post_id=post_id,
                        emotion_id=emotion_id,
                    )
                )

            photo = session.query(Photo).filter(Photo.id == post_id).first()
            if photo is None:
                return True
            existing = (
                session.query(PhotoEmotion)
                .filter(PhotoEmotion.photo_id == post_id, PhotoEmotion.emotion_id == emotion_id)
                .first()
            )
            if existing is None:
                session.add(
                    PhotoEmotion(
                        id=str(uuid.uuid4()),
                        photo_id=post_id,
                        emotion_id=emotion_id,
                    )
                )
        return True

    def add_post_sentiment(self, sentiment_data: Dict[str, Any]) -> bool:
        self.posts_sentiment.append(dict(sentiment_data))
        try:
            with self.session_scope() as session:
                payload = {
                    "id": str(uuid.uuid4()),
                    "post_id": sentiment_data["post_id"],
                    "user_id": sentiment_data["user_id"],
                    "topic_id": sentiment_data.get("topic_id"),
                    "round": sentiment_data["round"],
                    "neg": sentiment_data.get("neg"),
                    "pos": sentiment_data.get("pos"),
                    "neu": sentiment_data.get("neu"),
                    "compound": sentiment_data.get("compound"),
                    "sentiment_parent": sentiment_data.get("sentiment_parent"),
                    "is_post": sentiment_data.get("is_post", 0),
                    "is_comment": sentiment_data.get("is_comment", 0),
                    "is_reaction": sentiment_data.get("is_reaction", 0),
                }
                session.add(PostSentiment(**payload))
        except Exception:
            self.logger.debug("Skipping persistent post sentiment write for %s", sentiment_data.get("post_id"))
        return True

    def get_post_sentiment(self, post_id: str) -> Optional[Dict[str, Any]]:
        with self.session_scope() as session:
            row = (
                session.query(PostSentiment)
                .filter(PostSentiment.post_id == post_id)
                .order_by(PostSentiment.id.desc())
                .first()
            )
            if row is None:
                photo = session.query(Photo).filter(Photo.id == post_id).first()
                if photo is not None and photo.sentiment_score is not None:
                    return {"compound": photo.sentiment_score}
                comment = session.query(Comment).filter(Comment.id == post_id).first()
                if comment is not None and comment.sentiment_score is not None:
                    return {"compound": comment.sentiment_score}
                return None
            return {column.name: getattr(row, column.name) for column in PostSentiment.__table__.columns}

    def add_post_toxicity(self, toxicity_data: Dict[str, Any]) -> bool:
        payload = {"id": str(uuid.uuid4()), **dict(toxicity_data)}
        self.posts_toxicity.append(payload)
        try:
            with self.session_scope() as session:
                session.add(PostToxicity(**payload))
        except Exception:
            self.logger.debug("Skipping persistent post toxicity write for %s", toxicity_data.get("post_id"))
        return True

    def add_or_get_hashtag(self, hashtag_text: str) -> str:
        if hashtag_text in self.hashtags:
            return self.hashtags[hashtag_text]
        with self.session_scope() as session:
            existing = session.query(Hashtag).filter(Hashtag.hashtag == hashtag_text).first()
            if existing is not None:
                self.hashtags[hashtag_text] = existing.id
                return existing.id
            hashtag_id = str(uuid.uuid4())
            session.add(Hashtag(id=hashtag_id, hashtag=hashtag_text))
            self.hashtags[hashtag_text] = hashtag_id
            return hashtag_id

    def add_post_hashtag(self, post_id: str, hashtag_id: str) -> bool:
        self.post_hashtags.append({"post_id": post_id, "hashtag_id": hashtag_id})
        with self.session_scope() as session:
            photo = session.query(Photo).filter(Photo.id == post_id).first()
            if photo is None:
                return True
            existing = (
                session.query(PhotoHashtag)
                .filter(PhotoHashtag.photo_id == post_id, PhotoHashtag.hashtag_id == hashtag_id)
                .first()
            )
            if existing is None:
                session.add(
                    PhotoHashtag(id=str(uuid.uuid4()), photo_id=post_id, hashtag_id=hashtag_id)
                )
        return True

    def get_or_create_round(self, day: int, hour: int) -> str:
        cache_key = (day, hour)
        if cache_key in self.round_cache:
            return self.round_cache[cache_key]
        with self.session_scope() as session:
            round_obj = session.query(Round).filter(Round.day == day, Round.hour == hour).first()
            if round_obj is None:
                round_obj = Round(id=str(uuid.uuid4()), day=day, hour=hour)
                session.add(round_obj)
                session.flush()
            self.round_cache[cache_key] = round_obj.id
            return round_obj.id

    def create_user(self, user_data: Dict[str, Any]) -> str:
        payload = dict(user_data)
        user_id = payload.setdefault("id", str(uuid.uuid4()))
        payload.setdefault("username", f"user_{user_id[:8]}")
        payload.setdefault("password", "secret")
        payload.setdefault("round_actions", 3)
        payload.setdefault("daily_activity_level", 1)
        allowed_keys = {column.name for column in User_mgmt.__table__.columns}
        payload = {key: value for key, value in payload.items() if key in allowed_keys}
        with self.session_scope() as session:
            existing = session.query(User_mgmt).filter(User_mgmt.id == user_id).first()
            if existing is None:
                session.add(User_mgmt(**payload))
        return user_id

    def get_user(self, user_id: str) -> Optional[dict]:
        with self.session_scope() as session:
            row = session.query(User_mgmt).filter_by(id=user_id).first()
            if row is None:
                return None
            return {column.name: getattr(row, column.name) for column in User_mgmt.__table__.columns}

    def get_user_by_username(self, username: str) -> Optional[dict]:
        with self.session_scope() as session:
            row = session.query(User_mgmt).filter_by(username=username).first()
            if row is None:
                return None
            return {column.name: getattr(row, column.name) for column in User_mgmt.__table__.columns}

    def list_users(self, limit: int = 100, offset: int = 0) -> List[dict]:
        with self.session_scope() as session:
            rows = session.query(User_mgmt).limit(limit).offset(offset).all()
            return [
                {column.name: getattr(row, column.name) for column in User_mgmt.__table__.columns}
                for row in rows
            ]

    def update_satisfaction(self, user_id: str, delta: float) -> float:
        with self.session_scope() as session:
            user = session.query(User_mgmt).filter_by(id=user_id).first()
            if user is None:
                return 0.0
            new_score = max(0.0, min(100.0, float(user.satisfaction_score or 100.0) + float(delta)))
            user.satisfaction_score = new_score
            if new_score <= 10.0:
                user.is_churned = True
            return new_score

    def set_churn_state(self, user_id: str, is_churned: bool) -> bool:
        with self.session_scope() as session:
            user = session.query(User_mgmt).filter_by(id=user_id).first()
            if user is None:
                return False
            user.is_churned = bool(is_churned)
            return True

    def update_last_active_day(self, user_id: str, day: int) -> bool:
        with self.session_scope() as session:
            user = session.query(User_mgmt).filter_by(id=user_id).first()
            if user is None:
                return False
            user.last_active_day = int(day)
            return True

    def create_photo(self, photo_data: Dict[str, Any]) -> str:
        payload = dict(photo_data)
        photo_id = payload.setdefault("id", str(uuid.uuid4()))
        payload.setdefault("thumbnail_url", payload.get("image_url"))
        payload.setdefault("image_url", "")
        topics = list(payload.pop("topics", []) or [])
        topic = payload.pop("topic", None)
        if topic and topic not in topics:
            topics.append(topic)

        allowed_keys = {column.name for column in Photo.__table__.columns}
        clean_payload = {k: v for k, v in payload.items() if k in allowed_keys}

        with self.session_scope() as session:
            session.add(Photo(**clean_payload))
            session.flush()
            for topic_name in topics:
                topic_id = self._add_or_get_interest_in_session(session, topic_name)
                existing = (
                    session.query(PhotoTopic)
                    .filter(PhotoTopic.photo_id == photo_id, PhotoTopic.topic_id == topic_id)
                    .first()
                )
                if existing is None:
                    session.add(
                        PhotoTopic(
                            id=str(uuid.uuid4()),
                            photo_id=photo_id,
                            topic_id=topic_id,
                            confidence=1.0,
                        )
                    )
        return photo_id

    def _add_or_get_interest_in_session(self, session: Session, interest_name: str) -> str:
        existing = session.query(Interest).filter(Interest.interest == interest_name).first()
        if existing is not None:
            return existing.iid
        interest_id = str(uuid.uuid4())
        session.add(Interest(iid=interest_id, interest=interest_name))
        session.flush()
        return interest_id

    def _latest_round_id(self, session: Session) -> str:
        round_row = (
            session.query(Round)
            .order_by(Round.day.desc(), Round.hour.desc(), Round.id.desc())
            .first()
        )
        return round_row.id if round_row is not None else ""

    def get_photo(self, photo_id: str) -> Optional[dict]:
        with self.session_scope() as session:
            photo = session.query(Photo).filter(Photo.id == photo_id).first()
            if photo is None:
                return None
            return {column.name: getattr(photo, column.name) for column in Photo.__table__.columns}

    def get_user_photos(self, user_id: str, limit: int = 20, offset: int = 0) -> List[dict]:
        with self.session_scope() as session:
            photos = (
                session.query(Photo)
                .join(Round, Round.id == Photo.round)
                .filter(Photo.user_id == user_id)
                .order_by(Round.day.desc(), Round.hour.desc(), Photo.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [
                {column.name: getattr(photo, column.name) for column in Photo.__table__.columns}
                for photo in photos
            ]

    def delete_photo(self, photo_id: str) -> bool:
        with self.session_scope() as session:
            photo = session.query(Photo).filter_by(id=photo_id).first()
            if photo is None:
                return False
            photo.deleted_at = datetime.utcnow()
            return True

    def add_or_get_interest(self, interest_name: str) -> str:
        with self.session_scope() as session:
            return self._add_or_get_interest_in_session(session, interest_name)

    def get_or_create_interest(self, interest_name: str) -> str:
        return self.add_or_get_interest(interest_name)

    def get_topic_name_from_id(self, topic_id: str) -> Optional[str]:
        with self.session_scope() as session:
            interest = session.query(Interest).filter(Interest.iid == topic_id).first()
            return interest.interest if interest else None

    def get_photo_topics(self, photo_id: str) -> List[str]:
        with self.session_scope() as session:
            rows = session.query(PhotoTopic.topic_id).filter(PhotoTopic.photo_id == photo_id).all()
            return [row[0] for row in rows]

    def set_user_interests(self, user_id: str, topic_ids: List[str], round_id: str) -> int:
        written = 0
        with self.session_scope() as session:
            for topic_id in topic_ids:
                session.add(
                    UserInterest(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        interest_id=topic_id,
                        round_id=round_id,
                    )
                )
                written += 1
        return written

    def get_user_interests(self, user_id: str) -> List[str]:
        with self.session_scope() as session:
            rows = (
                session.query(Interest.interest)
                .join(UserInterest, UserInterest.interest_id == Interest.iid)
                .filter(UserInterest.user_id == user_id)
                .all()
            )
            return [row[0] for row in rows if row and row[0]]

    def add_follow(self, user_id: str, follower_id: str, round_id: str, action: str = "follow") -> str:
        follow_id = str(uuid.uuid4())
        with self.session_scope() as session:
            session.add(
                Follow(
                    id=follow_id,
                    user_id=user_id,
                    follower_id=follower_id,
                    action=action,
                    round=round_id,
                )
            )
        return follow_id

    def remove_follow(self, user_id: str, follower_id: str, round_id: str) -> bool:
        with self.session_scope() as session:
            row = session.query(Follow).filter_by(user_id=user_id, follower_id=follower_id).first()
            if row is None:
                return False
            row.action = "unfollow"
            row.round = round_id
            return True

    def get_followers(self, user_id: str) -> List[str]:
        with self.session_scope() as session:
            rows = session.query(Follow).filter_by(user_id=user_id, action="follow").all()
            return [row.follower_id for row in rows]

    def get_following(self, user_id: str) -> List[str]:
        with self.session_scope() as session:
            rows = session.query(Follow).filter_by(follower_id=user_id, action="follow").all()
            return [row.user_id for row in rows]

    def add_photo_emotion(self, photo_id: str, emotion: str) -> bool:
        emotion_obj = self.get_emotion_by_name(emotion)
        if emotion_obj is None:
            return False
        return self.add_post_emotion(photo_id, emotion_obj["id"])

    def add_reaction(self, user_id: str, photo_id: str, reaction_type: str, round_id: str) -> str:
        with self.session_scope() as session:
            existing = session.query(Reaction).filter_by(user_id=user_id, photo_id=photo_id).first()
            if existing is not None:
                existing.reaction_type = reaction_type
                existing.round = round_id
                return existing.id
            reaction_id = str(uuid.uuid4())
            session.add(
                Reaction(
                    id=reaction_id,
                    user_id=user_id,
                    photo_id=photo_id,
                    reaction_type=reaction_type,
                    round=round_id,
                )
            )
            photo = session.query(Photo).filter_by(id=photo_id).first()
            if photo is not None:
                photo.num_likes = (photo.num_likes or 0) + 1
            return reaction_id

    def remove_reaction(self, user_id: str, photo_id: str) -> bool:
        with self.session_scope() as session:
            row = session.query(Reaction).filter_by(user_id=user_id, photo_id=photo_id).first()
            if row is None:
                return False
            session.delete(row)
            photo = session.query(Photo).filter_by(id=photo_id).first()
            if photo is not None and photo.num_likes:
                photo.num_likes = max(0, photo.num_likes - 1)
            return True

    def add_comment(
        self, user_id: str, photo_id: str, body: str, round_id: str, parent_comment_id: str = None
    ) -> str:
        with self.session_scope() as session:
            comment_id = str(uuid.uuid4())
            session.add(
                Comment(
                    id=comment_id,
                    user_id=user_id,
                    photo_id=photo_id,
                    body=body,
                    round=round_id,
                    parent_comment_id=parent_comment_id,
                )
            )
            photo = session.query(Photo).filter_by(id=photo_id).first()
            if photo is not None:
                photo.num_comments = (photo.num_comments or 0) + 1
            return comment_id

    def get_comments(self, photo_id: str, limit: int = 50, offset: int = 0) -> List[dict]:
        with self.session_scope() as session:
            rows = (
                session.query(Comment)
                .join(Round, Round.id == Comment.round)
                .filter_by(photo_id=photo_id, is_deleted=False, parent_comment_id=None)
                .order_by(Round.day.asc(), Round.hour.asc(), Comment.created_at)
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [
                {column.name: getattr(row, column.name) for column in Comment.__table__.columns}
                for row in rows
            ]

    def create_story(self, story_data: dict) -> str:
        with self.session_scope() as session:
            story_id = story_data.get("id") or str(uuid.uuid4())
            valid_keys = {column.name for column in Story.__table__.columns}
            filtered = {k: v for k, v in story_data.items() if k in valid_keys and k != "id"}
            image_urls = filtered.get("image_urls")
            if isinstance(image_urls, str):
                try:
                    image_urls = json.loads(image_urls)
                except json.JSONDecodeError:
                    image_urls = [image_urls] if image_urls else []
            elif image_urls is None:
                image_urls = []
            elif not isinstance(image_urls, list):
                image_urls = [image_urls]

            normalized_urls: List[str] = []
            for item in image_urls:
                if isinstance(item, dict):
                    candidate = item.get("url") or item.get("image_url") or item.get("media_url")
                else:
                    candidate = item
                candidate = str(candidate).strip() if candidate is not None else ""
                if candidate and candidate not in normalized_urls:
                    normalized_urls.append(candidate)

            media_url = str(filtered.get("media_url") or "").strip()
            if not media_url and normalized_urls:
                media_url = normalized_urls[0]
            if not normalized_urls and media_url:
                normalized_urls = [media_url]

            title = str(filtered.get("title") or filtered.get("caption") or "Story").strip()
            description = str(filtered.get("description") or filtered.get("caption") or title).strip()
            caption = str(filtered.get("caption") or description or title).strip()
            media_type = str(filtered.get("media_type") or ("carousel" if len(normalized_urls) > 1 else "image")).strip()

            filtered["media_url"] = media_url
            filtered["media_type"] = media_type
            filtered["title"] = title
            filtered["description"] = description
            filtered["caption"] = caption
            filtered["image_urls"] = json.dumps(normalized_urls)

            if not filtered["media_url"]:
                raise ValueError("Stories must include at least one existing image URL.")
            if not normalized_urls:
                raise ValueError("Stories must include at least one existing image URL.")

            session.add(Story(id=story_id, **filtered))
            return story_id

    def record_story_view(self, story_id: str, viewer_id: str) -> bool:
        with self.session_scope() as session:
            existing = session.query(StoryView).filter_by(story_id=story_id, viewer_id=viewer_id).first()
            if existing is not None:
                return False
            session.add(
                StoryView(
                    id=str(uuid.uuid4()),
                    story_id=story_id,
                    viewer_id=viewer_id,
                    round=self._latest_round_id(session),
                )
            )
            story = session.query(Story).filter_by(id=story_id).first()
            if story is not None:
                story.view_count = (story.view_count or 0) + 1
            return True

    def get_recent_stories(self, user_id: str, limit: int = 50) -> List[dict]:
        with self.session_scope() as session:
            following_rows = session.query(Follow.user_id).filter_by(follower_id=user_id, action="follow").all()
            following_ids = [row[0] for row in following_rows]
            if not following_ids:
                return []
            rows = (
                session.query(Story)
                .join(Round, Round.id == Story.round)
                .filter(Story.user_id.in_(following_ids))
                .order_by(Round.day.desc(), Round.hour.desc(), Story.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                self._serialize_story(row)
                for row in rows
            ]

    def _serialize_story(self, story: Story) -> Dict[str, Any]:
        payload = {column.name: getattr(story, column.name) for column in Story.__table__.columns}
        image_urls_raw = payload.get("image_urls")
        image_urls: List[str] = []
        if isinstance(image_urls_raw, str) and image_urls_raw.strip():
            try:
                parsed = json.loads(image_urls_raw)
            except json.JSONDecodeError:
                parsed = [image_urls_raw]
            if isinstance(parsed, list):
                image_urls = [str(item).strip() for item in parsed if str(item).strip()]
            elif parsed:
                image_urls = [str(parsed).strip()]
        elif isinstance(image_urls_raw, list):
            image_urls = [str(item).strip() for item in image_urls_raw if str(item).strip()]

        if not image_urls and payload.get("media_url"):
            image_urls = [str(payload["media_url"]).strip()]

        payload["image_urls"] = image_urls
        if not payload.get("title"):
            payload["title"] = payload.get("caption") or "Story"
        if not payload.get("description"):
            payload["description"] = payload.get("caption") or payload["title"] or ""
        if not payload.get("caption"):
            payload["caption"] = payload["description"] or payload["title"]
        return payload

    def update_photo_sentiment(self, photo_id: str, sentiment_score: float) -> bool:
        with self.session_scope() as session:
            photo = session.query(Photo).filter(Photo.id == photo_id).first()
            if photo is None:
                return False
            photo.sentiment_score = sentiment_score
        return True

    def _round_index(self, round_obj: Round) -> int:
        return int(round_obj.day or 0) * 1000 + int(round_obj.hour or 0)

    def _get_round(self, session: Session, round_id: str) -> Round:
        round_obj = session.query(Round).filter(Round.id == round_id).one()
        return round_obj

    def get_user_interests_in_window(
        self, user_id: str, current_round_id: str, attention_window: int
    ) -> List[Dict[str, Any]]:
        with self.session_scope() as session:
            current_round = self._get_round(session, current_round_id)
            current_index = self._round_index(current_round)
            lower_bound = current_index - max(0, attention_window) + 1

            rows = (
                session.query(UserInterest, Round)
                .join(Round, Round.id == UserInterest.round_id)
                .filter(UserInterest.user_id == user_id)
                .all()
            )
            result = []
            for user_interest, round_obj in rows:
                idx = self._round_index(round_obj)
                if lower_bound <= idx <= current_index:
                    result.append(
                        {
                            "interest_id": user_interest.interest_id,
                            "round_id": user_interest.round_id,
                        }
                    )
            return result

    def compute_interest_counts_in_window(
        self, user_id: str, current_round_id: str, attention_window: int
    ) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for row in self.get_user_interests_in_window(user_id, current_round_id, attention_window):
            interest_id = row["interest_id"]
            counts[interest_id] = counts.get(interest_id, 0) + 1
        return counts

    def add_recommendation(self, user_id: str, photo_ids: List[str], round_id: str) -> str:
        with self.session_scope() as session:
            recommendation_id = str(uuid.uuid4())
            session.add(
                Recommendation(
                    id=recommendation_id,
                    user_id=user_id,
                    photo_ids=json.dumps(photo_ids),
                    round=round_id,
                )
            )
            return recommendation_id

    def get_recommendation(self, user_id: str, round_id: str) -> Optional[List[str]]:
        with self.session_scope() as session:
            row = (
                session.query(Recommendation)
                .filter_by(user_id=user_id, round=round_id)
                .order_by(Recommendation.id.desc())
                .first()
            )
            if row is None:
                return None
            return json.loads(row.photo_ids or "[]")

    def get_or_create_hashtag(self, tag: str) -> str:
        return self.add_or_get_hashtag(tag)

    def tag_photo(self, photo_id: str, hashtag_id: str) -> None:
        self.add_post_hashtag(photo_id, hashtag_id)

    def add_memory_event(self, event_data: dict) -> int:
        payload = dict(event_data or {})
        normalized = {
            "run_id": payload.get("run_id"),
            "round_id": payload.get("round_id", 0),
            "actor_user_id": payload.get("actor_user_id", payload.get("agent_user_id")),
            "target_user_id": payload.get("target_user_id", payload.get("other_user_id")),
            "target_photo_id": payload.get("target_photo_id"),
            "actor_photo_id": payload.get("actor_photo_id"),
            "event_type": payload.get("event_type"),
            "relation_label": payload.get("relation_label"),
            "tone_label": payload.get("tone_label"),
            "topics_json": payload.get("topics_json"),
            "salient_claim": payload.get("salient_claim"),
            "event_text": payload.get("event_text", payload.get("description")),
            "weight": payload.get("weight", 1.0),
            "importance": payload.get("importance", 0.0),
            "last_accessed_round": payload.get("last_accessed_round"),
            "access_count": payload.get("access_count", 0),
        }
        if normalized["topics_json"] is None and payload.get("topics") is not None:
            normalized["topics_json"] = json.dumps(payload.get("topics"))
        try:
            normalized["round_id"] = int(normalized["round_id"])
        except (TypeError, ValueError):
            normalized["round_id"] = 0
        if normalized["last_accessed_round"] is None:
            normalized["last_accessed_round"] = normalized["round_id"]

        allowed_keys = {column.name for column in MemoryInteractionEvent.__table__.columns}
        normalized = {key: value for key, value in normalized.items() if key in allowed_keys}
        with self.session_scope() as session:
            event = MemoryInteractionEvent(**normalized)
            session.add(event)
            session.flush()
            return int(event.id)

    def get_memory_events(self, run_id: str, agent_user_id: str, limit: int = 100) -> List[dict]:
        with self.session_scope() as session:
            rows = (
                session.query(MemoryInteractionEvent)
                .filter_by(run_id=run_id, actor_user_id=agent_user_id)
                .order_by(MemoryInteractionEvent.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    **{column.name: getattr(row, column.name) for column in MemoryInteractionEvent.__table__.columns},
                    "agent_user_id": row.actor_user_id,
                    "other_user_id": row.target_user_id,
                    "description": row.event_text,
                }
                for row in rows
            ]

    def add_report(
        self, reporter_id: str, content_id: str, content_type: str, reason: str, round_id: str
    ) -> str:
        with self.session_scope() as session:
            report_id = str(uuid.uuid4())
            session.add(
                Reported(
                    id=report_id,
                    reporter_id=reporter_id,
                    content_id=content_id,
                    content_type=content_type,
                    reason=reason,
                    round_id=round_id,
                )
            )
            return report_id

    def add_follow_request(self, follower_id: str, user_id: str) -> str:
        with self.session_scope() as session:
            request_id = str(uuid.uuid4())
            session.add(FollowRequest(id=request_id, follower_id=follower_id, user_id=user_id))
            return request_id

    def review_follow_request(self, follower_id: str, user_id: str, action: str, round_id: str) -> bool:
        with self.session_scope() as session:
            request = (
                session.query(FollowRequest)
                .filter_by(follower_id=follower_id, user_id=user_id, status="pending")
                .first()
            )
            if request is None:
                return False
            normalized = str(action or "").lower()
            request.status = "accepted" if normalized == "accept" else "rejected"
            if request.status == "accepted":
                self.add_follow(user_id=user_id, follower_id=follower_id, round_id=round_id)
            return True

    def get_pending_follow_requests(self, user_id: str) -> List[dict]:
        with self.session_scope() as session:
            rows = session.query(FollowRequest).filter_by(user_id=user_id, status="pending").all()
            return [
                {column.name: getattr(row, column.name) for column in FollowRequest.__table__.columns}
                for row in rows
            ]

    def save_photo(self, user_id: str, photo_id: str) -> str:
        with self.session_scope() as session:
            save_id = str(uuid.uuid4())
            session.add(
                SavedPhoto(
                    id=save_id,
                    user_id=user_id,
                    photo_id=photo_id,
                    round=self._latest_round_id(session),
                )
            )
            return save_id

    def get_saved_photos(self, user_id: str, limit: int = 30) -> List[dict]:
        with self.session_scope() as session:
            rows = (
                session.query(SavedPhoto)
                .join(Round, Round.id == SavedPhoto.round)
                .filter_by(user_id=user_id)
                .order_by(Round.day.desc(), Round.hour.desc(), SavedPhoto.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {column.name: getattr(row, column.name) for column in SavedPhoto.__table__.columns}
                for row in rows
            ]

    def send_dm(self, sender_id: str, recipient_id: str, content: str, photo_id: str = None) -> str:
        with self.session_scope() as session:
            dm_id = str(uuid.uuid4())
            session.add(
                DirectMessage(
                    id=dm_id,
                    sender_id=sender_id,
                    recipient_id=recipient_id,
                    body=content,
                    photo_id=photo_id,
                )
            )
            return dm_id

    def get_dms(self, user_id: str, limit: int = 50) -> List[dict]:
        with self.session_scope() as session:
            rows = (
                session.query(DirectMessage)
                .join(Round, Round.id == DirectMessage.round)
                .filter(
                    or_(
                        DirectMessage.sender_id == user_id,
                        DirectMessage.recipient_id == user_id,
                    )
                )
                .order_by(Round.day.desc(), Round.hour.desc(), DirectMessage.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {column.name: getattr(row, column.name) for column in DirectMessage.__table__.columns}
                for row in rows
            ]

    def get_explore_feed(self, user_id: str, limit: int = 30) -> List[dict]:
        from YPhotoSharing.YServer.recsys.explore_recsys import ExploreRecsys

        with self.session_scope() as session:
            followed_subq = (
                session.query(Follow.user_id)
                .filter_by(follower_id=user_id, action="follow")
                .scalar_subquery()
            )
            rows = (
                session.query(Photo)
                .join(Round, Round.id == Photo.round)
                .filter(
                    Photo.user_id.notin_(followed_subq),
                    Photo.user_id != user_id,
                    Photo.is_removed == 0,
                )
                .order_by(Round.day.desc(), Round.hour.desc(), Photo.created_at.desc())
                .limit(100)
                .all()
            )
            candidates = [
                {column.name: getattr(photo, column.name) for column in Photo.__table__.columns}
                for photo in rows
            ]
            ranker = ExploreRecsys()
            return ranker.evaluate(user_id, "", session, candidates, limit)

    def get_hashtag_feed(self, hashtag: str, limit: int = 30) -> List[dict]:
        with self.session_scope() as session:
            rows = (
                session.query(Photo)
                .join(Round, Round.id == Photo.round)
                .filter(Photo.caption.like(f"%#{hashtag}%"), Photo.is_removed == 0)
                .order_by(Round.day.desc(), Round.hour.desc(), Photo.created_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {column.name: getattr(photo, column.name) for column in Photo.__table__.columns}
                for photo in rows
            ]

    def get_latest_agent_opinion(self, user_id: str, topic_id: str) -> Optional[float]:
        with self.session_scope() as session:
            query = session.query(UserOpinion).filter(UserOpinion.user_id == user_id)
            query = query.filter((UserOpinion.topic == topic_id) | (UserOpinion.topic_id == topic_id))
            opinion = query.order_by(UserOpinion.round_id.desc()).first()
            return opinion.opinion_score if opinion else None

    def update_comment_sentiment(self, comment_id: str, sentiment_score: float) -> bool:
        with self.session_scope() as session:
            comment = session.query(Comment).filter_by(id=comment_id).first()
            if comment is None:
                return False
            comment.sentiment_score = sentiment_score
            return True

    def update_user_opinion(
        self,
        user_id: str,
        topic: str,
        opinion_score: float,
        round_id: str,
        topic_id: Optional[str] = None,
        opinion_label: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> str:
        opinion_id = str(uuid.uuid4())
        with self.session_scope() as session:
            existing = (
                session.query(UserOpinion)
                .filter(
                    UserOpinion.user_id == user_id,
                    UserOpinion.topic == topic,
                    UserOpinion.round_id == round_id,
                )
                .first()
            )
            if existing is not None:
                existing.topic_id = topic_id
                existing.opinion_score = opinion_score
                existing.opinion_label = opinion_label
                existing.model_name = model_name
                return existing.id
            session.add(
                UserOpinion(
                    id=opinion_id,
                    user_id=user_id,
                    topic_id=topic_id,
                    topic=topic,
                    round_id=round_id,
                    opinion_score=opinion_score,
                    opinion_label=opinion_label,
                    model_name=model_name,
                )
            )
        return opinion_id

    def get_user_opinions(self, user_id: str) -> dict:
        with self.session_scope() as session:
            rows = (
                session.query(UserOpinion)
                .join(Round, UserOpinion.round_id == Round.id)
                .filter(UserOpinion.user_id == user_id)
                .order_by(Round.day.desc(), Round.hour.desc())
                .all()
            )
            result = {}
            for row in rows:
                if row.topic not in result:
                    result[row.topic] = row.opinion_score
            return result

    def get_opinion_paths(self, user_id: str, topic: Optional[str] = None, limit: int = 100) -> List[dict]:
        with self.session_scope() as session:
            query = session.query(OpinionPath).filter_by(user_id=user_id)
            if topic is not None:
                query = query.filter_by(topic=topic)
            rows = query.order_by(OpinionPath.created_at.desc()).limit(limit).all()
            return [
                {column.name: getattr(row, column.name) for column in OpinionPath.__table__.columns}
                for row in rows
            ]

    def record_opinion_path(
        self,
        user_id: str,
        topic: str,
        topic_id: Optional[str],
        round_id: str,
        model_name: str,
        source_score: Optional[float],
        source_label: Optional[str],
        target_score: float,
        target_label: Optional[str],
        transition: str,
        direction: Optional[str] = None,
        evaluation_scope: Optional[str] = None,
        parent_post_id: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> str:
        path_id = str(uuid.uuid4())
        with self.session_scope() as session:
            session.add(
                OpinionPath(
                    id=path_id,
                    user_id=user_id,
                    topic_id=topic_id,
                    topic=topic,
                    round_id=round_id,
                    model_name=model_name,
                    evaluation_scope=evaluation_scope,
                    source_score=source_score,
                    source_label=source_label,
                    target_score=target_score,
                    target_label=target_label,
                    transition=transition,
                    direction=direction,
                    parent_post_id=parent_post_id,
                    actor_user_id=actor_user_id,
                    payload_json=payload_json,
                )
            )
        return path_id

    def set_stress_reward_variations(
        self,
        user_id: str,
        round_id: str,
        variations: List[Dict[str, Any]],
        action_name: Optional[str] = None,
    ) -> int:
        written = 0
        with self.session_scope() as session:
            for variation in variations:
                session.add(
                    StressReward(
                        id=str(uuid.uuid4()),
                        uid=user_id,
                        variable=variation["variable"],
                        value=float(variation["value"]),
                        type="variation",
                        action=action_name,
                        tid=round_id,
                    )
                )
                written += 1
        return written

    def _compute_stress_reward_aggregate(
        self, session: Session, user_id: str, current_round_id: str, backward_rounds: int
    ) -> Dict[str, float]:
        current_round = self._get_round(session, current_round_id)
        current_index = self._round_index(current_round)
        lower_bound = current_index - max(0, backward_rounds)
        rows = (
            session.query(StressReward, Round)
            .join(Round, Round.id == StressReward.tid)
            .filter(StressReward.uid == user_id, StressReward.type == "variation")
            .all()
        )
        aggregate = {"stress": 0.0, "reward": 0.0}
        for event, round_obj in rows:
            idx = self._round_index(round_obj)
            if lower_bound <= idx <= current_index:
                aggregate[event.variable] = aggregate.get(event.variable, 0.0) + float(event.value)
        for key, value in aggregate.items():
            aggregate[key] = max(0.0, min(1.0, value))
        return aggregate

    def get_stress_reward(
        self, user_id: str, current_round_id: str, backward_rounds: int = 24
    ) -> Dict[str, Any]:
        with self.session_scope() as session:
            aggregate = self._compute_stress_reward_aggregate(
                session, user_id, current_round_id, backward_rounds
            )
            for variable, value in aggregate.items():
                existing = (
                    session.query(StressReward)
                    .filter(
                        StressReward.uid == user_id,
                        StressReward.type == "aggregate",
                        StressReward.tid == current_round_id,
                        StressReward.variable == variable,
                    )
                    .first()
                )
                if existing is None:
                    session.add(
                        StressReward(
                            id=str(uuid.uuid4()),
                            uid=user_id,
                            variable=variable,
                            value=value,
                            type="aggregate",
                            action=None,
                            tid=current_round_id,
                        )
                    )
                else:
                    existing.value = value
        return {"status": 200, **aggregate}

    def get_home_feed(self, user_id: str, limit: int = 30) -> List[dict]:
        from YPhotoSharing.YServer.recsys.feed_ranking_service import FeedRankingService

        with self.session_scope() as session:
            author_rows = (
                session.query(Follow.user_id)
                .filter(Follow.follower_id == user_id, Follow.action == "follow")
                .all()
            )
            author_ids = [row[0] for row in author_rows]
            if not author_ids:
                return []
            photos = session.query(Photo).filter(Photo.user_id.in_(author_ids)).all()
            candidates = [
                {column.name: getattr(photo, column.name) for column in Photo.__table__.columns}
                for photo in photos
            ]
            ranking = FeedRankingService(session)
            return ranking.rank_feed(user_id, candidates)[:limit]
