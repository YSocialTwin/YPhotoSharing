"""The page where the clients of a photo-sharing experiment are created."""

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required
from y_web.sdk import gettext as _
from y_web.sdk.routes import blueprint
from y_web.sdk.runtime import is_vllm_installed
from y_web.sdk.web import (
    build_client_creation_context,
    check_privileges,
    experiment_configuration_update_required,
    redirect_to_clients_page,
)

from ..photo.agents import PHOTO_SHARING_LIKERT_SCALE

clientsr = blueprint("clients")

CLIENT_DEFAULTS = {
    "start_day": 0,
    "use_local_diffusion": True,
    "local_diffusion_model": "segmind/tiny-sd",
    "enable_memory_annotations": True,
    "logging": {
        "enable_console_log": True,
        "enable_execution_log": True,
        "enable_action_log": False,
        "enable_prompt_log": False,
    },
    "actions": {
        "post_photo": 0.15,
        "react": 0.20,
        "comment": 0.15,
        "follow": 0.10,
        "share": 0.05,
        "report": 0.05,
        "save": 0.10,
        "reply_comment": 0.10,
        "unfollow": 0.05,
        "send_dm": 0.05,
        "post_story": 0.05,
        "watch_story": 0.05,
    },
    "hourly_activity": {
        "0": 0.2,
        "1": 0.1,
        "2": 0.05,
        "3": 0.05,
        "4": 0.1,
        "5": 0.2,
        "6": 0.4,
        "7": 0.6,
        "8": 0.8,
        "9": 0.9,
        "10": 0.8,
        "11": 0.8,
        "12": 0.9,
        "13": 0.9,
        "14": 0.8,
        "15": 0.8,
        "16": 0.8,
        "17": 0.9,
        "18": 1.0,
        "19": 1.0,
        "20": 1.0,
        "21": 0.9,
        "22": 0.6,
        "23": 0.4,
    },
}


@clientsr.route("/admin/clients_photo/<idexp>")
@login_required
def clients_photo(idexp):
    """Render the dedicated photo-sharing HPC client creation page."""
    check_privileges(current_user.username)

    context = build_client_creation_context(idexp, "HPC")
    exp = context["experiment"]
    if exp is None:
        flash(_("Experiment not found."), "error")
        return redirect(url_for("experiments.settings"))
    misplaced = redirect_to_clients_page(exp, "clientsr.clients_photo")
    if misplaced is not None:
        return misplaced
    if experiment_configuration_update_required(exp):
        flash(
            _(
                "Update Experiment Configuration before creating clients for this experiment."
            ),
            "warning",
        )
        return redirect(url_for("experiments.experiment_details", uid=idexp))

    context["embedded_vllm_available"] = bool(is_vllm_installed())
    context["photo_client_defaults"] = CLIENT_DEFAULTS
    context["photo_likert_scale"] = PHOTO_SHARING_LIKERT_SCALE
    return render_template("@photo_sharing/admin/clients_photo.html", **context)
