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

from ysocial_federation import quoted as fed_quoted
from ysocial_federation.bindings import BoundAccountsMixin
from ysocial_federation.adapter import IngestReport, PlatformAdapter
from ysocial_federation.envelope import COORDINATOR, Envelope
from ysocial_federation.schemas import TEXT_EXCERPT_MAX
from ysocial_federation.timebase import ZERO_BASED

log = logging.getLogger("yphotosharing.federation")
HUMAN_PREFIX = "human:"  # identities of people; never take part in attention, churn, leave or discovery (INV-15)


class YPhotoSharingAdapter(BoundAccountsMixin, PlatformAdapter):
    platform = "photo_sharing"

    def __init__(self, member, federation_id=1, host=None, accounts=None, export_policy="marked", emit_exposures=False,
                 crosspost_mode="coordinator_rule", bindings_file=None):
        """accounts: {global_agent_id: local user id}; without an entry the global id is the local user id.

        bindings_file (INV-17): agents are bound by username; the accounts are reported to the coordinator, whose answer is kept in
        this file. Then the local id is never the global id: an account that is not bound acts as usual and is not exported."""
        if export_policy not in ("marked", "all"):
            raise ValueError("export_policy must be 'marked' or 'all'")
        self.member = member
        self.federation_id = federation_id
        self.host = host
        self.export_policy = export_policy
        self.emit_exposures = bool(emit_exposures)
        if crosspost_mode not in ("coordinator_rule", "agent_action"):
            raise ValueError("crosspost_mode must be 'coordinator_rule' or 'agent_action'")
        self.crosspost_mode = crosspost_mode
        self._destinations = {}  # {global_agent_id: [{"member", "local_account_id"}]}, set by the gate before each export
        self._accounts = {str(k): str(v) for k, v in (accounts or {}).items()}
        self._by_user = {v: k for k, v in self._accounts.items()}
        self._lock = threading.RLock()
        self._inactive = None  # cache of the ids that are not active; loaded from the table on first use
        self._humans = None  # {local user id: "human:..."}; loaded from federation_human on first use (H5c)
        self._init_bindings(bindings_file, self._enumerate_accounts, cast=str)

    def _enumerate_accounts(self, after):
        """Ids are UUIDs (no order): the marker is the number of accounts, so a round without new accounts costs one COUNT."""
        from sqlalchemy import func

        from YPhotoSharing.YServer.classes.models import User_mgmt

        with self._session() as s:
            count = s.scalar(select(func.count()).select_from(User_mgmt))
            if after is not None and int(after) == int(count):
                return [], after
            rows = s.execute(select(User_mgmt.username, User_mgmt.id).order_by(User_mgmt.id)).all()
        humans = self._human_map()
        return [(u, i) for u, i in rows if i not in humans and i not in self._by_user], count

    # -- clock -------------------------------------------------------------------------
    def to_tick(self, local_round):
        day, hour = local_round
        return ZERO_BASED.to_tick(int(day), int(hour))

    def from_tick(self, tick):
        return ZERO_BASED.from_tick(tick)

    # -- identity and database ---------------------------------------------------------
    def user_of(self, global_agent_id):
        gid = str(global_agent_id)
        if gid in self._accounts:
            return self._accounts[gid]
        if gid.startswith(HUMAN_PREFIX):
            for uid, hid in self._human_map().items():
                if hid == gid:
                    return uid
        if self._is_bound_mode:  # INV-17: the global id comes from the coordinator, never from the local id
            return None
        return gid

    def agent_of(self, user_id):
        uid = str(user_id)
        if uid in self._by_user:
            return self._by_user[uid]
        human = self._human_map().get(uid)  # a person never takes the local id as global identity (could clash with an agent)
        if human is not None:
            return human
        return self._unbound_id(uid) if self._is_bound_mode else uid

    # -- human participants (H5c) --------------------------------------------------------
    def _human_map(self):
        with self._lock:
            if self._humans is None:
                if self.host is None:
                    self._humans = {}
                else:
                    from .tables import FederationHuman

                    with self._session() as s:
                        self._humans = {r.user_id: r.global_agent_id for r in s.scalars(select(FederationHuman)).all()}
            return self._humans

    def register_human(self, user_id, global_agent_id):
        """Record that the local account `user_id` is the person `global_agent_id` (`human:...`); idempotent."""
        from .tables import FederationHuman

        gid = str(global_agent_id)
        if not gid.startswith(HUMAN_PREFIX) or len(gid) == len(HUMAN_PREFIX):
            raise ValueError("a human identity starts with 'human:'")
        with self._lock, self._session() as s:
            row = s.get(FederationHuman, str(user_id))
            if row is None:
                other = s.scalar(select(FederationHuman).where(FederationHuman.global_agent_id == gid))
                if other is not None and other.user_id != str(user_id):
                    raise ValueError(f"{gid} is already the account {other.user_id}")
                s.add(FederationHuman(user_id=str(user_id), global_agent_id=gid))
            elif row.global_agent_id != gid:
                raise ValueError(f"account {user_id} is already {row.global_agent_id}")
            s.commit()
            self._humans = None

    def is_human(self, user_id):
        return str(user_id) in self._human_map()

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
                if uid is None:
                    log.warning("federation: membership change for unknown agent %s ignored", ch.global_agent_id)
                    continue
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
        def names(photo_id):
            return [i.interest for i in s.scalars(select(Interest).join(PhotoTopic, PhotoTopic.topic_id == Interest.iid)
                                                  .where(PhotoTopic.photo_id == photo_id).order_by(Interest.interest)).all()]

        topics = names(photo.id)
        if not topics and photo.parent_photo_id:  # a share has no topics of its own: those of the original travel with it
            topics = names(photo.parent_photo_id)
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
                marked = set(candidates)
                if self.export_policy == "all":
                    candidates |= set(s.scalars(select(Photo.id).where(Photo.round == self._round_id())).all())
                photos = [s.get(Photo, pid) for pid in candidates - done - made]
                # F8: a share (parent_photo_id set) leaves only when the agent marked it, and only in agent_action
                shares_ok = self.crosspost_mode == "agent_action"
                pending = sorted((p for p in photos if p is not None and not p.is_removed and p.image_url
                                  and (p.parent_photo_id is None or (shares_ok and p.id in marked))
                                  and self._active(s, p.user_id) and self._federated(p.user_id)),
                                 key=lambda p: (p.caption or "", p.id))  # UUIDs carry no order: the text keeps it stable
                for seq, photo in enumerate(pending):
                    s.merge(FederationExport(photo_id=photo.id, tick=tick, seq=seq))
                s.commit()
                if self.crosspost_mode == "agent_action":
                    self._fix_crossposts(s, tick, pending, len(pending))
                already = s.scalars(select(FederationExport).where(FederationExport.tick == tick)
                                    .order_by(FederationExport.seq)).all()
            out = []
            asked = self._crossposts_of(s, tick) if self.crosspost_mode == "agent_action" else []
            by_photo = {r.photo_id for r in asked}
            for row in already:
                if row.photo_id in by_photo:  # the agent chose where to post it: the cross-posts are the message
                    continue
                photo = s.get(Photo, row.photo_id)
                out.append(Envelope.create(self.federation_id, self.member, COORDINATOR, tick, row.seq, "content.v1",
                                           self._content(s, photo)))
            for req in asked:
                content = self._content(s, s.get(Photo, req.photo_id))
                if req.text:
                    content["text_excerpt"] = req.text[:TEXT_EXCERPT_MAX]
                body = dict(content, target_account_id=req.account_id)
                quoted = self._quoted(s, s.get(Photo, req.photo_id))
                if quoted is not None:
                    body["quoted"] = quoted
                out.append(Envelope.create(self.federation_id, self.member, req.member, tick, req.seq, "crosspost.v1", body))
            if self.emit_exposures:
                quoting = self._quote_pairs(s, asked)
                rows = list(self._exposure_rows(s, tick))
                if quoting:
                    rows = rows + self._ensure_quote_exposures(s, tick, rows, quoting)
                front = []
                for row in rows:
                    if not self._federated(row.viewer_uid):
                        continue
                    env = Envelope.create(self.federation_id, self.member, COORDINATOR, tick, max((e.seq for e in out + front), default=-1) + 1, "exposure.v1", {
                        "viewer_global_agent_id": self.agent_of(row.viewer_uid), "source_ref": row.source_ref, "tick": tick,
                        "exact": bool(row.exact), "kind": row.kind, "tie": row.tie})
                    (front if (str(row.viewer_uid), row.source_ref) in quoting else out).append(env)
                # P3: the exposure of the agent to the foreign content it quotes leaves before the cross-post that quotes it
                first = min((i for i, e in enumerate(out) if e.payload_type == "crosspost.v1" and e.payload.get("quoted")), default=len(out))
                out[first:first] = front
            return out

    def _quote_pairs(self, s, asked):
        """P3: {(viewer account, source_ref)} of the cross-posts that quote content materialised on this platform (seen here
        by the quoting agent, who is neither a person nor inactive)."""
        from YPhotoSharing.YServer.classes.models import Photo
        from .tables import FederationRef

        pairs = set()
        for req in asked:
            photo = s.get(Photo, req.photo_id)
            quoted = self._quoted(s, photo)
            if quoted is None or self.is_human(photo.user_id) or not self._active(s, photo.user_id):
                continue
            if s.scalar(select(FederationRef.local_id).where(FederationRef.local_kind == "photo", FederationRef.source_ref == quoted["source_ref"])) is not None:
                pairs.add((str(photo.user_id), quoted["source_ref"]))
        return pairs

    def _ensure_quote_exposures(self, s, tick, rows, pairs):
        """P3: an interact exposure (exact) for each (viewer, ref) pair with no exposure of that viewer to that content yet
        (this tick or an earlier one), stored in the log after the rows of the tick so that a retry gives the same."""
        from YPhotoSharing.YServer.classes.models import Photo
        from .tables import FederationExposure, FederationRef

        have = {(str(r.viewer_uid), r.source_ref) for r in s.scalars(select(FederationExposure).where(FederationExposure.tick <= tick)).all()}
        seq = max((r.seq for r in rows), default=-1) + 1
        added = []
        for viewer, ref in sorted(pairs - have):
            local = s.scalar(select(FederationRef.local_id).where(FederationRef.local_kind == "photo", FederationRef.source_ref == ref))
            row = FederationExposure(tick=tick, seq=seq, viewer_uid=viewer, source_ref=ref, kind="interact",
                                     tie=self._tie(s, viewer, s.get(Photo, local).user_id), exact=1)
            s.add(row)
            added.append(row)
            seq += 1
        s.commit()
        return added

    def _quoted(self, s, photo):
        """F8: `quoted` of a photo that shares another one (None for any other photo): the original author, this platform
        and the original caption; the author is a federation identity only when the account is in the identity map."""
        if photo is None or not photo.parent_photo_id:
            return None
        from YPhotoSharing.YServer.classes.models import Photo, User_mgmt
        from .tables import FederationRef

        original = s.get(Photo, photo.parent_photo_id)
        if original is None:
            return None
        author = s.get(User_mgmt, original.user_id)
        gid = self._by_user.get(str(original.user_id)) or self._human_map().get(str(original.user_id))
        ref = s.scalar(select(FederationRef.source_ref).where(FederationRef.local_kind == "photo", FederationRef.local_id == original.id))
        ref = ref or f"ysocial://{self.federation_id}/{self.member}/photo/{original.id}"
        return fed_quoted.build(author.username if author is not None else "unknown", gid, self.member, ref, original.caption)

    def _tie(self, s, viewer, author):
        """none / follow / mutual between a viewer and the author of a photo, from the latest follow rows."""
        from YPhotoSharing.YServer.classes.models import Follow, Round

        def follows(a, b):
            row = s.execute(select(Follow, Round).outerjoin(Round, Round.id == Follow.round).where(
                Follow.user_id == a, Follow.follower_id == b).order_by(Round.day.desc(), Round.hour.desc())).first()
            return row is not None and row[0].action == "follow"
        if not follows(viewer, author):
            return "none"
        return "mutual" if follows(author, viewer) else "follow"

    def _exposure_rows(self, s, tick):
        """Views (photos recommended in the round: approximate, exact = false) and interactions (reaction or comment:
        exact) of active accounts with the materialised cross-posts of the round of the tick, in a stable order."""
        import json

        from YPhotoSharing.YServer.classes.models import Comment, Photo, Reaction, Recommendation, Round
        from .tables import FederationExposure, FederationRef, FederationState

        def stored():
            return list(s.scalars(select(FederationExposure).where(FederationExposure.tick == tick).order_by(FederationExposure.seq)).all())
        done = s.get(FederationState, "exposure_tick")
        if done is not None and int(done.value) >= tick:
            return stored()
        day, hour = self.from_tick(tick)
        rnd = s.scalars(select(Round).where(Round.day == day, Round.hour == hour)).first()
        refs = {r.local_id: r.source_ref for r in s.scalars(select(FederationRef).where(FederationRef.local_kind == "photo")).all()} if rnd else {}
        if refs:
            author = {pid: uid for pid, uid in s.execute(select(Photo.id, Photo.user_id).where(Photo.id.in_(list(refs)))).all()}
            found = {}

            def add(viewer, pid, kind, exact):
                if viewer is None or viewer == author.get(pid) or not self._active(s, viewer):
                    return
                found.setdefault((str(viewer), refs[pid], kind), (pid, exact))
            for rec in s.scalars(select(Recommendation).where(Recommendation.round == rnd.id)).all():
                try:
                    ids = json.loads(rec.photo_ids or "[]")
                except ValueError:
                    ids = (rec.photo_ids or "").split(",")
                for raw in ids:
                    if str(raw).strip() in refs:
                        add(rec.user_id, str(raw).strip(), "view", False)
            for r in s.scalars(select(Reaction).where(Reaction.round == rnd.id, Reaction.photo_id.in_(list(refs)))).all():
                add(r.user_id, r.photo_id, "interact", True)
            for c in s.scalars(select(Comment).where(Comment.round == rnd.id, Comment.photo_id.in_(list(refs)))).all():
                add(c.user_id, c.photo_id, "interact", True)
            for seq, ((viewer, ref, kind), (pid, exact)) in enumerate(sorted(found.items())):
                s.add(FederationExposure(tick=tick, seq=seq, viewer_uid=viewer, source_ref=ref, kind=kind,
                                         tie=self._tie(s, viewer, author[pid]), exact=int(exact)))
        if done is None:
            s.add(FederationState(key="exposure_tick", value=str(tick)))
        else:
            done.value = str(tick)
        s.commit()
        return stored()

    def mark_for_export(self, photo_id, targets=None):
        """The agent chose to cross-post this photo (D-07): it will be exported at the next barrier.

        targets (crosspost.mode = agent_action): [{"member", "text"}], where the agent wants it and with which text."""
        from .tables import FederationCrosspost, FederationExport

        with self._lock, self._session() as s:
            if s.get(FederationExport, str(photo_id)) is None:
                s.add(FederationExport(photo_id=str(photo_id), tick=None, seq=None))
            if self.crosspost_mode == "agent_action":
                for target in targets or []:
                    member = str(target.get("member") or "")
                    if member and member != self.member and s.get(FederationCrosspost, (str(photo_id), member)) is None:
                        s.add(FederationCrosspost(photo_id=str(photo_id), member=member, text=str(target.get("text") or "")))
            s.commit()

    # -- agent-action cross-posts (F6.2) -------------------------------------------------
    def set_destinations(self, destinations):
        self._destinations = {str(k): list(v) for k, v in (destinations or {}).items()}

    def destination_members(self, user_id):
        """Members where this account's agent could cross-post now (as of the last barrier)."""
        return sorted(d["member"] for d in self._destinations.get(self.agent_of(user_id), []))

    def _fix_crossposts(self, s, tick, photos, first_seq):
        """First export of the tick: give each requested cross-post its account, tick and sequence number (a request
        for a platform where the author has no active account is dropped)."""
        from sqlalchemy import select as _select

        from .tables import FederationCrosspost

        seq = first_seq
        for photo in photos:
            wanted = self._destinations.get(self.agent_of(photo.user_id), [])
            rows = s.scalars(_select(FederationCrosspost).where(FederationCrosspost.photo_id == photo.id, FederationCrosspost.tick.is_(None))
                             .order_by(FederationCrosspost.member)).all()
            for row in rows:
                account = next((d["local_account_id"] for d in wanted if d["member"] == row.member), None)
                row.tick = tick
                if account is None:
                    log.info("federation: cross-post of photo %s to %s dropped: no active account", photo.id, row.member)
                    continue
                row.account_id, row.seq = str(account), seq
                seq += 1
        s.commit()

    def _crossposts_of(self, s, tick):
        from .tables import FederationCrosspost

        return list(s.scalars(select(FederationCrosspost).where(FederationCrosspost.tick == tick, FederationCrosspost.seq.is_not(None))
                              .order_by(FederationCrosspost.seq)).all())

    # -- bus: ingest -------------------------------------------------------------------
    def _topic_id(self, s, name, tick, source_member):
        """Topic migration: the topic of that name here (case-insensitive), created and recorded when it does not exist."""
        from sqlalchemy import func
        from YPhotoSharing.YServer.classes.models import Interest
        from .tables import FederationTopic

        found = s.scalars(select(Interest).where(func.lower(Interest.interest) == name.lower()).order_by(Interest.iid)).first()
        if found is not None:
            return found.iid
        iid = self.host._db._add_or_get_interest_in_session(s, name)
        if s.get(FederationTopic, name) is None:
            s.add(FederationTopic(name=name, created_tick=int(tick), source_member=str(source_member)))
        return iid

    def ingest_inbox(self, tick, envelopes):
        from YPhotoSharing.YServer.classes.models import Photo, PhotoTopic, User_mgmt
        from .tables import FederationQuoted, FederationRef

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
                quoted = payload.get("quoted")
                photo_id = str(uuid.uuid4())
                # photo, topics and reference in one transaction: a crash leaves nothing, the message comes again
                s.add(Photo(id=photo_id, user_id=uid, round=self._round_id(), image_url=payload["image_ref"],
                            thumbnail_url=payload["image_ref"],
                            caption=fed_quoted.render(payload["text_excerpt"], quoted, 300) if quoted else payload["text_excerpt"]))
                s.flush()
                if quoted:
                    s.add(FederationQuoted(photo_id=photo_id, author_name=quoted["author_name"], global_agent_id=quoted["global_agent_id"],
                                           member=quoted["member"], source_ref=quoted["source_ref"], text_excerpt=quoted["text_excerpt"]))
                seen = set()
                for name in payload.get("topics") or []:
                    name = str(name).strip()
                    if not name or name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    s.add(PhotoTopic(id=str(uuid.uuid4()), photo_id=photo_id, confidence=1.0,
                                     topic_id=self._topic_id(s, name, tick, env.source_member)))
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
                if str(m.global_agent_id).startswith(HUMAN_PREFIX) or self.is_human(uid):
                    continue  # people have no stress/reward model (INV-15)
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

    def churned_agents(self, day):
        """Agents of this platform that left on their own (users.left_on set at a round up to the end of the day, F4.5): the
        coordinator records them as left with reason churn. Only accounts the federation still sees as active."""
        from YPhotoSharing.YServer.classes.models import Round, User_mgmt
        from .tables import FederationMembership

        with self._lock, self._session() as s:
            rounds = set(s.scalars(select(Round.id).where(Round.day <= int(day))).all())
            out = []
            for row in s.scalars(select(FederationMembership).where(FederationMembership.state == "active")).all():
                if str(row.global_agent_id).startswith(HUMAN_PREFIX):
                    continue  # a person leaving the platform is not churn (INV-15)
                user = s.get(User_mgmt, row.user_id)
                if user is not None and user.left_on is not None and user.left_on in rounds:
                    out.append(row.global_agent_id)
            return sorted(out)

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
                if str(gid).startswith(HUMAN_PREFIX):
                    continue  # no attention multiplier for people (INV-15)
                uid = self.user_of(gid)
                if uid in known and float(value) != 1.0:
                    s.add(FederationAttention(user_id=uid, day=int(day), multiplier=float(value)))
            s.commit()

    def attention_multipliers(self):
        """{local user id: multiplier} of the current day (accounts not listed: 1)."""
        from .tables import FederationAttention

        with self._lock, self._session() as s:
            return {r.user_id: r.multiplier for r in s.scalars(select(FederationAttention)).all()}
