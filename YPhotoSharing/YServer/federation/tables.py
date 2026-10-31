"""Tables of the federation inside the YPhotoSharing database (all new, additive; created only when federation is on).

federation_membership: state of each local account as the coordinator told it (dormant, active, left).
federation_ref:        every photo materialised from a cross-post (origin = federation) with its source.
federation_export:     photos handed to the bus, with tick and sequence number, so that exporting the same tick again
                       gives the same messages (INV-05); tick NULL = marked by the agent, not exported yet.
federation_state:      small key/value store.
They live in a metadata of their own: the existing tables and their creation do not change."""

from sqlalchemy import Column, Integer, String, Text
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


class FederationState(Base):
    __tablename__ = "federation_state"

    key = Column(String(32), primary_key=True)
    value = Column(String(64), nullable=False)


def ensure_tables(engine):
    """CREATE TABLE IF NOT EXISTS for the four tables."""
    Base.metadata.create_all(engine, checkfirst=True)
