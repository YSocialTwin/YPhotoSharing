"""
LLM usage and cost tracking for YPhotoSharing.

This mirrors the YSimulator cost-tracker pattern by writing one JSON object per
line to a dedicated ``*_llm_usage.log`` file and flushing every record
immediately.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from YPhotoSharing.common_utils import build_json_line_file_logger


class LLMUsageTracker:
    """
    Track LLM calls, token estimates, and optional costs.
    """

    def __init__(
        self,
        token_costs: Optional[Dict[str, float]] = None,
        logger: Optional[logging.Logger] = None,
        log_file_path: Optional[Path] = None,
        enable_file_logging: bool = True,
    ):
        self.call_counts = defaultdict(int)
        self.token_counts = defaultdict(int)
        self.token_costs = token_costs or {}
        self.logger = logger or logging.getLogger(__name__)
        self.usage_logger = None
        if enable_file_logging and log_file_path:
            self.usage_logger = build_json_line_file_logger(
                f"YPhotoSharing.LLMUsage.{id(self)}",
                log_file_path,
                propagate=False,
            )

    def record_call(self, method: str, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.call_counts[method] += 1
        total_tokens = input_tokens + output_tokens
        self.token_counts[method] += total_tokens

        self.logger.debug(
            "LLM call recorded: %s (in=%s, out=%s, total=%s)",
            method,
            input_tokens,
            output_tokens,
            total_tokens,
        )

        if self.usage_logger:
            log_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "method": method,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cumulative_calls": self.call_counts[method],
                "cumulative_tokens": self.token_counts[method],
            }
            if method in self.token_costs:
                cost_per_1k = self.token_costs[method]
                log_entry["cost"] = (total_tokens / 1000.0) * cost_per_1k
                log_entry["cumulative_cost"] = self.get_estimated_cost(method)

            self.usage_logger.info(json.dumps(log_entry))
            for handler in self.usage_logger.handlers:
                handler.flush()

    def log_gpu_selection(
        self,
        gpu_info: dict,
        model_name: Optional[str] = None,
        backend: str = "vllm",
    ) -> None:
        if not self.usage_logger:
            return

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event": "gpu_selection",
            "backend": backend,
            "physical_gpu_id": gpu_info.get("physical_gpu_id"),
            "logical_gpu_id": gpu_info.get("logical_gpu_id"),
            "assignment_method": gpu_info.get("assignment_method", "unknown"),
            "cuda_visible_devices": gpu_info.get("cuda_visible_devices"),
        }
        if model_name:
            log_entry["model"] = model_name

        self.usage_logger.info(json.dumps(log_entry))
        for handler in self.usage_logger.handlers:
            handler.flush()
        self.logger.info(
            "GPU selection logged: method=%s, physical_gpu=%s",
            gpu_info.get("assignment_method"),
            gpu_info.get("physical_gpu_id"),
        )

    def get_call_count(self, method: Optional[str] = None) -> int:
        if method:
            return self.call_counts[method]
        return sum(self.call_counts.values())

    def get_token_count(self, method: Optional[str] = None) -> int:
        if method:
            return self.token_counts[method]
        return sum(self.token_counts.values())

    def get_estimated_cost(self, method: Optional[str] = None) -> float:
        if not self.token_costs:
            return 0.0

        if method:
            tokens = self.token_counts[method]
            cost_per_1k = self.token_costs.get(method, 0.0)
            return (tokens / 1000.0) * cost_per_1k

        total_cost = 0.0
        for method_name, tokens in self.token_counts.items():
            cost_per_1k = self.token_costs.get(method_name, 0.0)
            total_cost += (tokens / 1000.0) * cost_per_1k
        return total_cost

    def get_summary(self) -> Dict[str, dict]:
        summary = {
            "total_calls": self.get_call_count(),
            "total_tokens": self.get_token_count(),
            "estimated_cost": self.get_estimated_cost(),
            "by_method": {},
        }
        for method in set(self.call_counts.keys()) | set(self.token_counts.keys()):
            summary["by_method"][method] = {
                "calls": self.call_counts[method],
                "tokens": self.token_counts[method],
                "cost": self.get_estimated_cost(method),
            }
        return summary
