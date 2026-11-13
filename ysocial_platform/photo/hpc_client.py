"""The simulation, agents and logging sections of the client of a photo-sharing experiment."""

from sqlalchemy import select
from y_web.sdk.models import OpinionGroup, db

from .agents import PHOTO_SHARING_LIKERT_SCALE
from .agents import activity_profiles as _photo_sharing_activity_profiles


def sections(form):
    """``(simulation, agents, logging)`` of a new client, from the values of the creation form."""
    start_day = int(form.form_data.get("start_day", "0"))
    use_local_diffusion = form.form_data.get("use_local_diffusion") in {
        "on",
        "true",
        "1",
        "yes",
    }
    local_diffusion_model = str(
        form.form_data.get("local_diffusion_model", "segmind/tiny-sd")
    ).strip()
    enable_memory_annotations = form.form_data.get(
        "enable_memory_annotations", "true"
    ) in {"on", "true", "1", "yes"}
    opinion_model_name = (
        str(form.form_data.get("update_rule", "llm_evaluation")).strip()
        or "llm_evaluation"
    )
    llm_evaluation_scope = (
        str(form.form_data.get("llm_evaluation_scope", "interlocutor_only")).strip()
        or "interlocutor_only"
    )
    photo_action_defaults = {
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
    }
    photo_actions_likelihood = {
        key: float(form.form_data.get(key, str(default)))
        for key, default in photo_action_defaults.items()
    }
    photo_logging_config = {
        "enable_console_log": form.form_data.get("enable_console_log", "true")
        in {"on", "true", "1", "yes"},
        "enable_execution_log": form.form_data.get("enable_execution_log", "true")
        in {"on", "true", "1", "yes"},
        "enable_action_log": form.form_data.get("enable_action_log")
        in {
            "on",
            "true",
            "1",
            "yes",
        },
        "enable_prompt_log": form.form_data.get("enable_prompt_log")
        in {
            "on",
            "true",
            "1",
            "yes",
        },
        "enable_actor_log": True,
        "enable_client_log": True,
        "enable_llm_usage_log": True,
    }
    photo_opinion_groups = {
        group.name: [group.lower_bound, group.upper_bound]
        for group in db.session.scalars(
            select(OpinionGroup).order_by(OpinionGroup.lower_bound.asc())
        ).all()
    }
    if form.llm_backend == "ollama":
        form.llm_config.setdefault("backend", "ollama")
        form.llm_config.setdefault("use_vllm", False)
        form.llm_config.setdefault("use_remote_batch", False)
        if form.llm_v_config is not None:
            form.llm_v_config.setdefault("backend", "ollama")
    elif form.llm_v_config is not None:
        form.llm_v_config.setdefault("backend", "vllm")

    simulation_config = {
        "num_rounds": max(form.days, 1) * 24,
        "start_day": start_day,
        "use_local_diffusion": bool(use_local_diffusion),
        "local_diffusion_model": local_diffusion_model,
        "enable_emotion_annotation": bool(form.emotion_annotation),
        "enable_sentiment": bool(form.enable_sentiment),
        "enable_toxicity": bool(form.enable_toxicity),
        "perspective_api_key": form.perspective_api_key,
        "enable_memory_annotations": bool(enable_memory_annotations),
        "discussion_topics": form.discussion_topics,
        "opinion_dynamics": {
            "enabled": bool(form.opinion_dynamics_enabled),
            "model_name": opinion_model_name,
            "evaluation_scope": llm_evaluation_scope,
            "likert_scale": PHOTO_SHARING_LIKERT_SCALE,
            "opinion_groups": photo_opinion_groups,
        },
        "agents": {
            "probability_of_secondary_follow": form.probability_of_secondary_follow,
            "probability_of_follow_back": form.probability_of_follow_back,
            "churn": {
                "enabled": form.churn_enabled,
                "churn_probability": form.percentage_removed_agents_iteration,
                "inactivity_threshold": 5,
                "churn_percentage": form.percentage_removed_agents_iteration,
            },
            "new_agents": {
                "enabled": form.new_agents_enabled,
                "probability_new_agents": form.percentage_new_agents_iteration,
                "percentage_new_agents": form.percentage_new_agents_iteration,
            },
        },
        "actions_likelihood": photo_actions_likelihood,
        "activity_profiles": _photo_sharing_activity_profiles(form.profiles),
        "hourly_activity": form.hourly_activity,
        "agent_archetypes": {
            "enabled": form.enable_archetypes,
            "agent_downcast": form.agent_downcast,
            "distribution": {
                "validator": form.archetype_validator,
                "broadcaster": form.archetype_broadcaster,
                "explorer": form.archetype_explorer,
            },
        },
    }
    agents_config = {
        "reading_from_follower_ratio": form.reading_from_follower_ratio,
        "max_length_thread_reading": form.max_length_thread_reading,
        "attention_window": form.attention_window,
        "probability_of_daily_follow": form.probability_of_daily_follow,
        "probability_of_secondary_follow": form.probability_of_secondary_follow,
        "probability_of_follow_back": form.probability_of_follow_back,
        "follow_action_decay": {
            "enabled": form.follow_decay_enabled,
            "decay_function": form.follow_decay_function,
            "half_life_rounds": form.follow_decay_half_life,
            "decay_rate": form.follow_decay_rate,
            "min_probability_ratio": form.follow_decay_min_ratio,
        },
        "batch_size": form.batch_size,
        "visibility_rounds": form.visibility_rounds,
        "memory_enabled": bool(form.memory_enabled),
        "memory_pair_limit": form.memory_pair_limit,
        "memory_prompt_max_chars": form.memory_prompt_max_chars,
        "memory_social_decay_lambda": form.memory_social_decay_lambda,
        "memory_social_corruption_rate": form.memory_social_corruption_rate,
        "memory_social_resummarize_every_events": form.memory_social_resummarize_every_events,
        "memory_thread_decay_lambda": form.memory_thread_decay_lambda,
        "memory_thread_corruption_rate": form.memory_thread_corruption_rate,
        "memory_thread_resummarize_every_events": form.memory_thread_resummarize_every_events,
        "memory_evidence_tail_max": form.memory_evidence_tail_max,
        "memory_digest_update_cadence_rounds": form.memory_digest_update_cadence_rounds,
        "memory_digest_events_limit": form.memory_digest_events_limit,
        "memory_cold_start_window": form.memory_cold_start_window,
        "memory_semantic_enabled": bool(form.memory_semantic_enabled),
        "memory_search_k": form.memory_search_k,
        "memory_search_max_chars": form.memory_search_max_chars,
        "memory_search_time_window_rounds": form.memory_search_time_window_rounds,
        "memory_tier_a_max_chars": form.memory_tier_a_max_chars,
        "memory_tier_b_max_chars": form.memory_tier_b_max_chars,
        "memory_tier_c_max_chars": form.memory_tier_c_max_chars,
        "memory_total_max_chars": form.memory_total_max_chars,
        "memory_tier_c_uncertainty_threshold": form.memory_tier_c_uncertainty_threshold,
        "memory_reflection_cadence_rounds": form.memory_reflection_cadence_rounds,
        "memory_reflection_min_events": form.memory_reflection_min_events,
        "memory_reflection_trigger_importance_sum": form.memory_reflection_trigger_importance_sum,
        "memory_reflection_max_items_per_run": form.memory_reflection_max_items_per_run,
        "memory_embedding_model": form.memory_embedding_model,
        "memory_embedding_async": bool(form.memory_embedding_async),
        "memory_importance_mode": form.memory_importance_mode,
        "memory_backend": (
            "hybrid_semantic" if bool(form.memory_semantic_enabled) else "simple_recent"
        ),
    }
    simulation_config["agents"].update(agents_config)
    logging_config = photo_logging_config
    return simulation_config, agents_config, logging_config
