"""The human gateway of photo sharing, as YSocial's World Simulation talks to it.

The gateway is a process of its own (``run_gateway.py``) that YSocial starts next to the server; YSocial writes
``human_gateway.token`` and ``human_gateway.json`` (host, port, pid) in the experiment folder. When the server is stopped
the person acts through the runtime script (``run_offline_gateway.py``).
"""

from __future__ import annotations

import os
import subprocess

from y_web.sdk import HumanGatewayTraits

ENSURE_PATH = "/v1/humans/ensure"


def ensure_body(key, username, human_id, language):
    return {"human_key": key, "username": username, "language": language}


def actions_request(account_id, username, key, actions):
    return "/v1/actions", {"account_id": account_id, "actions": actions}


def offline_ensure(paths, body):
    return [str(paths.folder)], {"method": "POST", "path": ENSURE_PATH, "body": body}


def offline_actions(paths, path, body):
    return [str(paths.folder)], {"method": "POST", "path": path, "body": body}


def start_process(launch):
    """The gateway process: ``(process, state)``; the process writes ``human_gateway.json`` itself."""
    script = os.path.join(launch.repo_dir, "run_gateway.py")
    if not os.path.exists(script):
        raise FileNotFoundError(f"{script} not found: update the photo sharing runtime")
    proc = subprocess.Popen(
        [launch.python, script, str(launch.folder)],
        cwd=launch.repo_dir,
        env=dict(os.environ, YPHOTOSHARING_GATEWAY_TOKEN=launch.token),
        stdin=subprocess.DEVNULL,
        **launch.popen_kwargs,
    )
    return proc, None


def share(photo_id, caption: str, targets: list) -> dict:
    return {
        "type": "share",
        "photo_id": photo_id,
        "caption": caption,
        "crosspost_to": targets,
    }


def post(
    caption: str,
    targets: list,
    *,
    image_base64: str = "",
    extension: str = "",
    image_url: str = "",
) -> dict:
    action = {"type": "post_photo", "caption": caption, "crosspost_to": targets}
    if image_url:
        action["image_url"] = image_url
    else:
        action.update(image_base64=image_base64, extension=extension)
    return action


def build_action(text, targets, post_id=None, community=None):
    """The composer reposts a photo; it does not make a photo from words."""
    return share(post_id, text, targets) if post_id else None


HUMAN_GATEWAY = HumanGatewayTraits(
    repo="YPhotoSharing",
    token_header="X-YPS-Gateway-Token",
    ensure_path=ENSURE_PATH,
    actions_path="/v1/actions",
    key_template="{user_id}",  # the runtime derives the identity from the key (``human:<key>``)
    ensure_body=ensure_body,
    actions_request=actions_request,
    offline_ensure=offline_ensure,
    offline_actions=offline_actions,
    start_process=start_process,
    build_action=build_action,
)
