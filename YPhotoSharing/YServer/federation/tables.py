"""Tables of the federation inside the YPhotoSharing database (all new, additive; created only when federation is on).

federation_membership: state of each local account as the coordinator told it (dormant, active, left).
federation_ref:        every photo materialised from a cross-post (origin = federation) with its source.
federation_export:     photos handed to the bus, with tick and sequence number, so that exporting the same tick again
                       gives the same messages (INV-05); tick NULL = marked by the agent, not exported yet.
federation_state:      small key/value store.
They live in a metadata of their own: the existing tables and their creation do not change."""

from sqlalchemy import Boolean, Column, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class FederationMembership(Base):
    __tablename__ = "federation_membership"

    user_id = Column(String(36), primary_key=True)
    global_agent_id = Column(String(64), nullable=False, unique=True)
    state = Column(String(10), nullable=False)
    since_tick = Column(Integer, nullable=False, default=0)
    reason = Column(String(16), nullable=False, default="initial")


class FederationRef(Base):
    __tablename__ = "federation_ref"

    local_kind = Column(String(16), primary_key=True)
    local_id = Column(String(36), primary_key=True)
    source_ref = Column(Text, nullable=False)
    fed_msg_id = Column(String(200), nullable=False, unique=True)


class FederationExport(Base):
    __tablename__ = "federation_export"

    photo_id = Column(String(36), primary_key=True)
    tick = Column(Integer, nullable=True)
    seq = Column(Integer, nullable=True)


class FederationQuoted(Base):
    """F8: structured reference of the photo another agent posted, shared by the photo `photo_id`."""

    __tablename__ = "federation_quoted"

    photo_id = Column(String(36), primary_key=True)
    author_name = Column(String(200), nullable=False)
    global_agent_id = Column(String(64), nullable=True)
    member = Column(String(64), nullable=False)
    source_ref = Column(Text, nullable=True)
    text_excerpt = Column(Text, nullable=False, default="")


class FederationCrosspost(Base):
    """The agent chose to cross-post a photo to another platform with this text (F6.2, crosspost.mode = agent_action).

    account_id, tick and seq are fixed at the first export of the photo, so that a retry sends the same message."""

    __tablename__ = "federation_crosspost"

    photo_id = Column(String(36), primary_key=True)
    member = Column(String(64), primary_key=True)
    text = Column(Text, nullable=False, default="")
    account_id = Column(String(64), nullable=True)
    tick = Column(Integer, nullable=True)
    seq = Column(Integer, nullable=True)


class FederationAttention(Base):
    """Attention multiplier of the day for each account (F4.3); an account without a row has multiplier 1."""

    __tablename__ = "federation_attention"

    user_id = Column(String(36), primary_key=True)
    day = Column(Integer, nullable=False)
    multiplier = Column(Float, nullable=False)


class FederationExposure(Base):
    """exposure.v1 handed to the bus for a tick (F4.4b), fixed on the first export so that a retry sends the same messages."""

    __tablename__ = "federation_exposure_log"

    tick = Column(Integer, primary_key=True)
    seq = Column(Integer, primary_key=True)
    viewer_uid = Column(String(36), nullable=False)
    source_ref = Column(Text, nullable=False)
    kind = Column(String(10), nullable=False)
    tie = Column(String(10), nullable=False)
    exact = Column(Integer, nullable=False)


class FederationTopic(Base):
    """Topics created here because cross-posted content carried them (topic migration): name as first seen, tick, origin."""

    __tablename__ = "federation_topic"

    name = Column(String(200), primary_key=True)
    created_tick = Column(Integer, nullable=False)
    source_member = Column(String(64), nullable=False)


class FederationHuman(Base):
    """H5c: accounts of human participants and their federation identity (`human:...`), registered by the human gateway."""

    __tablename__ = "federation_human"

    user_id = Column(String(36), primary_key=True)
    global_agent_id = Column(String(128), nullable=False, unique=True)


class FederationProvisioned(Base):
    """Accounts created here because the coordinator asked for them (INV-19): the agent of a client of another platform
    decided to join. A client of this platform adopts each one (gives it an agent that acts); `adopted` tells which."""

    __tablename__ = "federation_provisioned"

    user_id = Column(String(36), primary_key=True)
    global_agent_id = Column(String(64), nullable=False, unique=True)
    username = Column(String(50), nullable=False)
    interests_json = Column(String(1000), nullable=False, default="[]")
    adopted = Column(Boolean, nullable=False, default=False)


class FederationState(Base):
    __tablename__ = "federation_state"

    key = Column(String(32), primary_key=True)
    value = Column(String(64), nullable=False)


def ensure_tables(engine):
    """CREATE TABLE IF NOT EXISTS for the tables."""
    Base.metadata.create_all(engine, checkfirst=True)
