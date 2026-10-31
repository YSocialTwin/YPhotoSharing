"""PlatformAdapter of YPhotoSharing (photo_sharing).

Clock (F2.3): canonical time of the server (day, hour), base 0 (day 0, hour 0 is the first round; F0.4).
Bus and membership (F3.4d), same design as the other runtimes:
- apply_membership stores the state of each account in federation_membership; accounts that are not active are left
  out of every feed, recommendation and follow suggestion (filter_photos / filter_users, called by the server) and
  the clients ask which they are (server.get_federation_inactive_agents) so they do not act.
- export_outbox turns the photos that the agents marked for cross-post (key `crosspost` of the photo data), or every
  photo of active authors in the current round with export_policy = "all", into content.v1 (kind "photo").
- ingest_inbox materialises crosspost.v1 as a photo of the author, once per fed_msg_id (INV-05), with a federation_ref
  row. A photo needs its image: a cross-post without image_ref is skipped (skipped_no_image).
Affective report (F4.1): native stress/reward of the server. Attention (F4.3): multipliers stored per account, read by the client.

`host` is the object that owns the database: it needs `_db` (with `engine` and `get_or_create_round`) and
`current_round_id` (the OrchestratorServer; a small stand-in in tests)."""

import logging
import threading
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ysocial_federation.adapter import IngestReport, PlatformAdapter
from ysocial_federation.envelope import COORDINATOR, Envelope
from ysocial_federation.schemas import TEXT_EXCERPT_MAX
from ysocial_federation.timebase import ZERO_BASED

log = logging.getLogger("yphotosharing.federation")


