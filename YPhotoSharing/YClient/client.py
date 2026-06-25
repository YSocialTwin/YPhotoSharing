from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .annotation import build_annotation_config_from_json
from .text_processing import annotate_content


@dataclass
class SimulationClient:
    """Minimal client facade exposing YSimulator-style annotation switches."""

    config: Dict[str, Any] = field(default_factory=dict)
    perspective_api_key: Optional[str] = None

    def __post_init__(self) -> None:
        simulation = self.config.get("simulation") if isinstance(self.config.get("simulation"), dict) else {}
        self.annotation_config = build_annotation_config_from_json(self.config)
        self.perspective_api_key = self.annotation_config.get("perspective_api_key") or simulation.get(
            "perspective_api_key"
        )

    def annotate(self, text: str, llm_handle=None) -> Dict[str, Any]:
        return annotate_content(
            text,
            {
                "simulation": {
                    **self.annotation_config,
                    "perspective_api_key": self.perspective_api_key,
                }
            },
            llm_handle=llm_handle,
        )

