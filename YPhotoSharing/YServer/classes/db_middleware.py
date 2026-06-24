"""
Database middleware for YPhotoSharing server.

Provides a thread-safe session factory and high-level helper methods
for reading and writing Instagram-like simulation data.
Only the server component may import this module.
"""

import json
import logging
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional

from sqlalchemy import create_engine, and_, or_, func
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from YPhotoSharing.YServer.classes.models import (
    Base,
    Comment,
    DirectMessage,
    Emotion,
    Follow,
    Hashtag,
    Interest,
    MemoryInteractionEvent,
    MemorySocialCard,
    Mention,
    OpinionPath,
    Photo,
    PhotoEmotion,
    PhotoHashtag,
    PhotoTopic,
    Reaction,
    Recommendation,
    Reported,
    Round,
    Story,
    StoryView,
    TrendingHashtag,
    User_mgmt,
    UserInterest,
    UserOpinion,
)

logger = logging.getLogger(__name__)


def build_connection_string(db_config: dict, config_path=None) -> str:
    """Build a SQLAlchemy connection string from the database configuration dict."""
    from pathlib import Path
    from urllib.parse import quote_plus

    db_type = db_config.get("type", "sqlite")

    if db_type == "sqlite":
        sqlite_config = db_config.get("sqlite", {})
        db_filename = sqlite_config.get("filename", "yphotosharing.db")
        if config_path:
            db_path = Path(config_path) / db_filename
        else:
            db_path = Path(db_filename)
        return f"sqlite:///{db_path}"

    elif db_type == "postgresql":
        pg = db_config.get("postgresql", {})
        pwd = quote_plus(pg.get("password", "")) if pg.get("password") else ""
        auth = f"{pg.get('username', 'postgres')}:{pwd}@" if pwd else f"{pg.get('username', 'postgres')}@"
        return (
            f"postgresql+psycopg2://{auth}"
            f"{pg.get('host', 'localhost')}:{pg.get('port', 5432)}"
            f"/{pg.get('database', 'yphotosharing')}"
        )

    elif db_type == "mysql":
        my = db_config.get("mysql", {})
        pwd = quote_plus(my.get("password", "")) if my.get("password") else ""
        auth = f"{my.get('username', 'root')}:{pwd}@" if pwd else f"{my.get('username', 'root')}@"
        return (
            f"mysql+pymysql://{auth}"
            f"{my.get('host', 'localhost')}:{my.get('port', 3306)}"
            f"/{my.get('database', 'yphotosharing')}"
        )

    raise ValueError(f"Unsupported database type: {db_type}")


