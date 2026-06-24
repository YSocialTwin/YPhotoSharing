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

from sqlalchemy import create_engine
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
            s.add(User_mgmt(id=uid, **{k: v for k, v in user_data.items() if k != "id"}))
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
        with self.session_scope() as s:
            pid = photo_data.get("id") or str(uuid.uuid4())
            s.add(Photo(id=pid, **{k: v for k, v in photo_data.items() if k != "id"}))
            
            # Phase 4: Handle sharing (increment parent num_shares)
            parent_id = photo_data.get("parent_photo_id")
            if parent_id:
                parent = s.query(Photo).filter_by(id=parent_id).first()
                if parent:
                    parent.num_shares += 1
                    
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
        with self.session_scope() as s:
            eid = str(uuid.uuid4())
            s.add(PhotoEmotion(id=eid, photo_id=photo_id, emotion=emotion))
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
            s.add(Story(id=sid, **{k: v for k, v in story_data.items() if k != "id"}))
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
            event = MemoryInteractionEvent(**event_data)
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

    def update_user_opinion(self, user_id: str, topic: str, opinion_score: float) -> bool:
        with self.session_scope() as s:
            op = s.query(UserOpinion).filter_by(user_id=user_id, topic=topic).first()
            if op:
                op.opinion_score = opinion_score
            else:
                s.add(UserOpinion(id=str(uuid.uuid4()), user_id=user_id, topic=topic, opinion_score=opinion_score))
            return True

    def get_user_opinions(self, user_id: str) -> dict:
        with self.session_scope() as s:
            ops = s.query(UserOpinion).filter_by(user_id=user_id).all()
            return {op.topic: op.opinion_score for op in ops}
