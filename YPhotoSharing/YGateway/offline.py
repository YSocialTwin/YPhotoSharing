"""Offline participation: a person acts while the server is not running.

The request is applied to the database of the experiment by an in-process `LocalBackend`, under an exclusive file lock
so two requests never write at once, in the round at which the experiment stopped. With the server running the request
is refused with 409: the person goes through the online gateway. A cross-post asked offline is recorded exactly like
an online one and leaves at the first barrier after the restart."""

import fcntl
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

from .core import HumanGateway
from .http import dispatch

LOCK_FILE = "human_gateway.lock"
RUNNING_MARKER = "ray_ready.temp"


def server_running(folder) -> bool:
    return (Path(folder) / RUNNING_MARKER).exists()


def handle_offline(folder, method: str, parts: list, q: dict, body: Dict[str, Any],
                   backend_factory: Callable[[Path], Any]) -> Tuple[int, Dict[str, Any]]:
    """Apply one gateway request (same routes as the HTTP one) to the database of `folder`."""
    folder = Path(folder)
    if not isinstance(body, dict) or method not in ("GET", "POST"):
        return 400, {"ok": False, "code": "invalid_request"}
    if server_running(folder):
        return 409, {"ok": False, "code": "server_running"}
    with open(folder / LOCK_FILE, "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            return dispatch(HumanGateway(backend_factory(folder)), method, parts, q or {}, body)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
