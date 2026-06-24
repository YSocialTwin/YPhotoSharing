from __future__ import annotations

from dataclasses import dataclass
from math import exp, log1p
from typing import Any, Dict, Optional

import ray


def deep_update(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_update(result[key], value)
        else:
            result[key] = value
    return result


def build_stress_reward_settings_from_config(config: Optional[dict]) -> dict:
    config = config or {}
    simulation_cfg = config.get("simulation", {}) if isinstance(config.get("simulation"), dict) else {}
    top_level_cfg = config.get("stress_reward") if isinstance(config.get("stress_reward"), dict) else None
    simulation_sr_cfg = simulation_cfg.get("stress_reward") if isinstance(simulation_cfg.get("stress_reward"), dict) else None

    settings = {"enabled": False, "backward_rounds": 24, "system": {}}
    for source in (top_level_cfg, simulation_sr_cfg):
        if not source:
            continue
        settings = deep_update(settings, source)

    if "stress_reward_enabled" in config:
        settings["enabled"] = bool(config.get("stress_reward_enabled"))
    if "stress_reward_enabled" in simulation_cfg:
        settings["enabled"] = bool(simulation_cfg.get("stress_reward_enabled"))
    if "stress_reward_annotation" in config:
        settings["enabled"] = bool(config.get("stress_reward_annotation"))
    if "stress_reward_annotation" in simulation_cfg:
        settings["enabled"] = bool(simulation_cfg.get("stress_reward_annotation"))

    settings["backward_rounds"] = int(settings.get("backward_rounds", 24) or 24)
    if not isinstance(settings.get("system"), dict):
        settings["system"] = {}
    return settings


@dataclass
class AffectiveTraits:
    sensitivity: float = 1.0
    reward_sensitivity: float = 1.0
    resilience: float = 1.0
    visibility_need: float = 1.0


class StressRewardSystem:
    DEFAULT_CONFIG: Dict[str, Any] = {
        "traits": {
            "sensitivity": 1.0,
            "reward_sensitivity": 1.0,
            "resilience": 1.0,
            "visibility_need": 1.0,
        },
        "coupling": {
            "reward_buffers_stress_alpha": 0.30,
            "stress_reduces_reward_beta": 0.20,
        },
        "churn": {
            "enabled": False,
            "stress_weight": 1.5,
            "reward_weight": 1.0,
            "bias": -2.2,
            "temperature": 0.35,
            "min_probability": 0.0,
            "max_probability": 0.95,
        },
        "events": {
            "reaction": {
                "like": {"stress": -0.005, "reward": 0.03},
                "dislike": {"stress": 0.03, "reward": -0.02},
            },
            "comment": {
                "positive": {"stress": -0.02, "reward": 0.07},
                "neutral": {"stress": 0.0, "reward": 0.01},
                "critical": {"stress": 0.03, "reward": -0.01},
                "hostile": {"stress": 0.10, "reward": -0.05},
                "supportive": {"stress": -0.05, "reward": 0.08},
            },
            "report": {
                "mass_report": {"stress": 0.06, "reward": -0.03},
            },
            "share": {
                "positive": {"stress": -0.01, "reward": 0.08},
                "hostile": {"stress": 0.12, "reward": -0.06},
            },
        },
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = deep_update(self.DEFAULT_CONFIG, config or {})

    @staticmethod
    def _clamp01(value: Any) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except Exception:
            return 0.0

    def churn_enabled(self) -> bool:
        return bool((self.config.get("churn") or {}).get("enabled", False))

    def compute_reaction_delta(
        self,
        *,
        reaction: str,
        current_stress: Optional[float] = None,
        current_reward: Optional[float] = None,
    ) -> Dict[str, float]:
        return self._compute_delta(
            family="reaction",
            subtype=reaction,
            current_stress=current_stress,
            current_reward=current_reward,
            volume=1,
        )

    def compute_comment_delta(
        self,
        *,
        tone: str,
        current_stress: Optional[float] = None,
        current_reward: Optional[float] = None,
        directness: float = 1.0,
        support_strength: float = 1.0,
    ) -> Dict[str, float]:
        return self._compute_delta(
            family="comment",
            subtype=tone,
            current_stress=current_stress,
            current_reward=current_reward,
            directness=directness,
            support_strength=support_strength,
        )

    def compute_share_delta(
        self,
        *,
        tone: str,
        current_stress: Optional[float] = None,
        current_reward: Optional[float] = None,
        public_exposure: float = 1.0,
    ) -> Dict[str, float]:
        return self._compute_delta(
            family="share",
            subtype=tone,
            current_stress=current_stress,
            current_reward=current_reward,
            public_exposure=public_exposure,
        )

    def compute_report_delta(
        self,
        *,
        outcome: str,
        current_stress: Optional[float] = None,
        current_reward: Optional[float] = None,
        public_exposure: float = 1.0,
        importance: float = 1.0,
        volume: int = 1,
    ) -> Dict[str, float]:
        return self._compute_delta(
            family="report",
            subtype=outcome,
            current_stress=current_stress,
            current_reward=current_reward,
            public_exposure=public_exposure,
            importance=importance,
            volume=volume,
        )

    def compute_current_stress_reward(
        self,
        *,
        server,
        agent_id: str,
        current_tid: str,
        backward_rounds: int = 24,
    ) -> Dict[str, float]:
        payload = ray.get(
            server.get_stress_reward.remote(
                str(agent_id),
                str(current_tid),
                int(backward_rounds),
            )
        )
        return {
            "stress": self._clamp01((payload or {}).get("stress", 0.0)),
            "reward": self._clamp01((payload or {}).get("reward", 0.0)),
        }

    def compute_churn_probability(self, *, current_stress: float, current_reward: float) -> float:
        churn_cfg = self.config.get("churn") or {}
        stress = self._clamp01(current_stress)
        reward = self._clamp01(current_reward)
        temperature = max(1e-6, float(churn_cfg.get("temperature", 0.35)))
        logits = (
            float(churn_cfg.get("stress_weight", 1.5)) * stress
            - float(churn_cfg.get("reward_weight", 1.0)) * reward
            + float(churn_cfg.get("bias", -2.2))
        )
        probability = 1.0 / (1.0 + exp(-(logits / temperature)))
        probability = max(float(churn_cfg.get("min_probability", 0.0)), probability)
        probability = min(float(churn_cfg.get("max_probability", 0.95)), probability)
        return self._clamp01(probability)

    def _compute_delta(
        self,
        *,
        family: str,
        subtype: str,
        current_stress: Optional[float] = None,
        current_reward: Optional[float] = None,
        directness: float = 1.0,
        public_exposure: float = 1.0,
        support_strength: float = 1.0,
        volume: int = 1,
        importance: float = 1.0,
    ) -> Dict[str, float]:
        base = self.config["events"][family][subtype]
        stress_ctx = 0.2 if current_stress is None else current_stress
        reward_ctx = 0.4 if current_reward is None else current_reward
        ds = float(base["stress"]) * float(importance)
        dr = float(base["reward"]) * float(importance)

        if family == "reaction":
            ds *= log1p(volume)
            dr *= log1p(volume)
        elif family == "comment" and subtype == "hostile":
            ds *= directness * public_exposure
            dr *= directness
        elif family == "comment" and subtype == "supportive":
            ds *= support_strength
            dr *= support_strength
        elif family in {"share", "report"}:
            ds *= public_exposure
            dr *= public_exposure

        alpha = float(self.config["coupling"]["reward_buffers_stress_alpha"])
        beta = float(self.config["coupling"]["stress_reduces_reward_beta"])
        if ds > 0:
            ds *= max(0.0, 1.0 - alpha * reward_ctx)
        if dr > 0:
            dr *= max(0.0, 1.0 - beta * stress_ctx)

        return {
            "delta_stress": float(ds),
            "delta_reward": float(dr),
            "projected_stress": self._clamp01(stress_ctx + ds),
            "projected_reward": self._clamp01(reward_ctx + dr),
        }

