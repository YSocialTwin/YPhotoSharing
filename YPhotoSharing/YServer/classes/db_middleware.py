from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Base,
    Emotion,
    Follow,
    Hashtag,
    Interest,
    OpinionPath,
    Photo,
    PhotoEmotion,
    PhotoHashtag,
    PhotoTopic,
    Round,
    StressReward,
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
        return True

    def add_post_toxicity(self, toxicity_data: Dict[str, Any]) -> bool:
        payload = {"id": str(uuid.uuid4()), **dict(toxicity_data)}
        self.posts_toxicity.append(payload)
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
        with self.session_scope() as session:
            existing = session.query(User_mgmt).filter(User_mgmt.id == user_id).first()
            if existing is None:
                session.add(User_mgmt(**payload))
        return user_id

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
                .filter(Photo.user_id == user_id)
                .order_by(Photo.created_at.desc())
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [
                {column.name: getattr(photo, column.name) for column in Photo.__table__.columns}
                for photo in photos
            ]

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

    def add_photo_emotion(self, photo_id: str, emotion: str) -> bool:
        emotion_obj = self.get_emotion_by_name(emotion)
        if emotion_obj is None:
            return False
        return self.add_post_emotion(photo_id, emotion_obj["id"])

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

    def get_latest_agent_opinion(self, user_id: str, topic_id: str) -> Optional[float]:
        with self.session_scope() as session:
            query = session.query(UserOpinion).filter(UserOpinion.user_id == user_id)
            query = query.filter((UserOpinion.topic == topic_id) | (UserOpinion.topic_id == topic_id))
            opinion = query.order_by(UserOpinion.round_id.desc()).first()
            return opinion.opinion_score if opinion else None

    def update_user_opinion(
        self,
        user_id: str,
        topic: str,
        topic_id: Optional[str],
        opinion_score: float,
        round_id: str,
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