class DatabaseMiddleware:
    """
    High-level database access layer for the YPhotoSharing server.

    Thread-safe via SQLAlchemy's scoped session.  The server actor is the
    sole consumer; clients communicate exclusively through Ray remote calls.
    """

    def __init__(self, db_config: dict, config_path=None):
        conn_str = build_connection_string(db_config, config_path)
        self._engine = create_engine(conn_str, echo=False)
        self._SessionFactory = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)
        logger.info(f"DatabaseMiddleware initialised ({db_config.get('type', 'sqlite')})")

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session: Session = self._SessionFactory()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            logger.error(f"DB error: {exc}")
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Round helpers
    # ------------------------------------------------------------------

    def get_or_create_round(self, day: int, hour: int) -> str:
        """Return the UUID for (day, hour), creating it if necessary."""
        with self.session_scope() as s:
            row = s.query(Round).filter_by(day=day, hour=hour).first()
            if row:
                return row.id
            new_id = str(uuid.uuid4())
            s.add(Round(id=new_id, day=day, hour=hour))
            return new_id

    # ------------------------------------------------------------------
    # User helpers
    # ------------------------------------------------------------------

    def create_user(self, user_data: dict) -> str:
        """Insert a new user; returns the user UUID."""
        with self.session_scope() as s:
            uid = user_data.get("id") or str(uuid.uuid4())
            
            valid_keys = {c.name for c in User_mgmt.__table__.columns}
            filtered_data = {k: v for k, v in user_data.items() if k in valid_keys and k != "id"}
            
            user_obj = User_mgmt(id=uid, **filtered_data)
            s.add(user_obj)
            return uid

    def get_user(self, user_id: str) -> Optional[dict]:
        with self.session_scope() as s:
            row = s.query(User_mgmt).filter_by(id=user_id).first()
            if not row:
                return None
            return {c.name: getattr(row, c.name) for c in row.__table__.columns}

    def get_user_by_username(self, username: str) -> Optional[dict]:
        with self.session_scope() as s:
            row = s.query(User_mgmt).filter_by(username=username).first()
            if not row:
                return None
            return {c.name: getattr(row, c.name) for c in row.__table__.columns}

    def list_users(self, limit: int = 100, offset: int = 0) -> List[dict]:
        with self.session_scope() as s:
            rows = s.query(User_mgmt).limit(limit).offset(offset).all()
            return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]

    def update_satisfaction(self, user_id: str, delta: float) -> float:
        """Update and return the new satisfaction score. Cap at 0 and 100."""
        with self.session_scope() as s:
            user = s.query(User_mgmt).filter_by(id=user_id).first()
            if not user:
                return 0.0
            new_score = max(0.0, min(100.0, user.satisfaction_score + delta))
            user.satisfaction_score = new_score
            if new_score <= 10.0:
                user.is_churned = True
            return new_score

    def set_churn_state(self, user_id: str, is_churned: bool) -> bool:
        with self.session_scope() as s:
            user = s.query(User_mgmt).filter_by(id=user_id).first()
            if not user:
                return False
            user.is_churned = is_churned
            return True

    def update_last_active_day(self, user_id: str, day: int) -> bool:
        with self.session_scope() as s:
            user = s.query(User_mgmt).filter_by(id=user_id).first()
            if not user:
                return False
            user.last_active_day = int(day)
            return True

    # ------------------------------------------------------------------
    # Follow helpers
    # ------------------------------------------------------------------

    def add_follow(self, user_id: str, follower_id: str, round_id: str) -> str:
        with self.session_scope() as s:
            fid = str(uuid.uuid4())
            s.add(Follow(id=fid, user_id=user_id, follower_id=follower_id, action="follow", round=round_id))
            return fid

    def remove_follow(self, user_id: str, follower_id: str, round_id: str) -> bool:
        with self.session_scope() as s:
            row = s.query(Follow).filter_by(user_id=user_id, follower_id=follower_id).first()
            if row:
                row.action = "unfollow"
                row.round = round_id
                return True
            return False

    def get_followers(self, user_id: str) -> List[str]:
        with self.session_scope() as s:
            rows = s.query(Follow).filter_by(user_id=user_id, action="follow").all()
            return [r.follower_id for r in rows]

    def get_following(self, user_id: str) -> List[str]:
        with self.session_scope() as s:
            rows = s.query(Follow).filter_by(follower_id=user_id, action="follow").all()
            return [r.user_id for r in rows]

    # ------------------------------------------------------------------
    # Photo helpers
    # ------------------------------------------------------------------

    def create_photo(self, photo_data: dict) -> str:
        import re
        from YPhotoSharing.YServer.classes.models import Hashtag, PhotoHashtag
        with self.session_scope() as s:
            pid = photo_data.get("id") or str(uuid.uuid4())
            valid_keys = {c.name for c in Photo.__table__.columns}
            filtered_data = {k: v for k, v in photo_data.items() if k in valid_keys and k != "id"}
            s.add(Photo(id=pid, **filtered_data))
            
            # Extract and save hashtags from caption
            caption = photo_data.get("caption", "")
            if caption:
                extracted_hashtags = set(re.findall(r"#(\w+)", caption))
                for h_text in extracted_hashtags:
                    h_text = h_text.lower()
                    h_obj = s.query(Hashtag).filter_by(hashtag=h_text).first()
                    if not h_obj:
                        h_obj = Hashtag(id=str(uuid.uuid4()), hashtag=h_text)
                        s.add(h_obj)
                        s.flush()
                    s.add(PhotoHashtag(id=str(uuid.uuid4()), photo_id=pid, hashtag_id=h_obj.id))

            # Phase 4: Handle sharing (increment parent num_shares)
            parent_id = photo_data.get("parent_photo_id")
            if parent_id:
                parent = s.query(Photo).filter_by(id=parent_id).first()
                if parent:
                    parent.num_shares += 1

            self._persist_photo_topics(s, pid, photo_data)

            # Extract hashtags
            caption = photo_data.get("caption", "")
            tags = set(re.findall(r"#(\w+)", caption))
            for tag in tags:
                tag = tag.lower()
                hid = f"hash_{tag}"
                row = s.query(Hashtag).filter_by(hashtag=tag).first()
                if not row:
                    s.add(Hashtag(id=hid, hashtag=tag))
                
                # Tag photo
                s.add(PhotoHashtag(id=str(uuid.uuid4()), photo_id=pid, hashtag_id=hid))
                    
            return pid

    def add_photo_emotion(self, photo_id: str, emotion: str) -> bool:
        from YPhotoSharing.YServer.classes.models import Emotion
        with self.session_scope() as s:
            emotion_obj = s.query(Emotion).filter_by(emotion=emotion).first()
            if not emotion_obj:
                emotion_obj = Emotion(id=str(uuid.uuid4()), emotion=emotion)
                s.add(emotion_obj)
                s.flush()
            eid = str(uuid.uuid4())
            s.add(PhotoEmotion(id=eid, photo_id=photo_id, emotion_id=emotion_obj.id))
            return True

    def get_photo(self, photo_id: str) -> Optional[dict]:
        with self.session_scope() as s:
            row = s.query(Photo).filter_by(id=photo_id).first()
            if not row:
                return None
            return {c.name: getattr(row, c.name) for c in row.__table__.columns}

    def get_user_photos(self, user_id: str, limit: int = 20, offset: int = 0) -> List[dict]:
        with self.session_scope() as s:
            rows = (
                s.query(Photo)
                .filter_by(user_id=user_id)
                .order_by(Photo.created_at.desc())
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]

    def delete_photo(self, photo_id: str) -> bool:
        with self.session_scope() as s:
            row = s.query(Photo).filter_by(id=photo_id).first()
            if row:
                row.deleted_at = datetime.utcnow()
                return True
            return False

    # ------------------------------------------------------------------
    # Reaction helpers
    # ------------------------------------------------------------------

    def add_reaction(self, user_id: str, photo_id: str, reaction_type: str, round_id: str) -> str:
        with self.session_scope() as s:
            existing = s.query(Reaction).filter_by(user_id=user_id, photo_id=photo_id).first()
            if existing:
                existing.reaction_type = reaction_type
                existing.round = round_id
                return existing.id
            rid = str(uuid.uuid4())
            s.add(Reaction(id=rid, user_id=user_id, photo_id=photo_id,
                           reaction_type=reaction_type, round=round_id))
            # Update denormalised count
            photo = s.query(Photo).filter_by(id=photo_id).first()
            if photo:
                photo.num_likes = (photo.num_likes or 0) + 1
            return rid

    def remove_reaction(self, user_id: str, photo_id: str) -> bool:
        with self.session_scope() as s:
            row = s.query(Reaction).filter_by(user_id=user_id, photo_id=photo_id).first()
            if row:
                s.delete(row)
                photo = s.query(Photo).filter_by(id=photo_id).first()
                if photo and photo.num_likes:
                    photo.num_likes = max(0, photo.num_likes - 1)
                return True
            return False

    # ------------------------------------------------------------------
    # Comment helpers
    # ------------------------------------------------------------------

    def add_comment(self, user_id: str, photo_id: str, body: str,
                    round_id: str, parent_comment_id: str = None) -> str:
        with self.session_scope() as s:
            cid = str(uuid.uuid4())
            s.add(Comment(id=cid, user_id=user_id, photo_id=photo_id,
                          body=body, round=round_id, parent_comment_id=parent_comment_id))
            photo = s.query(Photo).filter_by(id=photo_id).first()
            if photo:
                photo.num_comments = (photo.num_comments or 0) + 1
            return cid

    def get_comments(self, photo_id: str, limit: int = 50, offset: int = 0) -> List[dict]:
        with self.session_scope() as s:
            rows = (
                s.query(Comment)
                .filter_by(photo_id=photo_id, is_deleted=False, parent_comment_id=None)
                .order_by(Comment.created_at)
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]

    # ------------------------------------------------------------------
    # Story helpers
    # ------------------------------------------------------------------

    def create_story(self, story_data: dict) -> str:
        with self.session_scope() as s:
            sid = story_data.get("id") or str(uuid.uuid4())
            valid_keys = {c.name for c in Story.__table__.columns}
            filtered_data = {k: v for k, v in story_data.items() if k in valid_keys and k != "id"}
            s.add(Story(id=sid, **filtered_data))
            return sid

    def record_story_view(self, story_id: str, viewer_id: str) -> bool:
        with self.session_scope() as s:
            existing = s.query(StoryView).filter_by(story_id=story_id, viewer_id=viewer_id).first()
            if existing:
                return False
            s.add(StoryView(id=str(uuid.uuid4()), story_id=story_id, viewer_id=viewer_id))
            story = s.query(Story).filter_by(id=story_id).first()
            if story:
                story.view_count = (story.view_count or 0) + 1
            return True

    def get_recent_stories(self, user_id: str, limit: int = 50) -> List[dict]:
        from datetime import datetime, timedelta
        with self.session_scope() as s:
            following = s.query(Follow.user_id).filter_by(follower_id=user_id).all()
            following_ids = [f[0] for f in following]
            if not following_ids:
                return []
            
            # Simple heuristic: last 50 stories from followed users
            rows = (
                s.query(Story)
                .filter(Story.user_id.in_(following_ids))
                .order_by(Story.created_at.desc())
                .limit(limit)
                .all()
            )
            return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]

    # ------------------------------------------------------------------
    # Recommendation helpers
    # ------------------------------------------------------------------

    def add_recommendation(self, user_id: str, photo_ids: List[str], round_id: str) -> str:
        with self.session_scope() as s:
            rid = str(uuid.uuid4())
            s.add(Recommendation(id=rid, user_id=user_id,
                                 photo_ids=json.dumps(photo_ids), round=round_id))
            return rid

    def get_recommendation(self, user_id: str, round_id: str) -> Optional[List[str]]:
        with self.session_scope() as s:
            row = (s.query(Recommendation)
                   .filter_by(user_id=user_id, round=round_id)
                   .first())
            if not row:
                return None
            return json.loads(row.photo_ids or "[]")

    # ------------------------------------------------------------------
    # Hashtag helpers
    # ------------------------------------------------------------------

    def get_or_create_hashtag(self, tag: str) -> str:
        with self.session_scope() as s:
            row = s.query(Hashtag).filter_by(hashtag=tag).first()
            if row:
                return row.id
            hid = str(uuid.uuid4())
            s.add(Hashtag(id=hid, hashtag=tag))
            return hid

    def tag_photo(self, photo_id: str, hashtag_id: str) -> None:
        with self.session_scope() as s:
            existing = s.query(PhotoHashtag).filter_by(
                photo_id=photo_id, hashtag_id=hashtag_id
            ).first()
            if not existing:
                s.add(PhotoHashtag(id=str(uuid.uuid4()),
                                   photo_id=photo_id, hashtag_id=hashtag_id))

    # ------------------------------------------------------------------
    # Feed helpers (chronological home feed for a user)
    # ------------------------------------------------------------------

    def get_home_feed(self, user_id: str, limit: int = 30) -> List[dict]:
        """Return the ML ranked photos from users that user_id follows."""
        from YPhotoSharing.YServer.recsys.feed_ranking_service import FeedRankingService
        with self.session_scope() as s:
            following_ids = [
                r.user_id for r in
                s.query(Follow).filter_by(follower_id=user_id, action="follow").all()
            ]
            if not following_ids:
                return []
            
            # Fetch a larger candidate pool to rank
            rows = (
                s.query(Photo)
                .join(User_mgmt, Photo.user_id == User_mgmt.id)
                .filter(
                    Photo.user_id.in_(following_ids),
                    Photo.deleted_at.is_(None),
                    Photo.is_removed == 0,
                    User_mgmt.is_shadow_banned == 0
                )
                .order_by(Photo.created_at.desc())
                .limit(100) # Pre-filter candidate generation
                .all()
            )
            
            candidates = [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]
            
            # Phase 9: Rank with FeedRankingService
            ranker = FeedRankingService(s)
            ranked = ranker.rank_feed(user_id, candidates)
            
            return ranked[:limit]

    # ------------------------------------------------------------------
    # Memory helpers
    # ------------------------------------------------------------------

    def add_memory_event(self, event_data: dict) -> int:
        with self.session_scope() as s:
            if "agent_user_id" in event_data:
                event_data["actor_user_id"] = event_data.pop("agent_user_id")
            
            valid_keys = {c.name for c in MemoryInteractionEvent.__table__.columns}
            filtered_data = {k: v for k, v in event_data.items() if k in valid_keys}
            
            event = MemoryInteractionEvent(**filtered_data)
            s.add(event)
            s.flush()
            return event.id

    def get_memory_events(self, run_id: str, agent_user_id: str,
                          limit: int = 100) -> List[dict]:
        with self.session_scope() as s:
            rows = (
                s.query(MemoryInteractionEvent)
                .filter_by(run_id=run_id, actor_user_id=agent_user_id)
                .order_by(MemoryInteractionEvent.created_at.desc())
                .limit(limit)
                .all()
            )
            return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]

    # ------------------------------------------------------------------
    # Interest helpers
    # ------------------------------------------------------------------

    def get_or_create_interest(self, interest_name: str) -> str:
        with self.session_scope() as s:
            obj = s.query(Interest).filter_by(interest=interest_name).first()
            if obj:
                return obj.iid
            new_id = str(uuid.uuid4())
            s.add(Interest(iid=new_id, interest=interest_name))
            return new_id

    # ------------------------------------------------------------------
    # Moderation & Reporting
    # ------------------------------------------------------------------

    def add_report(self, reporter_id: str, content_id: str, content_type: str, reason: str, round_id: str):
        with self.session_scope() as s:
            report_id = str(uuid.uuid4())
            s.add(Reported(
                id=report_id,
                reporter_id=reporter_id,
                content_id=content_id,
                content_type=content_type,
                reason=reason,
                round_id=round_id
            ))
            return report_id

    def set_user_interests(self, user_id: str, interest_ids: List[str], round_id: str) -> None:
        with self.session_scope() as s:
            for iid in interest_ids:
                existing = s.query(UserInterest).filter_by(
                    user_id=user_id, interest_id=iid
                ).first()
                if not existing:
                    s.add(UserInterest(id=str(uuid.uuid4()), user_id=user_id,
                                       interest_id=iid, round_id=round_id))
                                       
    def get_user_interests(self, user_id: str) -> List[str]:
        """Returns the names of all active interests for a user."""
        with self.session_scope() as s:
            rows = s.query(Interest.interest).join(UserInterest).filter(UserInterest.user_id == user_id).all()
            return [r[0] for r in rows]

    # ------------------------------------------------------------------
    # Phase 8 Helpers
    # ------------------------------------------------------------------

    def add_follow_request(self, follower_id: str, user_id: str) -> str:
        from YPhotoSharing.YServer.classes.models import FollowRequest
        with self.session_scope() as s:
            req_id = str(uuid.uuid4())
            req = FollowRequest(id=req_id, follower_id=follower_id, user_id=user_id, status="pending")
            s.add(req)
            return req_id

    def review_follow_request(self, follower_id: str, user_id: str, action: str, round_id: str) -> bool:
        from YPhotoSharing.YServer.classes.models import FollowRequest
        with self.session_scope() as s:
            req = s.query(FollowRequest).filter_by(follower_id=follower_id, user_id=user_id, status="pending").first()
            if not req: return False
            req.status = action # 'accepted' or 'rejected'
            if action == "accepted":
                # Create the follow edge
                existing_follow = s.query(Follow).filter_by(follower_id=follower_id, user_id=user_id, action="follow").first()
                if not existing_follow:
                    s.add(Follow(follower_id=follower_id, user_id=user_id, round=round_id, action="follow"))
            return True

    def get_pending_follow_requests(self, user_id: str) -> List[dict]:
        from YPhotoSharing.YServer.classes.models import FollowRequest
        with self.session_scope() as s:
            reqs = s.query(FollowRequest).filter_by(user_id=user_id, status="pending").all()
            return [{"id": r.id, "follower_id": r.follower_id} for r in reqs]

    def save_photo(self, user_id: str, photo_id: str) -> str:
        from YPhotoSharing.YServer.classes.models import SavedPhoto
        with self.session_scope() as s:
            sid = str(uuid.uuid4())
            s.add(SavedPhoto(id=sid, user_id=user_id, photo_id=photo_id))
            return sid

    def get_saved_photos(self, user_id: str, limit: int = 30) -> List[dict]:
        from YPhotoSharing.YServer.classes.models import SavedPhoto, Photo
        with self.session_scope() as s:
            rows = s.query(Photo).join(SavedPhoto).filter(SavedPhoto.user_id == user_id).order_by(SavedPhoto.created_at.desc()).limit(limit).all()
            return [{"id": r.id, "caption": r.caption} for r in rows]

    def send_dm(self, sender_id: str, recipient_id: str, content: str, photo_id: str = None) -> str:
        from YPhotoSharing.YServer.classes.models import Message
        with self.session_scope() as s:
            mid = str(uuid.uuid4())
            s.add(Message(id=mid, sender_id=sender_id, recipient_id=recipient_id, content=content, photo_id=photo_id))
            return mid

    def get_dms(self, user_id: str, limit: int = 50) -> List[dict]:
        from YPhotoSharing.YServer.classes.models import Message
        from sqlalchemy import or_
        with self.session_scope() as s:
            rows = s.query(Message).filter(or_(Message.sender_id == user_id, Message.recipient_id == user_id)).order_by(Message.created_at.desc()).limit(limit).all()
            return [{"id": r.id, "sender": r.sender_id, "recipient": r.recipient_id, "content": r.content} for r in rows]

    def unfollow_user(self, follower_id: str, user_id: str, round_id: str) -> bool:
        with self.session_scope() as s:
            s.add(Follow(follower_id=follower_id, user_id=user_id, round=round_id, action="unfollow"))
            s.query(Follow).filter_by(follower_id=follower_id, user_id=user_id, action="follow").delete()
            return True

    def get_explore_feed(self, user_id: str, limit: int = 30) -> List[dict]:
        from YPhotoSharing.YServer.classes.models import Photo, Follow
        from YPhotoSharing.YServer.recsys.explore_recsys import ExploreRecsys
        with self.session_scope() as s:
            # Get popular recent posts not from followed users and not removed
            followed_subq = s.query(Follow.user_id).filter_by(follower_id=user_id, action="follow").subquery()
            
            # Fetch a larger candidate pool for CF ranking
            rows = s.query(Photo).filter(
                Photo.user_id.notin_(followed_subq),
                Photo.user_id != user_id, 
                Photo.is_removed == 0
            ).order_by(Photo.created_at.desc()).limit(100).all()
            
            candidates = [{c.name: getattr(p, c.name) for c in p.__table__.columns} for p in rows]
            
            # Phase 9: Rank with ExploreRecsys CF matching
            ranker = ExploreRecsys()
            ranked = ranker.evaluate(user_id, "", s, candidates, limit)
            
            return ranked

    def get_hashtag_feed(self, hashtag: str, limit: int = 30) -> List[dict]:
        from YPhotoSharing.YServer.classes.models import Photo
        with self.session_scope() as s:
            # Simple LIKE query for simulation
            rows = s.query(Photo).filter(Photo.caption.like(f"%#{hashtag}%"), Photo.is_removed == 0).order_by(Photo.created_at.desc()).limit(limit).all()
            return [{"id": p.id, "user_id": p.user_id, "caption": p.caption} for p in rows]

    # ------------------------------------------------------------------
    # Stage 5 & 6 handlers (Sentiment and Opinion)
    # ------------------------------------------------------------------
    
    def update_photo_sentiment(self, photo_id: str, sentiment_score: float) -> bool:
        with self.session_scope() as s:
            photo = s.query(Photo).filter_by(id=photo_id).first()
            if photo:
                photo.sentiment_score = sentiment_score
                return True
            return False

    def update_comment_sentiment(self, comment_id: str, sentiment_score: float) -> bool:
        with self.session_scope() as s:
            comment = s.query(Comment).filter_by(id=comment_id).first()
            if comment:
                comment.sentiment_score = sentiment_score
                return True
            return False

    def update_user_opinion(
        self,
        user_id: str,
        topic: str,
        opinion_score: float,
        round_id: str,
        topic_id: Optional[str] = None,
        opinion_label: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> bool:
        with self.session_scope() as s:
            op = s.query(UserOpinion).filter_by(user_id=user_id, topic=topic, round_id=round_id).first()
            if op:
                op.opinion_score = opinion_score
                if topic_id is not None:
                    op.topic_id = topic_id
                if opinion_label is not None:
                    op.opinion_label = opinion_label
                if model_name is not None:
                    op.model_name = model_name
            else:
                s.add(
                    UserOpinion(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        topic=topic,
                        topic_id=topic_id,
                        round_id=round_id,
                        opinion_score=opinion_score,
                        opinion_label=opinion_label,
                        model_name=model_name,
                    )
                )
            return True

    def get_user_opinions(self, user_id: str) -> dict:
        from YPhotoSharing.YServer.classes.models import Round
        with self.session_scope() as s:
            ops = s.query(UserOpinion).join(Round, UserOpinion.round_id == Round.id).filter(UserOpinion.user_id == user_id).order_by(Round.day.desc(), Round.hour.desc()).all()
            result = {}
            for op in ops:
                if op.topic not in result:
                    result[op.topic] = op.opinion_score
            return result

    def get_opinion_paths(self, user_id: str, topic: Optional[str] = None, limit: int = 100) -> List[dict]:
        with self.session_scope() as s:
            query = s.query(OpinionPath).filter_by(user_id=user_id)
            if topic is not None:
                query = query.filter_by(topic=topic)
            rows = query.order_by(OpinionPath.created_at.desc()).limit(limit).all()
            return [{c.name: getattr(r, c.name) for c in r.__table__.columns} for r in rows]

    # --- Integration Methods for Coordination, Interest Modeling, Opinion Dynamics ---

    def get_photo_topics(self, photo_id: str) -> list:
        from YPhotoSharing.YServer.classes.models import PhotoTopic
        with self.session_scope() as s:
            topics = s.query(PhotoTopic).filter_by(photo_id=photo_id).all()
            return [t.topic_id for t in topics]


    def add_or_get_interest(self, topic: str) -> str:
        with self.session_scope() as s:
            interest = s.query(Interest).filter_by(interest=topic).first()
            if interest:
                return interest.iid
            new_id = str(uuid.uuid4())
            s.add(Interest(iid=new_id, interest=topic))
            return new_id

    def add_photo_topic(self, photo_id: str, topic_id: str) -> bool:
        from YPhotoSharing.YServer.classes.models import PhotoTopic
        with self.session_scope() as s:
            pt = s.query(PhotoTopic).filter_by(photo_id=photo_id, topic_id=topic_id).first()
            if pt:
                return True
            s.add(PhotoTopic(id=str(uuid.uuid4()), photo_id=photo_id, topic_id=topic_id))
            return True

    def compute_interest_counts_in_window(
        self,
        agent_id: str,
        current_round_id: str,
        attention_window: int,
    ) -> dict:
        from YPhotoSharing.YServer.classes.models import UserInterest

        with self.session_scope() as s:
            current_round = s.query(Round).filter_by(id=str(current_round_id)).first()
            if current_round is None:
                return {}

            window_size = max(1, int(attention_window or 1))
            window_rounds = (
                s.query(Round.id)
                .filter(
                    or_(
                        Round.day < current_round.day,
                        and_(Round.day == current_round.day, Round.hour <= current_round.hour),
                    )
                )
                .order_by(Round.day.desc(), Round.hour.desc())
                .limit(window_size)
                .all()
            )
            round_ids = [row[0] for row in window_rounds]
            if not round_ids:
                return {}

            rows = (
                s.query(UserInterest.interest_id, func.count(UserInterest.id))
                .filter(
                    UserInterest.user_id == str(agent_id),
                    UserInterest.round_id.in_(round_ids),
                )
                .group_by(UserInterest.interest_id)
                .all()
            )
            return {interest_id: int(count or 0) for interest_id, count in rows}

    def add_or_get_interests_batch(self, topics: list) -> dict:
        res = {}
        for t in topics:
            res[t] = self.add_or_get_interest(t)
        return res

    def add_user_interests_batch(self, user_interests_data: list) -> int:
        from YPhotoSharing.YServer.classes.models import UserInterest
        with self.session_scope() as s:
            count = 0
            for d in user_interests_data:
                ui = UserInterest(
                    id=str(uuid.uuid4()),
                    user_id=d["user_id"],
                    interest_id=d["interest_id"],
                    interest_score=d.get("interest_score", 0.5)
                )
                s.add(ui)
                count += 1
            return count

    def get_latest_agent_opinion(self, agent_id: str, topic: str) -> Optional[float]:
        with self.session_scope() as s:
            topic_row = s.query(Interest).filter((Interest.iid == topic) | (Interest.interest == topic)).first()
            topic_id = topic_row.iid if topic_row else None
            topic_name = topic_row.interest if topic_row else topic
            query = s.query(UserOpinion).filter(UserOpinion.user_id == agent_id)
            if topic_id:
                query = query.filter((UserOpinion.topic_id == topic_id) | (UserOpinion.topic == topic_name))
            else:
                query = query.filter(UserOpinion.topic == topic_name)
            op = (
                query.join(Round, UserOpinion.round_id == Round.id)
                .order_by(Round.day.desc(), Round.hour.desc())
                .first()
            )
            return op.opinion_score if op else None

    def add_agent_opinion(
        self,
        user_id: str,
        round_id: str,
        topic: str,
        opinion_score: float,
        id_interacted_with: Optional[str] = None,
        id_post: Optional[str] = None,
        topic_id: Optional[str] = None,
        opinion_label: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> bool:
        return self.update_user_opinion(
            user_id=user_id,
            topic=topic,
            opinion_score=opinion_score,
            round_id=round_id,
            topic_id=topic_id,
            opinion_label=opinion_label,
            model_name=model_name,
        )

    def record_opinion_path(
        self,
        user_id: str,
        topic: str,
        round_id: str,
        model_name: str,
        source_score: Optional[float],
        source_label: Optional[str],
        target_score: float,
        target_label: Optional[str],
        transition: str,
        direction: Optional[str] = None,
        evaluation_scope: Optional[str] = None,
        topic_id: Optional[str] = None,
        parent_post_id: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        payload_json: Optional[str] = None,
    ) -> str:
        with self.session_scope() as s:
            pid = str(uuid.uuid4())
            s.add(
                OpinionPath(
                    id=pid,
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
            return pid

    def update_user_archetype(self, user_id: str, archetype: str) -> bool:
        with self.session_scope() as s:
            user = s.query(User_mgmt).filter_by(id=user_id).first()
            if user:
                user.archetype = archetype
                return True
            return False

    def get_all_users(self) -> list:
        with self.session_scope() as s:
            users = s.query(User_mgmt).all()
            return [u.id for u in users]

    def get_or_create_round(self, day: int, slot: int) -> str:
        from YPhotoSharing.YServer.classes.models import Round
        with self.session_scope() as s:
            r = s.query(Round).filter_by(day=day, hour=slot).first()
            if r: return r.id
            new_id = str(uuid.uuid4())
            s.add(Round(id=new_id, day=day, hour=slot))
            return new_id

    def get_topic_name_from_id(self, topic_id: str) -> Optional[str]:
        with self.session_scope() as s:
            topic = s.query(Interest).filter_by(iid=topic_id).first()
            return topic.interest if topic else None

    def _persist_photo_topics(self, session: Session, photo_id: str, photo_data: dict) -> None:
        from YPhotoSharing.YServer.classes.models import PhotoTopic

        topic_ids = []

        raw_topic_ids = photo_data.get("topic_ids") or []
        if isinstance(raw_topic_ids, str):
            raw_topic_ids = [raw_topic_ids]
        for topic_id in raw_topic_ids:
            if topic_id:
                topic_ids.append(str(topic_id))

        raw_topics = photo_data.get("topics")
        if raw_topics is None and photo_data.get("topic") is not None:
            raw_topics = [photo_data.get("topic")]
        if isinstance(raw_topics, str):
            raw_topics = [raw_topics]

        for topic in raw_topics or []:
            if not topic:
                continue
            topic_str = str(topic)
            if topic_str in topic_ids:
                continue
            existing_topic = session.query(Interest).filter_by(iid=topic_str).first()
            if existing_topic:
                topic_ids.append(existing_topic.iid)
            else:
                existing_named_topic = session.query(Interest).filter_by(interest=topic_str).first()
                if existing_named_topic:
                    topic_ids.append(existing_named_topic.iid)
                else:
                    new_topic_id = str(uuid.uuid4())
                    session.add(Interest(iid=new_topic_id, interest=topic_str))
                    topic_ids.append(new_topic_id)

        for topic_id in topic_ids:
            existing = (
                session.query(PhotoTopic)
                .filter_by(photo_id=photo_id, topic_id=topic_id)
                .first()
            )
            if not existing:
                session.add(PhotoTopic(id=str(uuid.uuid4()), photo_id=photo_id, topic_id=topic_id))

    def get_stress_reward(self, agent_id: str, round_id: str, backward_rounds: int = 24) -> dict:
        from YPhotoSharing.YServer.classes.models import StressReward

        try:
            with self.session_scope() as s:
                target_round = s.query(Round).filter_by(id=str(round_id)).first()
                if target_round is None:
                    return {"stress": 0.0, "reward": 0.0, "status": 404}

                target_day = int(target_round.day or 0)
                target_hour = int(target_round.hour or 0)
                window_size = max(1, int(backward_rounds or 24) + 1)

                def _before(day: int, hour: int):
                    return or_(Round.day < day, and_(Round.day == day, Round.hour < hour))

                def _at_or_before(day: int, hour: int):
                    return or_(Round.day < day, and_(Round.day == day, Round.hour <= hour))

                def _at_or_after(day: int, hour: int):
                    return or_(Round.day > day, and_(Round.day == day, Round.hour >= hour))

                window_rounds = (
                    s.query(Round)
                    .filter(_at_or_before(target_day, target_hour))
                    .order_by(Round.day.desc(), Round.hour.desc())
                    .limit(window_size)
                    .all()
                )
                earliest_window_round = window_rounds[-1] if window_rounds else target_round
                earliest_day = int(earliest_window_round.day or 0)
                earliest_hour = int(earliest_window_round.hour or 0)

                payload = {"stress": 0.0, "reward": 0.0, "status": 200}
                for variable in ("stress", "reward"):
                    latest_aggregate_row = (
                        s.query(StressReward, Round)
                        .join(Round, Round.id == StressReward.tid)
                        .filter(
                            StressReward.uid == str(agent_id),
                            StressReward.variable == variable,
                            StressReward.type == "aggregate",
                            _before(target_day, target_hour),
                        )
                        .order_by(Round.day.desc(), Round.hour.desc())
                        .first()
                    )

                    anchor_value = 0.0
                    variation_lower_bound = _at_or_after(earliest_day, earliest_hour)
                    if latest_aggregate_row is not None:
                        latest_aggregate, aggregate_round = latest_aggregate_row
                        anchor_value = float(latest_aggregate.value)
                        variation_lower_bound = _at_or_after(
                            int(aggregate_round.day or 0), int(aggregate_round.hour or 0)
                        )

                    variation_sum = (
                        s.query(func.coalesce(func.sum(StressReward.value), 0.0))
                        .join(Round, Round.id == StressReward.tid)
                        .filter(
                            StressReward.uid == str(agent_id),
                            StressReward.variable == variable,
                            StressReward.type == "variation",
                            variation_lower_bound,
                            _at_or_before(target_day, target_hour),
                        )
                        .scalar()
                    )
                    current_value = max(0.0, min(1.0, anchor_value + float(variation_sum or 0.0)))
                    payload[variable] = current_value

                    existing = (
                        s.query(StressReward)
                        .filter_by(
                            uid=str(agent_id),
                            variable=variable,
                            type="aggregate",
                            tid=str(round_id),
                        )
                        .first()
                    )
                    if existing is None:
                        s.add(
                            StressReward(
                                id=str(uuid.uuid4()),
                                uid=str(agent_id),
                                variable=variable,
                                value=current_value,
                                type="aggregate",
                                action=None,
                                tid=str(round_id),
                            )
                        )
                    else:
                        existing.value = current_value

                return payload
        except Exception:
            logger.exception("Error getting stress/reward for agent %s", agent_id)
            return {"stress": 0.0, "reward": 0.0, "status": 500}

    def set_stress_reward_variations(
        self, user_id: str, round_id: str, variations: list, action_name: Optional[str] = None
    ) -> int:
        from YPhotoSharing.YServer.classes.models import StressReward

        written = 0
        try:
            with self.session_scope() as s:
                for variation in variations or []:
                    variable = str((variation or {}).get("variable") or "").strip().lower()
                    if variable not in {"stress", "reward"}:
                        continue
                    try:
                        value = float((variation or {}).get("value"))
                    except (TypeError, ValueError):
                        continue
                    if value < -1.0 or value > 1.0:
                        continue
                    s.add(
                        StressReward(
                            id=str(uuid.uuid4()),
                            uid=str(user_id),
                            variable=variable,
                            value=value,
                            type="variation",
                            action=action_name,
                            tid=str(round_id),
                        )
                    )
                    written += 1
            return written
        except Exception:
            logger.exception("Error storing stress/reward variations for agent %s", user_id)
            return written

    def consolidate_redis_to_sqlite(self, day: int) -> dict:
        return {"status": "mocked"}

    def cleanup_old_posts_from_redis(self, day: int, slot: int) -> dict:
        return {"status": "mocked"}
