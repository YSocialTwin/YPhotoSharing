"""Gateway logic, independent of the transport.

`HumanGateway` validates the requests of a person and applies them through a *backend*:
- `OnlineBackend(call)`: the methods of the running server (the Ray actor, `call(method, *args)`);
- `LocalBackend(db, adapter)`: the same database layer used in-process, with the server stopped (offline.py).
Both expose the same methods, so a person's action takes the same path whether the server runs or not.
"""

from __future__ import annotations

import base64
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .humans import HUMAN_USER_TYPE, ensure_human, global_id_of

MAX_CAPTION = 2200
MAX_COMMENT = 1000
MAX_CROSSPOST_TEXT = 300
MAX_ACTIONS_PER_REQUEST = 20
MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_ACTIONS = frozenset({"post_photo", "share", "comment", "react", "unreact", "follow", "unfollow"})
REACTIONS = frozenset({"LIKE", "LOVE", "LAUGH", "WOW", "SAD", "ANGRY"})  # the values the reactions table accepts


class RateLimiter:
    """Token bucket per key: `burst` actions at once, refilled at `per_second`."""

    def __init__(self, burst: float = 10, per_second: float = 2, clock=time.monotonic):
        self.burst, self.rate, self.clock = burst, per_second, clock
        self._state: Dict[str, Tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, cost: float = 1) -> bool:
        with self._lock:
            now = self.clock()
            tokens, last = self._state.get(key, (self.burst, now))
            tokens = min(self.burst, tokens + (now - last) * self.rate)
            if tokens < cost:
                self._state[key] = (tokens, now)
                return False
            self._state[key] = (tokens - cost, now)
            return True


class OnlineBackend:
    """The running server, through `call(method, *args)` (the Ray actor)."""

    def __init__(self, call: Callable[..., Any]):
        self.call = call

    def context(self):
        return self.call("human_context")

    def ensure(self, human_key, username, language):
        return self.call("human_ensure", human_key, username, language)

    def user(self, account_id):
        return self.call("get_user", account_id)

    def post_photo(self, data):
        return self.call("post_photo", data)

    def react(self, user_id, photo_id, reaction_type, round_id):
        return self.call("react_to_photo", user_id, photo_id, reaction_type, round_id)

    def unreact(self, user_id, photo_id):
        return self.call("remove_reaction", user_id, photo_id)

    def comment(self, user_id, photo_id, body, round_id, parent):
        return self.call("post_comment", user_id, photo_id, body, round_id, parent)

    def follow(self, follower, user, round_id):
        return self.call("follow_user", follower, user, round_id)

    def unfollow(self, follower, user, round_id):
        return self.call("unfollow_user", follower, user, round_id)

    def photo(self, photo_id):
        return self.call("get_photo", photo_id)

    def photo_topics(self, photo_id):
        return self.call("get_photo_topics", photo_id)

    def comments(self, photo_id, limit):
        return self.call("get_comments", photo_id, limit)

    def feed(self, user_id, limit):
        return self.call("get_home_feed", user_id, limit)

    def save_media(self, content_b64, extension):
        return self.call("save_media", content_b64, extension)


class LocalBackend:
    """The same database layer in this process (server stopped, or tests). `adapter` is the federation adapter or None."""

    def __init__(self, db, adapter=None, media_service=None, service=None):
        from YPhotoSharing.YServer.services.social_action_service import SocialActionService

        self.db, self.adapter, self.media = db, adapter, media_service
        self.service = service or SocialActionService(db_adapter=db)

    def _round(self):
        from YPhotoSharing.YServer.classes.models import Round

        with self.db.session_scope() as s:
            row = s.query(Round).order_by(Round.day.desc(), Round.hour.desc(), Round.id.desc()).first()
            if row is not None:
                return row.id, int(row.day), int(row.hour)
        return self.db.get_or_create_round(0, 0), 0, 0

    def context(self):
        rid, day, hour = self._round()
        return {"round_id": rid, "day": day, "hour": hour, "federated": self.adapter is not None,
                "crosspost_mode": getattr(self.adapter, "crosspost_mode", None)}

    def ensure(self, human_key, username, language):
        return ensure_human(self.db, self.adapter, self._round()[0], human_key, username, language)

    def user(self, account_id):
        return self.db.get_user(account_id)

    def post_photo(self, data):
        data = dict(data)
        crosspost = bool(data.pop("crosspost", False))
        targets = data.pop("crosspost_to", None)
        photo_id = self.service.post_photo(data)
        if crosspost and self.adapter is not None:
            self.adapter.mark_for_export(photo_id, targets) if isinstance(targets, list) else self.adapter.mark_for_export(photo_id)
        return photo_id

    def react(self, user_id, photo_id, reaction_type, round_id):
        return self.service.react_to_photo(user_id, photo_id, reaction_type, round_id)

    def unreact(self, user_id, photo_id):
        return self.service.remove_reaction(user_id, photo_id)

    def comment(self, user_id, photo_id, body, round_id, parent):
        return self.service.post_comment(user_id, photo_id, body, round_id, parent)

    def follow(self, follower, user, round_id):
        return self.db.add_follow(user_id=user, follower_id=follower, round_id=round_id)

    def unfollow(self, follower, user, round_id):
        return self.db.remove_follow(user_id=user, follower_id=follower, round_id=round_id)

    def photo(self, photo_id):
        return self.service.get_photo(photo_id)

    def photo_topics(self, photo_id):
        return self.service.get_photo_topics(photo_id)

    def comments(self, photo_id, limit):
        return self.service.get_comments(photo_id, limit)

    def feed(self, user_id, limit):
        feed = self.db.get_home_feed(user_id, limit=limit * 2 if self.adapter is not None else limit)
        return (self.adapter.filter_photos(feed) if self.adapter is not None else feed)[:limit]

    def save_media(self, content_b64, extension):
        return self.media.save_media(content_b64, extension)