class YPhotoSharingAdapter(PlatformAdapter):
    platform = "photo_sharing"

    def __init__(self, member, federation_id=1, host=None, accounts=None, export_policy="marked"):
        """accounts: {global_agent_id: local user id}; without an entry the global id is the local user id."""
        if export_policy not in ("marked", "all"):
            raise ValueError("export_policy must be 'marked' or 'all'")
        self.member = member
        self.federation_id = federation_id
        self.host = host
        self.export_policy = export_policy
        self._accounts = {str(k): str(v) for k, v in (accounts or {}).items()}
        self._by_user = {v: k for k, v in self._accounts.items()}
        self._lock = threading.RLock()
        self._inactive = None  # cache of the ids that are not active; loaded from the table on first use

    # -- clock -------------------------------------------------------------------------
    def to_tick(self, local_round):
        day, hour = local_round
        return ZERO_BASED.to_tick(int(day), int(hour))

    def from_tick(self, tick):
        return ZERO_BASED.from_tick(tick)

    # -- identity and database ---------------------------------------------------------
    def user_of(self, global_agent_id):
        return self._accounts.get(str(global_agent_id), str(global_agent_id))

    def agent_of(self, user_id):
        return self._by_user.get(str(user_id), str(user_id))

    def _session(self):
        from .tables import ensure_tables

        engine = self.host._db.engine
        ensure_tables(engine)
        return Session(engine, expire_on_commit=False)

    def _round_id(self):
        rid = getattr(self.host, "current_round_id", None)
        if rid:
            return rid
        return self.host._db.get_or_create_round(self.host._current_day, self.host._current_hour)

    # -- membership --------------------------------------------------------------------
    def apply_membership(self, changes):
        from .tables import FederationMembership

        with self._lock, self._session() as s:
            for ch in changes:
                uid = self.user_of(ch.global_agent_id)
                row = s.get(FederationMembership, uid)
                if row is None:
                    s.add(FederationMembership(user_id=uid, global_agent_id=str(ch.global_agent_id), state=ch.state,
                                               since_tick=ch.tick, reason=ch.reason))
                else:
                    row.state, row.since_tick, row.reason = ch.state, ch.tick, ch.reason
            s.commit()
            self._inactive = None

    def inactive_agent_ids(self):
        """Local user ids whose state is dormant or left (cached; refreshed by apply_membership)."""
        from .tables import FederationMembership

        with self._lock:
            if self._inactive is None:
                with self._session() as s:
                    self._inactive = set(s.scalars(select(FederationMembership.user_id)
                                                   .where(FederationMembership.state != "active")).all())
            return set(self._inactive)

    def _active(self, s, user_id):
        from .tables import FederationMembership

        row = s.get(FederationMembership, str(user_id))
        return row is None or row.state == "active"

    # -- invisibility of the accounts that are not active (guide 4.10.1) --------------------
    def filter_photos(self, photos):
        """Photos (dicts with `user_id`, as the feeds return them) without those of accounts that are not active."""
        hidden = self.inactive_agent_ids()
        return [p for p in photos if p.get("user_id") not in hidden] if hidden else photos

    def filter_photo_ids(self, photo_ids):
        """Photo ids without the photos of accounts that are not active, same order."""
        hidden = self.inactive_agent_ids()
        if not hidden or not photo_ids:
            return photo_ids
        from YPhotoSharing.YServer.classes.models import Photo

        with Session(self.host._db.engine) as s:
            authors = dict(s.execute(select(Photo.id, Photo.user_id).where(Photo.id.in_(list(photo_ids)))).all())
        return [p for p in photo_ids if authors.get(p) not in hidden]

    def filter_users(self, user_ids):
        """User ids without the accounts that are not active, same order."""
        hidden = self.inactive_agent_ids()
        return [u for u in user_ids if u not in hidden] if hidden else user_ids

    # -- bus: export -------------------------------------------------------------------
    def _content(self, s, photo):
        from YPhotoSharing.YServer.classes.models import Interest, PhotoTopic, User_mgmt

        user = s.get(User_mgmt, photo.user_id)
        topics = [i.interest for i in s.scalars(select(Interest).join(PhotoTopic, PhotoTopic.topic_id == Interest.iid)
                                                .where(PhotoTopic.photo_id == photo.id).order_by(Interest.interest)).all()]
        return {"global_agent_id": self.agent_of(photo.user_id),
                "source_ref": f"ysocial://{self.federation_id}/{self.member}/photo/{photo.id}",
                "kind": "photo", "text_excerpt": (photo.caption or "")[:TEXT_EXCERPT_MAX],
                "image_ref": photo.image_url or None,
                "topics": topics, "lang": (user.language if user is not None and user.language else "en")}

    def export_outbox(self, tick):
        """content.v1 for the photos chosen at this barrier: the ones marked by the agents and, with export_policy
        "all", every photo of the current round. A second call for the same tick gives the same messages."""
        from YPhotoSharing.YServer.classes.models import Photo
        from .tables import FederationExport, FederationRef

        with self._lock, self._session() as s:
            already = s.scalars(select(FederationExport).where(FederationExport.tick == tick)
                                .order_by(FederationExport.seq)).all()
            if not already:  # first call for this tick: choose the photos and fix their sequence numbers
                done = set(s.scalars(select(FederationExport.photo_id).where(FederationExport.tick.is_not(None))).all())
                made = set(s.scalars(select(FederationRef.local_id).where(FederationRef.local_kind == "photo")).all())
                candidates = set(s.scalars(select(FederationExport.photo_id).where(FederationExport.tick.is_(None))).all())
                if self.export_policy == "all":
                    candidates |= set(s.scalars(select(Photo.id).where(Photo.round == self._round_id())).all())
                photos = [s.get(Photo, pid) for pid in candidates - done - made]
                pending = sorted((p for p in photos if p is not None and not p.is_removed and p.image_url
                                  and p.parent_photo_id is None and self._active(s, p.user_id)),
                                 key=lambda p: (p.caption or "", p.id))  # UUIDs carry no order: the text keeps it stable
                for seq, photo in enumerate(pending):
                    s.merge(FederationExport(photo_id=photo.id, tick=tick, seq=seq))
                s.commit()
                already = s.scalars(select(FederationExport).where(FederationExport.tick == tick)
                                    .order_by(FederationExport.seq)).all()
            out = []
            for row in already:
                photo = s.get(Photo, row.photo_id)
                out.append(Envelope.create(self.federation_id, self.member, COORDINATOR, tick, row.seq, "content.v1",
                                           self._content(s, photo)))
            return out

    def mark_for_export(self, photo_id):
        """The agent chose to cross-post this photo (D-07): it will be exported at the next barrier."""
        from .tables import FederationExport

        with self._lock, self._session() as s:
            if s.get(FederationExport, str(photo_id)) is None:
                s.add(FederationExport(photo_id=str(photo_id), tick=None, seq=None))
                s.commit()

    # -- bus: ingest -------------------------------------------------------------------
    def ingest_inbox(self, tick, envelopes):
        from YPhotoSharing.YServer.classes.models import Photo, PhotoTopic, User_mgmt
        from .tables import FederationRef

        report = IngestReport()

        def skip(reason):
            report.skipped[reason] = report.skipped.get(reason, 0) + 1

        with self._lock, self._session() as s:
            for env in envelopes:
                if env.payload_type != "crosspost.v1":
                    skip("skipped_unsupported")
                    continue
                if s.scalar(select(FederationRef.local_id).where(FederationRef.fed_msg_id == env.fed_msg_id)) is not None:
                    report.duplicates += 1  # INV-05: already materialised
                    continue
                payload = env.payload
                uid = str(payload["target_account_id"])
                if s.get(User_mgmt, uid) is None or not self._active(s, uid):
                    skip("skipped_ineligible")
                    continue
                if not payload.get("image_ref"):
                    skip("skipped_no_image")  # a photo needs its image
                    continue
                photo_id = str(uuid.uuid4())
                # photo, topics and reference in one transaction: a crash leaves nothing, the message comes again
                s.add(Photo(id=photo_id, user_id=uid, round=self._round_id(), image_url=payload["image_ref"],
                            thumbnail_url=payload["image_ref"], caption=payload["text_excerpt"]))
                s.flush()
                for name in dict.fromkeys(payload.get("topics") or []):
                    s.add(PhotoTopic(id=str(uuid.uuid4()), photo_id=photo_id, confidence=1.0,
                                     topic_id=self.host._db._add_or_get_interest_in_session(s, str(name))))
                s.add(FederationRef(local_kind="photo", local_id=photo_id, source_ref=payload["source_ref"],
                                    fed_msg_id=env.fed_msg_id))
                s.commit()
                report.materialized += 1
        return report

    def affective_report(self, day):
        """Native stress/reward of the active accounts at the last round of the canonical day (F4.1): the value of the
        server's own computation (DatabaseMiddleware._compute_stress_reward_aggregate, the one get_stress_reward uses),
        read without writing; actions = photos and reactions of the account in the day, exposures = photos recommended."""
        import json

        from sqlalchemy import func

        from YPhotoSharing.YServer.classes.models import Photo, Reaction, Recommendation, Round
        from ysocial_federation.schemas import AffectiveSample
        from .tables import FederationMembership

        with self._lock, self._session() as s:
            rounds = s.scalars(select(Round).where(Round.day == int(day)).order_by(Round.hour)).all()
            if not rounds:
                return []
            ids = [r.id for r in rounds]
            last = ids[-1]
            out = []
            for m in s.scalars(select(FederationMembership).where(FederationMembership.state == "active")
                               .order_by(FederationMembership.user_id)).all():
                uid = m.user_id
                agg = self.host._db._compute_stress_reward_aggregate(s, uid, last, 24)
                photos = s.scalar(select(func.count(Photo.id)).where(Photo.user_id == uid, Photo.round.in_(ids)))
                reacts = s.scalar(select(func.count(Reaction.id)).where(Reaction.user_id == uid, Reaction.round.in_(ids)))
                exposures = 0
                for rec in s.scalars(select(Recommendation).where(Recommendation.user_id == uid,
                                                                  Recommendation.round.in_(ids))).all():
                    try:
                        exposures += len(json.loads(rec.photo_ids or "[]"))
                    except ValueError:
                        exposures += len([p for p in (rec.photo_ids or "").split(",") if p.strip()])
                out.append(AffectiveSample(self.agent_of(uid), int(day), float(agg.get("stress", 0.0)),
                                           float(agg.get("reward", 0.0)), int(photos or 0) + int(reacts or 0), exposures))
            return out

    def apply_attention(self, day, multipliers):
        """Store the multipliers of the day (F4.3): accounts that are not in the dictionary go back to 1; unknown agents are
        ignored. The client reads them with server.get_federation_attention and the round planner scales the chance that an
        agent acts in a round."""
        from YPhotoSharing.YServer.classes.models import User_mgmt
        from .tables import FederationAttention

        with self._lock, self._session() as s:
            known = set(s.scalars(select(User_mgmt.id)).all())
            s.query(FederationAttention).delete()
            for gid, value in sorted((multipliers or {}).items()):
                uid = self.user_of(gid)
                if uid in known and float(value) != 1.0:
                    s.add(FederationAttention(user_id=uid, day=int(day), multiplier=float(value)))
            s.commit()

    def attention_multipliers(self):
        """{local user id: multiplier} of the current day (accounts not listed: 1)."""
        from .tables import FederationAttention

        with self._lock, self._session() as s:
            return {r.user_id: r.multiplier for r in s.scalars(select(FederationAttention)).all()}
