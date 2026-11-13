"""Creation of the account of a person, shared by the server (online) and the local backend (offline)."""

import re
import uuid

HUMAN_USER_TYPE = "human"
_NAMESPACE = uuid.UUID("5b0f6a84-79a2-4cd1-8d7e-6f0a8d5e1b21")


def human_account_id(human_key: str) -> str:
    """The same person always gets the same account id on this platform."""
    return str(uuid.uuid5(_NAMESPACE, f"yphotosharing:human:{human_key}"))


def global_id_of(human_key: str) -> str:
    return f"human:{human_key}"


def clean_username(name, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]", "_", str(name or "").strip())[:40]
    return text or fallback


def ensure_human(db, adapter, round_id, human_key, username=None, language=None) -> dict:
    """Create the account of the person `human_key` (idempotent) and, with a federation, record its `human:` identity.

    Returns {"account_id", "global_agent_id" (None without a federation), "created"}. The account is never driven by
    an agent client: `user_type` is "human", `round_actions` 0."""
    human_key = str(human_key or "").strip()
    if not human_key or len(human_key) > 100 or ":" in human_key:
        raise ValueError("invalid human_key")
    uid = human_account_id(human_key)
    existing = db.get_user(uid)
    created = existing is None
    if created:
        base = clean_username(username, f"human_{uid[:8]}")
        name, n = base, 0
        while db.get_user_by_username(name) is not None:
            n += 1
            name = f"{base[:44]}_{uid[:4]}{n if n > 1 else ''}"
        db.create_user({"id": uid, "username": name, "language": language or "en", "user_type": HUMAN_USER_TYPE,
                        "round_actions": 0, "daily_activity_level": 0, "password": "!", "joined_on": round_id})
    elif existing.get("user_type") != HUMAN_USER_TYPE:
        raise ValueError("the account is not a human one")
    gid = None
    if adapter is not None:
        gid = global_id_of(human_key)
        adapter.register_human(uid, gid)
    return {"account_id": uid, "global_agent_id": gid, "created": created}
