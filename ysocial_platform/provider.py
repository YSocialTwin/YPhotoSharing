"""The photo-sharing platform: what YSocial needs to know to run, show and manage a YPhotoSharing experiment.

The provider is declared in ``meta/registry.json`` (``platform`` section) and loaded by YSocial at startup.
It talks to the core through ``y_web.sdk`` only; the platform-specific modules (``photo/``, ``routes/``) are
part of this repository.

The experiment database is the schema of the Y server (``YPhotoSharing.YServer.classes.models``), which this
runtime ships: the platform depends on that schema being importable from the installed runtime.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, List, Mapping, Optional, Tuple

from y_web.sdk import (
    COMMON_FRONTEND_CAPABILITIES,
    HPC,
    N_,
    CreationRules,
    HpcClientForm,
    PlatformProvider,
    ServerConfigRequest,
)
from y_web.sdk import gettext as _
from y_web.sdk import services


class PhotoSharing(PlatformProvider):
    key = "photo_sharing"
    label = N_("Photo sharing")
    icon = "camera"
    order = 30

    library_package = f"{__package__}.photo"
    database_file_name = "yphotosharing.db"
    participant_is_account = True
    admin_view_session_keys = ("photo_view_user_id", "photo_switch_user_id")

    def attach_routes(self):
        importlib.import_module(f"{__package__}.routes")

    def entry_url(self, exp_id: int, user_id: int) -> Optional[str]:
        return f"/{exp_id}/photo/feed/all/feed/rf/1"

    def creation_rules(self, simulator_type: str) -> CreationRules:
        return CreationRules(database="server")

    def resolve_simulator(self, simulator_type: str, available: Mapping[str, bool]):
        if not available["photo_sharing"]:
            return HPC, _(
                "Photo Sharing experiments are unavailable because YPhotoSharing is not present."
            )
        return HPC, None

    def hpc_server_config(self, request: ServerConfigRequest) -> dict:
        return self.library("server_config").generate_photo_sharing_config(
            exp_name=request.exp_name,
            db_type=request.db_type,
            db_uri=request.db_uri,
            topics=request.topics,
            data_path=request.data_path,
            db_config_dict=request.db_config_dict,
            is_remote=request.is_remote,
        )

    def write_new_experiment_files(self, exp_dir: str, prompt_language: str) -> None:
        services.write_prompt_pack(
            "prompts_ygram.json",
            os.path.join(exp_dir, "prompts_ygram.json"),
            prompt_language,
        )

    details_template = "@photo_sharing/admin/experiment_details_photo.html"
    frontend_capabilities = COMMON_FRONTEND_CAPABILITIES | {
        "show_suggested_friends",  # "Suggestions for you" rail
        "show_recsys_info",
        "show_annotation_stats",
        "interaction_share",
        "annotation_agent_type",
        "default_photo_feed_tab",
    }
    frontend_exclusive_settings = frozenset({"default_photo_feed_tab"})  # home tab
    extra_prompt_files = ("prompts_ygram.json",)
    prompt_pack = ("prompts_ygram.json", "prompts_ygram.json")

    def experiment_prompt_pack(self, simulator_type: str) -> Tuple[str, str]:
        return self.prompt_pack

    def clients_page(self, simulator_type: str) -> str:
        return "clientsr.clients_photo"

    def hpc_client_files(self, exp_folder: str, client: Any, population: Any):
        config, agents, _ = super().hpc_client_files(exp_folder, client, population)
        return config, agents, os.path.join(exp_folder, "prompts_ygram.json")

    def prepare_hpc_client_files(
        self, exp_folder: str, client: Any, population: Any, client_config: str
    ) -> None:
        self.library("hpc").migrate_legacy_layout(
            exp_folder, client.name, population.name, client_config
        )

    def normalize_hpc_client_config(
        self, exp_folder: str, client_name: str, population_name: str, client_path: str
    ) -> bool:
        try:
            self.library("hpc").normalize_client_config(
                exp_folder, client_name, population_name, client_path
            )
        except Exception:
            pass  # a client file that could not be aligned still starts, as before
        return True

    def client_state_files(self, exp_dir: Path, client: Any) -> List[Path]:
        # the state of the client of a population, then any other population of the same client
        return list(exp_dir.glob(f"client_{client.name}-*.state.json"))

    def hpc_client_sections(
        self, form: HpcClientForm
    ) -> Optional[Tuple[dict, dict, dict]]:
        return self.library("hpc_client").sections(form)

    def finish_hpc_client_config(
        self, config: dict, form: HpcClientForm, exp_dir: str, population_name: str
    ) -> bool:
        self.library("hpc").finish_client_config(config, form, exp_dir, population_name)
        return True

    def hpc_agent_payload(
        self,
        payload: dict,
        agent: Any,
        ext_map: Mapping[str, Any],
        *,
        is_page: bool = False,
        normalize_recsys: bool = True,
    ) -> None:
        agents = self.library("agents")
        if is_page:
            payload["recsys_type"] = "0"
            payload["frecsys_type"] = "default"
            return
        if normalize_recsys:
            payload["recsys_type"] = agents.cluster_id(payload.get("recsys_type"))
        agents.apply_agent_fields(payload, agent, ext_map)

    def form_sections_available(self, admin_user: Any) -> bool:
        return self.library("forms").available(admin_user)

    def population_form_config(
        self, form: Mapping[str, Any], username_type: str, admin_user: Any
    ) -> Optional[dict]:
        return self.library("forms").population_config(form, username_type, admin_user)

    def population_agent_ext(
        self, agent: Any, config: Optional[dict], population: Any
    ) -> Optional[list]:
        if config is None and getattr(population, "username_type", "") != self.key:
            return None
        return self.library("forms").agent_ext_values(agent, config)

    def agent_payload_ext(self, agent_payload: Mapping[str, Any]) -> list:
        return self.library("forms").payload_ext(agent_payload)

    def default_avatar_url(self, user: Any) -> Optional[str]:
        return self.library("forms").default_avatar_url(user)

    def agent_form_context(self) -> dict:
        forms = self.library("forms")
        return {
            "story_visibility_options": forms.STORY_VISIBILITY,
            "creator_tier_options": forms.CREATOR_TIERS,
        }

    def agent_form_ext(self, form: Mapping[str, Any], admin_user: Any) -> dict:
        return self.library("forms").agent_ext(form, admin_user)

    def ensure_database_schema(self, engine: Any, uri: Optional[str] = None) -> bool:
        """Create the complete YPhotoSharing schema (it has its own SQLAlchemy base, with ``user_mgmt``).

        The runtime is imported lazily so a missing or half-initialised photo database can be repaired on first
        use; when the runtime cannot be imported the experiment still gets the tables the core reads.
        """
        from y_web.sdk import runtime

        try:
            external_root = Path(runtime.get_external_repo_dir("YPhotoSharing"))
            if external_root.exists() and str(external_root) not in sys.path:
                sys.path.insert(0, str(external_root))
            from YPhotoSharing.YServer.classes.models import Base as PhotoBase

            PhotoBase.metadata.create_all(bind=engine)
        except Exception:
            pass
        if uri:
            services.ensure_experiment_schema(uri)
        return True
