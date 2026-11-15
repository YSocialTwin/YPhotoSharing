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
    FieldGroup,
    HPC,
    N_,
    CreationRules,
    FederationTraits,
    FrontendSetting,
    HpcClientForm,
    PlatformProvider,
    ServerConfigRequest,
)
from y_web.sdk import gettext as _
from y_web.sdk import services


class PhotoSharing(PlatformProvider):
    key = "photo_sharing"
    admin_css = ("css/photo-admin.css",)
    #: texts of the plugin catalogue / repository metadata that the core translation catalogue carries
    catalog_texts = (
        N_(
            "Simulation runtime for photo-sharing experiments, with an Instagram-like platform."
        ),
    )
    label = N_("Photo sharing")
    icon = "camera"
    order = 30
    badge_text = N_("Photo Sharing")
    badge_palette = (
        "#0ea5e9",
        "#38bdf8",
        "#7dd3fc",
        "#0284c7",
        "#0369a1",
        "#bae6fd",
        "#075985",
        "#67e8f9",
    )
    frontend_annotations_hint = N_("Choose which labels are displayed on photos.")
    content_schema = {
        "requires": ("photos",),
        "signals": ("photo_topics", "photo_hashtags", "photo_emotions"),
        "content_table": "photos",
        "topic_table": "photo_topics",
        "hashtag_table": "photo_hashtags",
        "emotion_table": "photo_emotions",
        "content_id_column": "photo_id",
        "reaction_id_column": "photo_id",
        "recommendation_ids_column": "photo_ids",
        "text_column": "caption",
        "summary_expression": "COALESCE(NULLIF(TRIM({p}caption), ''), NULLIF(TRIM({p}alt_text), ''), NULLIF(TRIM({p}image_url), ''))",
        "reported_content_type": "photo",
        "wording": {
            "annotated": N_("Annotated Photos"),
            "polarity": N_("Current polarity breakdown across annotated photos."),
            "polarity_by_day": N_(
                "Positive, neutral, and negative photo counts by day."
            ),
            "polarized": N_("Most Polarized Photos"),
            "emotions": N_("Current distribution of annotated photos."),
            "volume": N_(
                "Total emotion tags versus distinct annotated photos per day."
            ),
        },
    }

    # Tables this platform adds to the standard experiment database (the core creates them with its own).
    experiment_tables = {
        "sqlite": {
            "photos": "\n        CREATE TABLE IF NOT EXISTS photos (\n            id TEXT PRIMARY KEY,\n            user_id TEXT NOT NULL REFERENCES user_mgmt(id) ON DELETE CASCADE,\n            round TEXT NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,\n            image_url TEXT NOT NULL,\n            thumbnail_url TEXT,\n            caption TEXT,\n            alt_text TEXT,\n            filter_name TEXT,\n            location_name TEXT,\n            latitude REAL,\n            longitude REAL,\n            is_carousel INTEGER DEFAULT 0,\n            carousel_index INTEGER DEFAULT 0,\n            parent_photo_id TEXT REFERENCES photos(id) ON DELETE SET NULL,\n            num_likes INTEGER DEFAULT 0,\n            num_comments INTEGER DEFAULT 0,\n            num_shares INTEGER DEFAULT 0,\n            is_sponsored INTEGER DEFAULT 0,\n            embedding TEXT,\n            aesthetic_score REAL,\n            viral_score REAL DEFAULT 0.0,\n            sentiment_score REAL,\n            media_url TEXT,\n            is_removed INTEGER DEFAULT 0,\n            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,\n            deleted_at DATETIME\n        )\n    ",
            "stories": "\n        CREATE TABLE IF NOT EXISTS stories (\n            id TEXT PRIMARY KEY,\n            user_id TEXT NOT NULL REFERENCES user_mgmt(id) ON DELETE CASCADE,\n            round TEXT NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,\n            media_url TEXT NOT NULL,\n            media_type TEXT DEFAULT 'carousel',\n            duration_seconds INTEGER DEFAULT 5,\n            sticker_type TEXT,\n            sticker_data TEXT,\n            caption TEXT,\n            title TEXT NOT NULL,\n            description TEXT NOT NULL,\n            image_urls TEXT NOT NULL DEFAULT '[]',\n            view_count INTEGER DEFAULT 0,\n            expires_at DATETIME,\n            created_at DATETIME DEFAULT CURRENT_TIMESTAMP\n        )\n    ",
            "saved_photos": "\n        CREATE TABLE IF NOT EXISTS saved_photos (\n            id TEXT PRIMARY KEY,\n            user_id TEXT NOT NULL REFERENCES user_mgmt(id) ON DELETE CASCADE,\n            photo_id TEXT NOT NULL REFERENCES photos(id) ON DELETE CASCADE,\n            round TEXT NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,\n            created_at DATETIME DEFAULT CURRENT_TIMESTAMP\n        )\n    ",
            "story_views": "\n        CREATE TABLE IF NOT EXISTS story_views (\n            id TEXT PRIMARY KEY,\n            story_id TEXT NOT NULL REFERENCES stories(id) ON DELETE CASCADE,\n            viewer_id TEXT NOT NULL REFERENCES user_mgmt(id) ON DELETE CASCADE,\n            round TEXT NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,\n            viewed_at DATETIME DEFAULT CURRENT_TIMESTAMP\n        )\n    ",
        },
        "postgresql": {
            "saved_photos": "\n        CREATE TABLE IF NOT EXISTS saved_photos (\n            id VARCHAR(36) PRIMARY KEY,\n            user_id VARCHAR(36) NOT NULL REFERENCES user_mgmt(id) ON DELETE CASCADE,\n            photo_id VARCHAR(36) NOT NULL REFERENCES photos(id) ON DELETE CASCADE,\n            round VARCHAR(36) NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,\n            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        )\n    ",
            "story_views": "\n        CREATE TABLE IF NOT EXISTS story_views (\n            id VARCHAR(36) PRIMARY KEY,\n            story_id VARCHAR(36) NOT NULL REFERENCES stories(id) ON DELETE CASCADE,\n            viewer_id VARCHAR(36) NOT NULL REFERENCES user_mgmt(id) ON DELETE CASCADE,\n            round VARCHAR(36) NOT NULL REFERENCES rounds(id) ON DELETE CASCADE,\n            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP\n        )\n    ",
        },
    }
    experiment_columns = {
        "sqlite": {"saved_photos": {"round": "TEXT"}, "story_views": {"round": "TEXT"}},
        "postgresql": {
            "saved_photos": {"round": "VARCHAR(36)"},
            "story_views": {"round": "VARCHAR(36)"},
        },
    }
    frontend_labels = {
        "interaction_post": (N_("New photo"), N_("Share a new photo")),
        "interaction_like": (N_("Like"), N_("Heart reaction on photos")),
        "interaction_comment": (
            N_("Comment"),
            N_("Comment on photos and reply to comments"),
        ),
        "interaction_share": (N_("Send / share"), N_("Send a photo to others")),
        "annotation_agent_type": (
            N_("Agent type"),
            N_("Badge identifying ad-hoc agents next to the author name"),
        ),
        "show_suggested_friends": (
            N_("Suggestions"),
            N_('Show the "Suggestions for you" box beside the feed'),
        ),
        "show_recsys_info": (
            N_("Recommender info"),
            N_("Show the content recommender system box beside the feed"),
        ),
        "show_annotation_stats": (
            N_("Annotation statistics"),
            N_("Show the live annotation statistics box beside the feed"),
        ),
    }
    menu_label = N_("Photo Sharing (e.g., Instagram)")
    badge = "photo"
    hpc_redis = True
    experiment_free_paths = ("/photo/feed",)

    def _feed_url(self, exp_id):
        from flask import url_for

        return url_for(
            "main.photo_feed",
            exp_id=exp_id,
            user_id="all",
            timeline="feed",
            mode="rf",
            page=1,
            tab="for_you",
        )

    def after_follow_url(self, exp_id, referrer):
        if "/photo/suggestions" in referrer or not referrer:
            return self._feed_url(exp_id)
        return None

    field_groups = (
        FieldGroup(
            "photo_sharing",
            N_("Photo Sharing"),
            "photo",
            extension_fields={
                "creator_tier": N_("Creator tier"),
                "story_visibility": N_("Story visibility"),
                "is_private": N_("Private account"),
                "is_verified": N_("Verified account"),
                "attention_budget": N_("Attention budget"),
                "favorite_filters": N_("Favourite filters"),
                "bio": N_("Has a biography"),
            },
            weight=20,
        ),
    )

    uuid_follow_ids = True  # the ids of its follow rows are UUIDs in every runtime

    # the pages the participants share
    reads_server_config = True

    def profile_redirect(self, exp, user, page):
        return f"/{exp.idexp}/photo/profile/{user.id}/recent/{page}"

    def page_context(self, exp, ui):
        annotations = bool(ui.get("annotations_enabled", True))
        return {
            "platform_ui": "photo",
            "forum_show_emotions": annotations
            and bool(ui.get("annotation_emotions", True)),
            "forum_show_topics": annotations
            and bool(ui.get("annotation_topics", True)),
        }

    # what the admin "frontend settings" page offers for this platform (the box is in templates/slots/)
    frontend_settings = (
        FrontendSetting(
            "default_photo_feed_tab",
            "for_you",
            choices=(
                {"name": "for_you", "label": N_("For you (recommended)")},
                {"name": "follower", "label": N_("Following")},
            ),
        ),
    )

    @property
    def human_gateway(self):
        """How a person of a World Simulation gets an account here and acts (``gateway.py``)."""
        return importlib.import_module(f"{__package__}.gateway").HUMAN_GATEWAY

    @property
    def human_recsys(self):
        """The recommender systems of the people who use the frontend (``recsys/``)."""
        return importlib.import_module(f"{__package__}.recsys").RECSYS

    server_label = "YPhotoSharing"
    runtime_keys = ("photo_sharing",)
    hpc_launch = {
        "runtime_repo": "YPhotoSharing",
        "supports_gunicorn": False,
        "frozen_server_runs_script": True,
        "client_config_only": True,
        "normalizes_client_config": True,
        "prompts_filename": "prompts_ygram.json",
        "orchestrator_actor": "orchestrator_server",
        "client_actor_prefix": "Client_",
        "supports_federation": True,
    }
    tag_runtime_sets = (("photo_sharing",),)
    federation_traits = FederationTraits(
        mdi_icon="mdi-image-multiple-outline",
        local_kind="photo",
        author_sql="SELECT p.id, u.username, p.user_id FROM photos p LEFT JOIN user_mgmt u ON u.id = p.user_id WHERE p.id IN ({q})",
        content_path="/{exp}/photo/profile/{author}/recent/1#feed-post-{id}",
        profile_path="/{exp}/photo/profile/{account}/recent/1",
        account_sql="SELECT id, username FROM user_mgmt WHERE id = ?",
        text_limit=300,
        decision_triggers=("publish", "interaction"),
        simulators=(HPC,),
    )

    library_package = f"{__package__}.photo"
    database_file_name = "yphotosharing.db"
    participant_is_account = True
    admin_view_session_keys = ("photo_view_user_id", "photo_switch_user_id")

    has_population_fields = True

    def carries_population_fields(self, population):
        from sqlalchemy import select
        from y_web import db
        from y_web.src.models import Agent_Ext, Agent_Population

        return bool(
            db.session.scalar(
                select(Agent_Ext.agent_id)
                .join(Agent_Population, Agent_Population.agent_id == Agent_Ext.agent_id)
                .where(
                    Agent_Population.population_id == population.id,
                    Agent_Ext.feature_name == "creator_tier",
                )
                .limit(1)
            )
        )

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
