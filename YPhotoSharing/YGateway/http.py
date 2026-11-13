"""Loopback HTTP transport of the human gateway (stdlib only).

Every request needs the per-run token in ``X-YPS-Gateway-Token`` (constant-time comparison, never logged). Bodies are
JSON of at most 6 MiB (a photo may travel as base64)."""

from __future__ import annotations

import hmac
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .core import HumanGateway

logger = logging.getLogger("YPhotoSharing.Gateway")
MAX_BODY = 6 * 1024 * 1024
TOKEN_HEADER = "X-YPS-Gateway-Token"


def dispatch(gw: HumanGateway, method: str, parts: list, q: dict, body: dict):
    """Route one request (`GET`/`POST` on `/v1/...`) to the gateway; returns (status, payload). Shared with offline."""
    acct = q.get("account_id") or body.get("account_id") or ""
    try:
        if parts == ["v1", "state"] and method == "GET":
            return gw.state()
        if parts == ["v1", "humans", "ensure"] and method == "POST":
            return gw.ensure(str(body.get("human_key") or ""), body.get("username"), body.get("language"))
        if parts == ["v1", "actions"] and method == "POST":
            return gw.actions(acct, body.get("actions"))
        if parts == ["v1", "feed"] and method == "GET":
            return gw.feed(acct, int(q.get("limit", 20)))
        if len(parts) == 4 and parts[:2] == ["v1", "photos"] and parts[3] == "comments" and method == "GET":
            return gw.comments(acct, parts[2], int(q.get("limit", 50)))
        return 404, {"ok": False, "code": "not_found"}
    except ValueError:
        return 400, {"ok": False, "code": "invalid_request"}
    except Exception:  # noqa: BLE001 - a gateway bug must not kill the service
        logger.exception("gateway request failed")
        return 500, {"ok": False, "code": "internal"}


class GatewayHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, gateway: HumanGateway, token: str):
        super().__init__(address, _Handler)
        self.gateway, self.token = gateway, token


class _Handler(BaseHTTPRequestHandler):
    server: GatewayHTTPServer

    def log_message(self, fmt, *args):  # no access log: it would carry query strings
        return

    def _send(self, status: int, body: dict) -> None:
        raw = json.dumps(body, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authorised(self) -> bool:
        return hmac.compare_digest(self.headers.get(TOKEN_HEADER, "").encode(), self.server.token.encode())

    def _body(self) -> Optional[dict]:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return None
        if length > MAX_BODY:
            return None
        try:
            data = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _route(self, method: str):
        if not self._authorised():
            return self._send(401, {"ok": False, "code": "unauthorised"})
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        q = {k: v[0] for k, v in parse_qs(url.query).items()}
        body = {}
        if method == "POST":
            body = self._body()
            if body is None:
                return self._send(400, {"ok": False, "code": "invalid_request"})
        self._send(*dispatch(self.server.gateway, method, parts, q, body))

    def do_GET(self):  # noqa: N802
        self._route("GET")

    def do_POST(self):  # noqa: N802
        self._route("POST")


def serve(gateway: HumanGateway, token: str, host: str = "127.0.0.1", port: int = 0) -> GatewayHTTPServer:
    """Start the gateway on a background thread and return the server (`server_address` has the port)."""
    server = GatewayHTTPServer((host, port), gateway, token)
    threading.Thread(target=server.serve_forever, name="yps-gateway", daemon=True).start()
    return server
