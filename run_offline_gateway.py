"""Offline entry of a person: one JSON request on stdin, one JSON answer on stdout.

Usage: python run_offline_gateway.py <experiment_folder>
stdin:  {"method": "POST", "path": "/v1/actions", "query": {...}, "body": {...}}

Works only while the server is stopped (see YPhotoSharing/YGateway/offline.py): the same routes and actions as the
online gateway, applied to the experiment database under a file lock. Exit 0 with the HTTP-like status in the answer.
"""

import json
import sys
from pathlib import Path

from YPhotoSharing.YGateway.core import LocalBackend
from YPhotoSharing.YGateway.offline import handle_offline


def backend_factory(folder: Path) -> LocalBackend:
    from YPhotoSharing.YServer.classes.db_middleware import DatabaseMiddleware
    from YPhotoSharing.YServer.services.media_service import MediaService

    config = json.loads((folder / "server_config.json").read_text())
    db_config = config.get("database") or {"type": "sqlite", "sqlite": {"filename": "yphotosharing.db"}}
    db = DatabaseMiddleware(db_config, folder)
    adapter = None
    section = config.get("federation") or {}
    if section.get("enabled"):
        from types import SimpleNamespace

        from YPhotoSharing.YServer.federation.adapter import YPhotoSharingAdapter

        host = SimpleNamespace(_db=db, current_round_id=None, _current_day=0, _current_hour=0, config_path=folder)
        adapter = YPhotoSharingAdapter(section["member"], int(section.get("federation_id", 1)), host=host,
                                       accounts=section.get("accounts"), export_policy=section.get("export_policy", "marked"),
                                       emit_exposures=bool(section.get("exposures", False)),
                                       crosspost_mode=section.get("crosspost_mode", "coordinator_rule"))
    return LocalBackend(db, adapter, MediaService(storage_dir=str(folder / "media")))


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return 2
    folder = Path(argv[0]).resolve()
    try:
        request = json.loads(sys.stdin.read() or "{}")
        parts = [p for p in str(request.get("path", "")).split("/") if p]
        method = str(request.get("method", "POST")).upper()
        (folder / "server_config.json").stat()
    except (json.JSONDecodeError, OSError):
        print(json.dumps({"ok": False, "status": 400, "code": "invalid_request"}))
        return 2
    status, body = handle_offline(folder, method, parts, request.get("query") or {}, request.get("body") or {}, backend_factory)
    print(json.dumps({**body, "status": status}, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