def _text(value, limit, required=False):
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError("text must be a string")
    value = value.strip().strip('"')
    if required and not value:
        raise ValueError("text is empty")
    if len(value) > limit:
        raise ValueError("text too long")
    return value


def crosspost_fields(raw, default_text: str) -> dict:
    """`crosspost_to` of a person's action ([{member, text}]) as the agent payload carries it; {} when empty."""
    if raw in (None, [], ()):
        return {}
    if not isinstance(raw, list) or len(raw) > 16:
        raise ValueError("crosspost_to must be a short list")
    out, seen = [], set()
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("member"), str) or not item["member"].strip():
            raise ValueError("crosspost_to entries need a member")
        member = item["member"].strip()
        if member in seen:
            continue
        seen.add(member)
        text = _text(item.get("text") if item.get("text") is not None else default_text, MAX_CROSSPOST_TEXT)
        out.append({"member": member, "text": text})
    return {"crosspost": True, "crosspost_to": sorted(out, key=lambda t: t["member"])} if out else {}


class HumanGateway:
    def __init__(self, backend, limiter: Optional[RateLimiter] = None):
        self.backend = backend
        self.limiter = limiter or RateLimiter()
        self._lock = threading.Lock()

    # -- accounts --------------------------------------------------------------------------
    def state(self):
        try:
            ctx = self.backend.context()
        except Exception:  # noqa: BLE001 - the server is not reachable
            return 503, {"ok": False, "code": "unavailable"}
        return 200, {"ok": True, **ctx}

    def ensure(self, human_key, username=None, language=None):
        try:
            out = self.backend.ensure(str(human_key or ""), username, language)
        except ValueError:
            return 400, {"ok": False, "code": "invalid_request"}
        except Exception:  # noqa: BLE001
            return 503, {"ok": False, "code": "unavailable"}
        return 200, {"ok": True, **out}

    def _human(self, account_id):
        if not isinstance(account_id, str) or not account_id:
            return None
        user = self.backend.user(account_id)
        return user if user and user.get("user_type") == HUMAN_USER_TYPE else None

    # -- actions ---------------------------------------------------------------------------
    def actions(self, account_id, actions):
        if not isinstance(actions, list) or not actions or len(actions) > MAX_ACTIONS_PER_REQUEST:
            return 400, {"ok": False, "code": "invalid_request"}
        try:
            if self._human(account_id) is None:
                return 403, {"ok": False, "code": "not_allowed"}
            if not self.limiter.allow(account_id, len(actions)):
                return 429, {"ok": False, "code": "rate_limited"}
            ctx = self.backend.context()
        except Exception:  # noqa: BLE001
            return 503, {"ok": False, "code": "unavailable"}
        results = []
        with self._lock:
            for act in actions:
                results.append(self._one(account_id, act, ctx))
        return 200, {"ok": all(r.get("ok") for r in results), "results": results}

    def _one(self, uid, act, ctx):
        kind = act.get("type") if isinstance(act, dict) else None
        if kind not in ALLOWED_ACTIONS:
            return {"ok": False, "code": "invalid_request"}
        rid = ctx["round_id"]
        try:
            if kind == "post_photo":
                caption = _text(act.get("caption"), MAX_CAPTION)
                image = self._image(act)
                topics = [t for t in (act.get("topics") or []) if isinstance(t, str) and t.strip()][:10]
                data = {"user_id": uid, "round": rid, "image_url": image, "caption": caption, "topics": topics,
                        "filter_name": act.get("filter_name") if isinstance(act.get("filter_name"), str) else None,
                        "location_name": act.get("location_name") if isinstance(act.get("location_name"), str) else None,
                        **crosspost_fields(act.get("crosspost_to"), caption)}
                return {"ok": True, "photo_id": self.backend.post_photo(data)}
            if kind == "share":
                parent = self.backend.photo(str(act.get("photo_id") or ""))
                if not parent:
                    return {"ok": False, "code": "not_found"}
                caption = _text(act.get("caption"), MAX_CAPTION)
                data = {"user_id": uid, "round": rid, "image_url": parent.get("image_url"), "caption": caption,
                        "parent_photo_id": parent.get("id") or str(act["photo_id"]), "filter_name": parent.get("filter_name"),
                        "location_name": parent.get("location_name"),
                        "topic_ids": list(self.backend.photo_topics(parent.get("id")) or []),  # as the agents' share does
                        **crosspost_fields(act.get("crosspost_to"), caption)}
                return {"ok": True, "photo_id": self.backend.post_photo(data)}
            if kind == "comment":
                body = _text(act.get("body"), MAX_COMMENT, required=True)
                if not self.backend.photo(str(act.get("photo_id") or "")):
                    return {"ok": False, "code": "not_found"}
                parent = act.get("parent_comment_id")
                return {"ok": True, "comment_id": self.backend.comment(uid, str(act["photo_id"]), body, rid,
                                                                      str(parent) if parent else None)}
            if kind in ("react", "unreact"):
                pid = str(act.get("photo_id") or "")
                if not self.backend.photo(pid):
                    return {"ok": False, "code": "not_found"}
                if kind == "unreact":
                    return {"ok": bool(self.backend.unreact(uid, pid))}
                reaction = str(act.get("reaction_type") or "LIKE").upper()
                if reaction not in REACTIONS:
                    return {"ok": False, "code": "invalid_request"}
                return {"ok": True, "reaction_id": self.backend.react(uid, pid, reaction, rid)}
            target = str(act.get("user_id") or "")  # follow / unfollow
            if not target or target == uid or self.backend.user(target) is None:
                return {"ok": False, "code": "invalid_request" if target == uid or not target else "not_found"}
            if kind == "follow":
                return {"ok": True, "follow_id": self.backend.follow(uid, target, rid)}
            return {"ok": bool(self.backend.unfollow(uid, target, rid))}
        except ValueError:
            return {"ok": False, "code": "invalid_request"}
        except Exception:  # noqa: BLE001 - one bad action must not hide the others
            return {"ok": False, "code": "internal"}

    def _image(self, act):
        if isinstance(act.get("image_url"), str) and act["image_url"].strip():
            return act["image_url"].strip()[:400]
        data = act.get("image_base64")
        if not isinstance(data, str) or not data:
            raise ValueError("a photo needs image_url or image_base64")
        ext = str(act.get("extension") or "jpg").lower()
        if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
            raise ValueError("unsupported image type")
        try:
            raw = base64.b64decode(data, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("invalid image") from exc
        if not raw or len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("invalid image size")
        return self.backend.save_media(data, ext)

    # -- reading ---------------------------------------------------------------------------
    def feed(self, account_id, limit=20):
        try:
            if self._human(account_id) is None:
                return 403, {"ok": False, "code": "not_allowed"}
            return 200, {"ok": True, "photos": self.backend.feed(account_id, max(1, min(int(limit), 50)))}
        except ValueError:
            return 400, {"ok": False, "code": "invalid_request"}
        except Exception:  # noqa: BLE001
            return 503, {"ok": False, "code": "unavailable"}

    def comments(self, account_id, photo_id, limit=50):
        try:
            if self._human(account_id) is None:
                return 403, {"ok": False, "code": "not_allowed"}
            if not self.backend.photo(photo_id):
                return 404, {"ok": False, "code": "not_found"}
            return 200, {"ok": True, "comments": self.backend.comments(photo_id, max(1, min(int(limit), 100)))}
        except ValueError:
            return 400, {"ok": False, "code": "invalid_request"}
        except Exception:  # noqa: BLE001
            return 503, {"ok": False, "code": "unavailable"}
