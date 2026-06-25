"""
SQLAlchemy models for YPhotoSharing – an Instagram-like simulation platform.

Schema mirrors the YSimulator database with Instagram-specific extensions:
photo posts, stories, image metadata, visual filters, location tags, etc.
"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base, relationship, backref

Base = declarative_base()


# ================================================
# REFERENCE / LOOKUP TABLES
# ================================================


class Emotion(Base):
    """Emotion types with icon mappings (❤️ 😂 😮 😢 😡 👍)."""

    __tablename__ = "emotions"

    id = Column(String(36), primary_key=True)
    emotion = Column(Text, nullable=False)
    icon = Column(Text)

    photo_emotions = relationship(
        "PhotoEmotion", back_populates="emotion_obj", cascade="all, delete-orphan"
    )


class Hashtag(Base):
    """Hashtag registry for content categorization."""

    __tablename__ = "hashtags"

    id = Column(String(36), primary_key=True)
    hashtag = Column(Text, nullable=False)

    photo_hashtags = relationship(
        "PhotoHashtag", back_populates="hashtag", cascade="all, delete-orphan"
    )


class Interest(Base):
    """Topics/interests for content and user profiling."""

    __tablename__ = "interests"

    iid = Column(String(36), primary_key=True)
    interest = Column(Text)

    user_interests = relationship(
        "UserInterest", back_populates="interest", cascade="all, delete-orphan"
    )
    photo_topics = relationship(
        "PhotoTopic", back_populates="topic", cascade="all, delete-orphan"
    )


class Round(Base):
    """Simulation time tracking (day and hour/slot)."""

    __tablename__ = "rounds"

    id = Column(String(36), primary_key=True)
    day = Column(Integer)
    hour = Column(Integer)

    __table_args__ = (UniqueConstraint("day", "hour", name="uq_round_day_hour"),)

    photos = relationship("Photo", back_populates="round_obj", cascade="all, delete-orphan")
    stories = relationship("Story", back_populates="round_obj", cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="round_obj", cascade="all, delete-orphan")
    recommendations = relationship(
        "Recommendation", back_populates="round_obj", cascade="all, delete-orphan"
    )
    user_interests = relationship(
        "UserInterest", back_populates="round_obj", cascade="all, delete-orphan"
    )


# ================================================
# USER MANAGEMENT
# ================================================


class User_mgmt(Base):
    """
    User management model for experiment participants.

    Stores user profile information including personality traits (Big Five),
    demographic information, preferences and activity settings.
    Compatible with the YSimulator schema.
    """

    __tablename__ = "user_mgmt"

    id = Column(String(36), primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(50))
    password = Column(String(400), nullable=False)
    user_type = Column(Text)
    leaning = Column(Text)
    age = Column(Integer)
    # Big Five personality traits
    oe = Column(Text)   # Openness to Experience
    co = Column(Text)   # Conscientiousness
    ex = Column(Text)   # Extraversion
    ag = Column(Text)   # Agreeableness
    ne = Column(Text)   # Neuroticism
    recsys_type = Column(Text)
    language = Column(Text)
    owner = Column(Text)
    education_level = Column(Text)
    joined_on = Column(String(36), ForeignKey("rounds.id", ondelete="SET NULL"))
    frecsys_type = Column(Text)
    round_actions = Column(Integer, nullable=False, default=3)
    gender = Column(Text)
    nationality = Column(Text)
    toxicity = Column(Text)
    is_page = Column(Integer, nullable=False, default=0)
    left_on = Column(String(36))
    daily_activity_level = Column(Integer, default=1)
    profession = Column(Text)
    activity_profile = Column(Text)
    archetype = Column(Text, default=None)
    # Instagram-specific profile fields
    bio = Column(Text)
    website = Column(String(400))
    profile_picture_url = Column(String(400), default="")
    cover_image = Column(String(400), nullable=False, default="")
    is_private = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    last_active_day = Column(Integer)

    # Phase 4: Influence graph analytics
    influence_score = Column(Float, default=0.0)
    broker_score = Column(Float, default=0.0)
    
    # Phase 5
    stress_level = Column(Float, default=0.0)
    is_shadow_banned = Column(Integer, default=0)

    # Phase 10: Advanced Platform Dynamics
    satisfaction_score = Column(Float, default=100.0)
    is_churned = Column(Boolean, default=False)

    # Relationships
    follows_as_user = relationship(
        "Follow", foreign_keys="Follow.user_id", back_populates="user",
        cascade="all, delete-orphan",
    )
    follows_as_follower = relationship(
        "Follow", foreign_keys="Follow.follower_id", back_populates="follower",
        cascade="all, delete-orphan",
    )
    recommendations = relationship(
        "Recommendation", back_populates="user", cascade="all, delete-orphan"
    )
    user_interests = relationship(
        "UserInterest", back_populates="user", cascade="all, delete-orphan"
    )
    photos = relationship("Photo", back_populates="user", cascade="all, delete-orphan")
    stories = relationship("Story", back_populates="user", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    reactions = relationship("Reaction", back_populates="user", cascade="all, delete-orphan")
    mentions = relationship("Mention", back_populates="user", cascade="all, delete-orphan")
    direct_messages_sent = relationship(
        "DirectMessage", foreign_keys="DirectMessage.sender_id",
        back_populates="sender", cascade="all, delete-orphan",
    )
    direct_messages_received = relationship(
        "DirectMessage", foreign_keys="DirectMessage.recipient_id",
        back_populates="recipient", cascade="all, delete-orphan",
    )
    round_joined = relationship("Round", foreign_keys=[joined_on])


# ================================================
# PHOTO CONTENT
# ================================================


class Photo(Base):
    """
    A photo post – the primary content unit in Instagram-like platforms.

    Supports multi-image carousels (carousel_index), visual filters, geolocation,
    alt text for accessibility and LLM-generated captions.
    """

    __tablename__ = "photos"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False)
    round = Column(String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    image_url = Column(String(400), nullable=False)
    thumbnail_url = Column(String(400))
    caption = Column(Text)
    alt_text = Column(Text)                # accessibility / AI-generated description
    filter_name = Column(String(50))       # e.g. "Clarendon", "Juno", "Lark"
    location_name = Column(String(200))
    latitude = Column(Float)
    longitude = Column(Float)
    is_carousel = Column(Boolean, default=False)
    carousel_index = Column(Integer, default=0)
    parent_photo_id = Column(String(36), ForeignKey("photos.id", ondelete="SET NULL"))
    num_likes = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    num_shares = Column(Integer, default=0)
    is_sponsored = Column(Boolean, default=False)
    embedding = Column(Text, nullable=True)     # JSON-serialized embedding
    aesthetic_score = Column(Float, nullable=True) # 0 to 1 score
    
    # Phase 4: Virality
    viral_score = Column(Float, default=0.0)
    sentiment_score = Column(Float, nullable=True) # Stage 5: Sentiment Annotation
    created_at = Column(DateTime, server_default=func.now())
    deleted_at = Column(DateTime)
    
    # Phase 5
    is_removed = Column(Integer, default=0)
    
    # Phase 7
    media_url = Column(String(400), nullable=True)

    # Relationships
    user = relationship("User_mgmt", back_populates="photos")
    round_obj = relationship("Round", back_populates="photos")
    reactions = relationship("Reaction", back_populates="photo", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="photo", cascade="all, delete-orphan")
    hashtags = relationship("PhotoHashtag", back_populates="photo", cascade="all, delete-orphan")
    topics = relationship("PhotoTopic", back_populates="photo", cascade="all, delete-orphan")
    emotions = relationship("PhotoEmotion", back_populates="photo", cascade="all, delete-orphan")
    mentions = relationship("Mention", back_populates="photo", cascade="all, delete-orphan")
    carousel_children = relationship(
        "Photo",
        foreign_keys=[parent_photo_id],
        backref=backref("carousel_parent", remote_side="Photo.id"),
    )


Index("idx_photos_user_id", Photo.user_id)
Index("idx_photos_round", Photo.round)
Index("idx_photos_created_at", Photo.created_at)


class Story(Base):
    """
    Ephemeral story – visible for 24 h in simulation time.

    Stories can contain images or short video clips (represented as a URL)
    and may have interactive stickers (polls, questions, sliders).
    """

    __tablename__ = "stories"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False)
    round = Column(String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    media_url = Column(String(400), nullable=False)
    media_type = Column(String(20), default="image")   # "image" | "video"
    duration_seconds = Column(Integer, default=5)
    sticker_type = Column(String(50))                  # "poll" | "question" | "slider" | None
    sticker_data = Column(Text)                        # JSON blob for sticker payload
    caption = Column(Text)                             # Optional text on the story
    view_count = Column(Integer, default=0)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User_mgmt", back_populates="stories")
    round_obj = relationship("Round", back_populates="stories")
    views = relationship("StoryView", back_populates="story", cascade="all, delete-orphan")


Index("idx_stories_user_id", Story.user_id)
Index("idx_stories_round", Story.round)


# ================================================
# MODERATION & SAFETY
# ================================================

class ModerationEvent(Base):
    """Records every moderation decision."""
    __tablename__ = "moderation_events"
    
    id = Column(String(36), primary_key=True)
    content_id = Column(String(36), nullable=False, index=True)
    content_type = Column(String(20), nullable=False) # 'photo' or 'comment'
    action_taken = Column(String(20), nullable=False) # 'remove', 'shadow-ban', 'warn'
    reason = Column(Text)
    confidence = Column(Float, default=1.0)
    round_id = Column(String(36))


class Reported(Base):
    """User-to-user content reports."""
    __tablename__ = "reported"
    
    id = Column(String(36), primary_key=True)
    reporter_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False)
    content_id = Column(String(36), nullable=False)
    content_type = Column(String(20), nullable=False)
    reason = Column(Text)
    round_id = Column(String(36))

    reporter = relationship("User_mgmt")


# ================================================
# ANALYTICS (Phase 6)
# ================================================

class AnalyticsSnapshot(Base):
    """Stores aggregate system metrics per round."""
    __tablename__ = "analytics_snapshots"
    
    id = Column(String(36), primary_key=True)
    round_id = Column(String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    active_users = Column(Integer, default=0)
    total_photos = Column(Integer, default=0)
    total_reactions = Column(Integer, default=0)
    total_comments = Column(Integer, default=0)
    total_follows = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())

    round_obj = relationship("Round")


# ================================================
# PHASE 8 (Extended Mechanics)
# ================================================

class FollowRequest(Base):
    __tablename__ = "follow_requests"
    id = Column(String(36), primary_key=True)
    follower_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="pending") # pending, accepted, rejected
    created_at = Column(DateTime, server_default=func.now())

class SavedPhoto(Base):
    __tablename__ = "saved_photos"
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False)
    photo_id = Column(String(36), ForeignKey("photos.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    id = Column(String(36), primary_key=True)
    sender_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False)
    recipient_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False)
    photo_id = Column(String(36), ForeignKey("photos.id", ondelete="SET NULL"), nullable=True)
    content = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


class StoryView(Base):
    """Records which user viewed which story (and when)."""

    __tablename__ = "story_views"

    id = Column(String(36), primary_key=True)
    story_id = Column(String(36), ForeignKey("stories.id", ondelete="CASCADE"), nullable=False)
    viewer_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False)
    viewed_at = Column(DateTime, server_default=func.now())

    story = relationship("Story", back_populates="views")

    __table_args__ = (
        UniqueConstraint("story_id", "viewer_id", name="uq_story_view"),
    )


Index("idx_story_views_user", StoryView.viewer_id)


# ================================================
# SOCIAL INTERACTIONS
# ================================================


class Follow(Base):
    """Directed follow relationships between users."""

    __tablename__ = "follow"

    id = Column(String(36), primary_key=True)
    user_id = Column(
        String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False
    )
    follower_id = Column(
        String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False
    )
    action = Column(Text)          # "follow" | "unfollow"
    round = Column(String(36))

    user = relationship("User_mgmt", foreign_keys=[user_id], back_populates="follows_as_user")
    follower = relationship(
        "User_mgmt", foreign_keys=[follower_id], back_populates="follows_as_follower"
    )


Index("idx_follow_user_id", Follow.user_id)
Index("idx_follow_follower_id", Follow.follower_id)


class Reaction(Base):
    """
    Emoji reactions to photos (like, love, laugh, wow, sad, angry).
    Maps to the Instagram double-tap ❤️ and reaction bar.
    """

    __tablename__ = "reactions"

    id = Column(String(36), primary_key=True)
    user_id = Column(
        String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False
    )
    photo_id = Column(
        String(36), ForeignKey("photos.id", ondelete="CASCADE"), nullable=False
    )
    emotion_id = Column(String(36), ForeignKey("emotions.id", ondelete="SET NULL"))
    reaction_type = Column(
        String(20),
        CheckConstraint("reaction_type IN ('LIKE','LOVE','LAUGH','WOW','SAD','ANGRY')"),
        default="LIKE",
    )
    round = Column(String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User_mgmt", back_populates="reactions")
    photo = relationship("Photo", back_populates="reactions")
    emotion = relationship("Emotion")
    round_obj = relationship("Round", back_populates="reactions")

    __table_args__ = (
        UniqueConstraint("user_id", "photo_id", name="uq_reaction_user_photo"),
    )


Index("idx_reactions_photo_id", Reaction.photo_id)
Index("idx_reactions_user_id", Reaction.user_id)
Index("idx_reactions_round", Reaction.round)


class Comment(Base):
    """Comment on a photo – supports threaded replies via parent_comment_id."""

    __tablename__ = "comments"

    id = Column(String(36), primary_key=True)
    photo_id = Column(
        String(36), ForeignKey("photos.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False
    )
    parent_comment_id = Column(String(36), ForeignKey("comments.id", ondelete="SET NULL"))
    body = Column(Text, nullable=False)
    sentiment_score = Column(Float, nullable=True) # Stage 5: Sentiment Annotation
    num_likes = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    round = Column(String(36))
    created_at = Column(DateTime, server_default=func.now())
    timestamp = Column(DateTime, default=func.now(), index=True)
    
    # Phase 5
    is_removed = Column(Integer, default=0)

    photo = relationship("Photo", back_populates="comments")
    user = relationship("User_mgmt", back_populates="comments")
    replies = relationship("Comment", backref="parent_comment", remote_side=[id])


Index("idx_comments_photo_id", Comment.photo_id)
Index("idx_comments_user_id", Comment.user_id)


class Mention(Base):
    """@mention of a user inside a caption or comment."""

    __tablename__ = "mentions"

    id = Column(String(36), primary_key=True)
    photo_id = Column(String(36), ForeignKey("photos.id", ondelete="CASCADE"))
    comment_id = Column(String(36), ForeignKey("comments.id", ondelete="CASCADE"))
    user_id = Column(
        String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False
    )
    round = Column(String(36))

    photo = relationship("Photo", back_populates="mentions")
    user = relationship("User_mgmt", back_populates="mentions")


# ================================================
# CONTENT METADATA
# ================================================


class PhotoHashtag(Base):
    """Many-to-many: photos ↔ hashtags."""

    __tablename__ = "photo_hashtags"

    id = Column(String(36), primary_key=True)
    photo_id = Column(String(36), ForeignKey("photos.id", ondelete="CASCADE"), nullable=False)
    hashtag_id = Column(String(36), ForeignKey("hashtags.id", ondelete="CASCADE"), nullable=False)

    photo = relationship("Photo", back_populates="hashtags")
    hashtag = relationship("Hashtag", back_populates="photo_hashtags")

    __table_args__ = (
        UniqueConstraint("photo_id", "hashtag_id", name="uq_photo_hashtag"),
    )


class PhotoTopic(Base):
    """Many-to-many: photos ↔ interest topics (LLM-inferred)."""

    __tablename__ = "photo_topics"

    id = Column(String(36), primary_key=True)
    photo_id = Column(String(36), ForeignKey("photos.id", ondelete="CASCADE"), nullable=False)
    topic_id = Column(String(36), ForeignKey("interests.iid", ondelete="CASCADE"), nullable=False)
    confidence = Column(Float, default=1.0)

    photo = relationship("Photo", back_populates="topics")
    topic = relationship("Interest", back_populates="photo_topics")

    __table_args__ = (
        UniqueConstraint("photo_id", "topic_id", name="uq_photo_topic"),
    )


class PhotoEmotion(Base):
    """Emotion distribution inferred from photo content by LLM."""

    __tablename__ = "photo_emotions"

    id = Column(String(36), primary_key=True)
    photo_id = Column(String(36), ForeignKey("photos.id", ondelete="CASCADE"), nullable=False)
    emotion_id = Column(String(36), ForeignKey("emotions.id", ondelete="CASCADE"), nullable=False)
    score = Column(Float, default=0.0)
    viral_score = Column(Float, default=0.0)

    photo = relationship("Photo", back_populates="emotions")
    emotion_obj = relationship("Emotion", back_populates="photo_emotions")


class PostEmotion(Base):
    """YSimulator-style generic emotion annotations for photos or comments."""

    __tablename__ = "post_emotions"

    id = Column(String(36), primary_key=True)
    post_id = Column(String(36), nullable=False, index=True)
    emotion_id = Column(String(36), ForeignKey("emotions.id", ondelete="CASCADE"), nullable=False, index=True)

    emotion = relationship("Emotion")


Index("idx_post_emotions_post_id", PostEmotion.post_id)
Index("idx_post_emotions_emotion_id", PostEmotion.emotion_id)


class PostSentiment(Base):
    """YSimulator-style sentiment annotations for photos or comments."""

    __tablename__ = "post_sentiment"

    id = Column(String(36), primary_key=True)
    post_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(36), ForeignKey("interests.iid", ondelete="CASCADE"), nullable=True, index=True)
    round = Column(String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    neg = Column(Float, nullable=True)
    pos = Column(Float, nullable=True)
    neu = Column(Float, nullable=True)
    compound = Column(Float, nullable=True)
    sentiment_parent = Column(Text, nullable=True)
    is_post = Column(Integer, default=0)
    is_comment = Column(Integer, default=0)
    is_reaction = Column(Integer, default=0)

    user = relationship("User_mgmt")
    round_obj = relationship("Round")
    topic = relationship("Interest")


Index("idx_post_sentiment_post_id", PostSentiment.post_id)
Index("idx_post_sentiment_user_id", PostSentiment.user_id)
Index("idx_post_sentiment_round", PostSentiment.round)
Index("idx_post_sentiment_topic_id", PostSentiment.topic_id)


class PostToxicity(Base):
    """YSimulator-style toxicity annotations for photos or comments."""

    __tablename__ = "post_toxicity"

    id = Column(String(36), primary_key=True)
    post_id = Column(String(36), nullable=False, index=True)
    toxicity = Column(Float, default=0.0, nullable=False)
    severe_toxicity = Column(Float, default=0.0)
    identity_attack = Column(Float, default=0.0)
    insult = Column(Float, default=0.0)
    profanity = Column(Float, default=0.0)
    threat = Column(Float, default=0.0)
    sexually_explicit = Column(Float, default=0.0)
    flirtation = Column(Float, default=0.0)


Index("idx_post_toxicity_post_id", PostToxicity.post_id)


# ================================================
# USER INTERESTS & RECOMMENDATIONS
# ================================================


class UserInterest(Base):
    """User interest associations updated over simulation rounds."""

    __tablename__ = "user_interest"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"))
    interest_id = Column(String(36), ForeignKey("interests.iid", ondelete="CASCADE"))
    round_id = Column(String(36), ForeignKey("rounds.id", ondelete="CASCADE"))

    user = relationship("User_mgmt", back_populates="user_interests")
    interest = relationship("Interest", back_populates="user_interests")
    round_obj = relationship("Round", back_populates="user_interests")


Index("idx_user_interest_user_id", UserInterest.user_id)
Index("idx_user_interest_interest_id", UserInterest.interest_id)


class Recommendation(Base):
    """Photo recommendations delivered to a user in a given simulation round."""

    __tablename__ = "recommendations"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False)
    photo_ids = Column(Text)   # JSON list of photo UUIDs
    round = Column(String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)

    user = relationship("User_mgmt", back_populates="recommendations")
    round_obj = relationship("Round", back_populates="recommendations")


Index("idx_recommendations_user_id", Recommendation.user_id)
Index("idx_recommendations_round", Recommendation.round)


# ================================================
# DIRECT MESSAGES
# ================================================


class DirectMessage(Base):
    """Private direct message between two users."""

    __tablename__ = "direct_messages"

    id = Column(String(36), primary_key=True)
    sender_id = Column(
        String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False
    )
    recipient_id = Column(
        String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False
    )
    body = Column(Text, nullable=False)
    photo_id = Column(String(36), ForeignKey("photos.id", ondelete="SET NULL"))  # shared photo
    is_read = Column(Boolean, default=False)
    round = Column(String(36))
    created_at = Column(DateTime, server_default=func.now())

    sender = relationship(
        "User_mgmt", foreign_keys=[sender_id], back_populates="direct_messages_sent"
    )
    recipient = relationship(
        "User_mgmt", foreign_keys=[recipient_id], back_populates="direct_messages_received"
    )


Index("idx_dm_sender", DirectMessage.sender_id)
Index("idx_dm_recipient", DirectMessage.recipient_id)


# ================================================
# EXPLORE & TRENDING
# ================================================


class TrendingHashtag(Base):
    """Snapshot of trending hashtags per simulation round."""

    __tablename__ = "trending_hashtags"

    id = Column(String(36), primary_key=True)
    hashtag_id = Column(String(36), ForeignKey("hashtags.id", ondelete="CASCADE"), nullable=False)
    round_id = Column(String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False)
    photo_count = Column(Integer, default=0)
    rank = Column(Integer)

    __table_args__ = (
        UniqueConstraint("hashtag_id", "round_id", name="uq_trending_hashtag_round"),
    )


# ================================================
# MEMORY / AGENT STATE (mirrors YSimulator)
# ================================================


class MemoryInteractionEvent(Base):
    """Run-scoped interaction event recorded by agents."""

    __tablename__ = "memory_interaction_events"

    id = Column(Integer, primary_key=True)
    run_id = Column(String(128), nullable=False, index=True)
    round_id = Column(Integer, nullable=False, index=True)
    actor_user_id = Column(String(36), nullable=False, index=True)
    target_user_id = Column(String(36), nullable=True, index=True)
    target_photo_id = Column(String(36), nullable=True, index=True)
    actor_photo_id = Column(String(36), nullable=True, index=True)
    event_type = Column(String(32), nullable=False, index=True)
    relation_label = Column(String(32), nullable=True)
    tone_label = Column(String(32), nullable=True)
    topics_json = Column(Text, nullable=True)
    salient_claim = Column(String(300), nullable=True)
    event_text = Column(Text, nullable=True)
    weight = Column(Float, default=1.0)
    importance = Column(Float, default=0.0, index=True)
    last_accessed_round = Column(Integer, nullable=True, index=True)
    access_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())


class MemorySocialCard(Base):
    """Per-agent relationship summary for another user."""

    __tablename__ = "memory_social_cards"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "agent_user_id", "other_user_id", name="uq_memory_social_card"
        ),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(String(128), nullable=False, index=True)
    agent_user_id = Column(String(36), nullable=False, index=True)
    other_user_id = Column(String(36), nullable=False, index=True)
    affinity = Column(Float, default=0.0)
    conflict = Column(Float, default=0.0)
    humor = Column(Float, default=0.0)
    trust = Column(Float, default=0.0)
    last_relation_label = Column(String(32), nullable=True)
    last_round_id = Column(Integer, nullable=True, index=True)
    last_updated_round = Column(Integer, nullable=True, index=True)
    event_count = Column(Integer, default=0)
    summary_text = Column(Text, nullable=True)
    evidence_tail_json = Column(Text, nullable=True)


class UserOpinion(Base):
    """Agent opinions on various discussion topics."""

    __tablename__ = "user_opinions"
    __table_args__ = (
        UniqueConstraint("user_id", "topic", "round_id", name="uq_user_topic_round_opinion"),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(36), ForeignKey("interests.iid", ondelete="CASCADE"), nullable=True, index=True)
    topic = Column(String(128), nullable=False, index=True)
    round_id = Column(String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    opinion_score = Column(Float, nullable=False, default=0.5)
    opinion_label = Column(String(64), nullable=True)
    model_name = Column(String(32), nullable=True)

    user = relationship("User_mgmt", backref=backref("opinions", cascade="all, delete-orphan"))
    round_obj = relationship("Round")
    topic_obj = relationship("Interest")


class OpinionPath(Base):
    """Discrete opinion transition trace for a single interaction."""

    __tablename__ = "opinion_paths"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "topic",
            "round_id",
            "source_score",
            "target_score",
            "transition",
            name="uq_opinion_path_transition",
        ),
    )

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False, index=True)
    topic_id = Column(String(36), ForeignKey("interests.iid", ondelete="CASCADE"), nullable=True, index=True)
    topic = Column(String(128), nullable=False, index=True)
    round_id = Column(String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False, index=True)
    model_name = Column(String(32), nullable=False)
    evaluation_scope = Column(String(32), nullable=True)
    source_score = Column(Float, nullable=True)
    source_label = Column(String(64), nullable=True)
    target_score = Column(Float, nullable=False)
    target_label = Column(String(64), nullable=True)
    transition = Column(String(32), nullable=False)
    direction = Column(String(16), nullable=True)
    parent_post_id = Column(String(36), nullable=True, index=True)
    actor_user_id = Column(String(36), nullable=True, index=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User_mgmt", backref=backref("opinion_paths", cascade="all, delete-orphan"))
    round_obj = relationship("Round")
    topic_obj = relationship("Interest")


class StressReward(Base):
    """Per-user stress/reward event rows and aggregates."""

    __tablename__ = "stress_reward"
    __table_args__ = (
        CheckConstraint("variable IN ('stress', 'reward')", name="ck_stress_reward_variable"),
        CheckConstraint("type IN ('aggregate', 'variation')", name="ck_stress_reward_type"),
        CheckConstraint(
            "(type = 'aggregate' AND value >= 0 AND value <= 1) "
            "OR (type = 'variation' AND value >= -1 AND value <= 1)",
            name="ck_stress_reward_value",
        ),
    )

    id = Column(String(36), primary_key=True)
    uid = Column(
        String(36), ForeignKey("user_mgmt.id", ondelete="CASCADE"), nullable=False, index=True
    )
    variable = Column(String(16), nullable=False, index=True)
    value = Column(Float, nullable=False)
    type = Column(String(16), nullable=False, index=True)
    action = Column(String(64), nullable=True)
    tid = Column(
        String(36), ForeignKey("rounds.id", ondelete="CASCADE"), nullable=False, index=True
    )

    user = relationship("User_mgmt", backref=backref("stress_reward_events", cascade="all, delete-orphan"))
    round_obj = relationship("Round")
