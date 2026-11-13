"""Run the human gateway of an experiment folder (started by the web application after the server).

Usage: python run_gateway.py <experiment_folder>

Connects to the running server actor like a client does, serves on loopback, writes ``human_gateway.json`` (host, port,
pid; never the token) and runs until interrupted. The per-run token comes from ``YPHOTOSHARING_GATEWAY_TOKEN`` (>= 16
characters). Host and port: ``human.gateway`` of server_config.json (default 127.0.0.1, free port).
"""

import json
import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path

from YPhotoSharing.YGateway import HumanGateway, OnlineBackend, serve

STATE_FILE = "human_gateway.json"
EXIT_OK, EXIT_INVALID, EXIT_SERVER_UNREACHABLE = 0, 2, 3


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__)
        return EXIT_INVALID
    folder = Path(argv[0]).resolve()
    token = os.environ.get("YPHOTOSHARING_GATEWAY_TOKEN", "")
    if len(token) < 16:
        print("YPHOTOSHARING_GATEWAY_TOKEN (>= 16 chars) is required", file=sys.stderr)
        return EXIT_INVALID
    try:
        config = json.loads((folder / "server_config.json").read_text())
    except (OSError, ValueError) as exc:
        print(f"invalid server_config.json: {exc}", file=sys.stderr)
        return EXIT_INVALID
    gw_cfg = (config.get("human") or {}).get("gateway") or {}
    import ray

    ready = folder / "ray_ready.temp"
    deadline = time.time() + 180
    while not ready.exists():
        if time.time() > deadline:
            print("server not ready (no ray_ready.temp)", file=sys.stderr)
            return EXIT_SERVER_UNREACHABLE
        time.sleep(0.2)
    address = (folder / "ray_config.temp").read_text().strip()
    namespace = (folder / "ray_namespace.temp").read_text().strip()
    ray.init(address=address, namespace=namespace, include_dashboard=False, logging_level=logging.WARNING)
    actor = ray.get_actor(config.get("server_name", "orchestrator_server"), namespace=namespace)

    def call(method, *args):
        return ray.get(getattr(actor, method).remote(*args), timeout=30)

    server = serve(HumanGateway(OnlineBackend(call)), token, gw_cfg.get("host", "127.0.0.1"), int(gw_cfg.get("port", 0)))
    host, port = server.server_address[:2]
    state, tmp = folder / STATE_FILE, folder / (STATE_FILE + ".tmp")
    tmp.write_text(json.dumps({"host": host, "port": port, "pid": os.getpid()}))
    os.replace(tmp, state)
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    stop.wait()
    server.shutdown()
    try:
        state.unlink()
    except OSError:
        pass
    ray.shutdown()
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
