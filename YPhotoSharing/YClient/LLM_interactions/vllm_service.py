"""
vLLM-backed batched LLM service for YPhotoSharing.

Uses an embedded vLLM engine (requires a CUDA-capable GPU) for high-throughput
batched inference.  Mirrors the method surface of LLMService so that the rest of
the codebase can switch between standard and batched modes transparently.
Only client-side components may import this module.
"""

import logging
import os
from typing import Any, Dict, List, Optional

import ray

from YPhotoSharing.YClient.LLM_interactions.usage_tracker import LLMUsageTracker

logger = logging.getLogger(__name__)

_GOEMOTIONS = {
    "admiration",
    "amusement",
    "anger",
    "annoyance",
    "approval",
    "caring",
    "confusion",
    "curiosity",
    "desire",
    "disappointment",
    "disapproval",
    "disgust",
    "embarrassment",
    "excitement",
    "fear",
    "gratitude",
    "grief",
    "joy",
    "love",
    "nervousness",
    "optimism",
    "pride",
    "realization",
    "relief",
    "remorse",
    "sadness",
    "surprise",
    "trust",
}

_VLLM_AVAILABLE = False
try:
    from vllm import LLM, SamplingParams  # noqa: F401
    _VLLM_AVAILABLE = True
except ImportError:
    pass


def _require_vllm():
    if not _VLLM_AVAILABLE:
        raise RuntimeError(
            "vLLM is not installed.  Install it with: pip install vllm\n"
            "Note: vLLM requires CUDA and a supported GPU."
        )


def _estimate_tokens_from_text(*parts: Any) -> int:
    text = " ".join(str(part) for part in parts if part is not None).strip()
    if not text:
        return 0
    return max(1, len(text) // 4)


@ray.remote(num_gpus=1)
class VLLMService:
    """
    High-throughput batched LLM inference actor backed by vLLM.

    One GPU is requested per actor via num_gpus=1.  For multi-GPU tensor
    parallelism increase tensor_parallel_size in llm_config.

    The method surface deliberately matches LLMService so that clients can
    swap backends without code changes.
    """

    def __init__(
        self,
        llm_config: Optional[Dict[str, Any]] = None,
        prompts_config: Optional[Dict[str, Any]] = None,
        llm_v_config: Optional[Dict[str, Any]] = None,
        logging_config: Optional[Dict[str, Any]] = None,
    ):
        _require_vllm()
        from vllm import LLM, SamplingParams

        llm_config = llm_config or {
            "model": "meta-llama/Llama-3.2-1B-Instruct",
            "temperature": 0.7,
            "max_tokens": 256,
            "tensor_parallel_size": 1,
        }
        self.prompts_config = prompts_config or {}
        self.model_name = llm_config.get("model", "meta-llama/Llama-3.2-1B-Instruct")
        log_dir = os.path.expanduser(
            str((logging_config or {}).get("log_dir", "."))
        )
        instance_name = str((logging_config or {}).get("instance_name", "client"))
        self.usage_tracker = None
        if (logging_config or {}).get("enable_llm_usage_log", True):
            self.usage_tracker = LLMUsageTracker(
                logger=logging.getLogger(f"YPhotoSharing.LLMUsage.{instance_name}"),
                log_file_path=os.path.join(log_dir, f"{instance_name}_llm_usage.log"),
                enable_file_logging=True,
            )

        self.sampling_params = SamplingParams(
            temperature=llm_config.get("temperature", 0.7),
            max_tokens=llm_config.get("max_tokens", 256),
        )

        tensor_parallel_size = llm_config.get("tensor_parallel_size", 1)
        gpu_memory_utilization = llm_config.get("gpu_memory_utilization", 0.90)

        self.llm = LLM(
            model=self.model_name,
            tensor_parallel_size=tensor_parallel_size,
            gpu_memory_utilization=gpu_memory_utilization,
            trust_remote_code=llm_config.get("trust_remote_code", False),
        )

        # Optional vision model (separate vLLM instance)
        self.llm_v = None
        self.sampling_params_v = None
        if llm_v_config:
            self.sampling_params_v = SamplingParams(
                temperature=llm_v_config.get("temperature", 0.5),
                max_tokens=llm_v_config.get("max_tokens", 300),
            )
            self.llm_v = LLM(
                model=llm_v_config.get("model", "llava-hf/llava-1.5-7b-hf"),
                tensor_parallel_size=llm_v_config.get("tensor_parallel_size", 1),
                gpu_memory_utilization=llm_v_config.get("gpu_memory_utilization", 0.85),
                trust_remote_code=llm_v_config.get("trust_remote_code", False),
            )

        if self.usage_tracker:
            gpu_visible = os.environ.get("CUDA_VISIBLE_DEVICES")
            self.usage_tracker.log_gpu_selection(
                {
                    "physical_gpu_id": gpu_visible,
                    "logical_gpu_id": 0 if gpu_visible else None,
                    "assignment_method": "ray_assigned",
                    "cuda_visible_devices": gpu_visible,
                },
                model_name=self.model_name,
                backend="vllm",
            )

        self._setup_logger(logging_config)
        logger.info(f"VLLMService initialised with model={self.model_name}")

    def _setup_logger(self, logging_config: Optional[Dict[str, Any]] = None):
        """
        Configure the module-level logger to write to {client_id}_actor.log file.
        """
        global logger

        if logging_config is None:
            logging_config = {}

        enable_actor_log = logging_config.get("enable_actor_log", True)
        if not enable_actor_log:
            return

        from pathlib import Path
        log_dir = Path(logging_config.get("log_dir", "."))
        client_id = logging_config.get("instance_name", "client")

        # Create log directory
        log_dir.mkdir(parents=True, exist_ok=True)

        # Configure logger
        logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicates
        logger.handlers = []

        # Create file handler with rotation
        from logging.handlers import RotatingFileHandler
        from YPhotoSharing.common_utils import _compress_rotated_log, _JsonFormatter

        log_file = log_dir / f"{client_id}_actor.log"
        handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)  # 10MB

        # Add compression for rotated files
        handler.rotator = _compress_rotated_log
        handler.namer = lambda name: name + ".gz"

        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)

        logger.info(f"VLLMService logger configured to write to {log_file}")

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    def _batch_generate(self, prompts: List[str], *, method_name: str = "generate") -> List[str]:
        if not prompts:
            return []
        outputs = self.llm.generate(prompts, self.sampling_params)
        texts = [out.outputs[0].text.strip() for out in outputs]
        if self.usage_tracker:
            for prompt_text, result_text in zip(prompts, texts):
                self.usage_tracker.record_call(
                    method_name,
                    input_tokens=_estimate_tokens_from_text(prompt_text),
                    output_tokens=_estimate_tokens_from_text(result_text),
                )
        return texts

    # ------------------------------------------------------------------
    # Public API (mirrors LLMService)
    # ------------------------------------------------------------------

    def generate_caption(self, topic: str, day: int, slot: int,
                         cluster_id: int = 0, agent_attrs: Optional[dict] = None) -> str:
        prompt = (
            f"Write an Instagram caption for a photo about: {topic}. "
            f"Day {day}, slot {slot}. Max 30 words. Add 2-3 hashtags."
        )
        results = self._batch_generate([prompt], method_name="generate_caption")
        return results[0] if results else ""

    def batch_generate_captions(self, requests: List[dict]) -> List[str]:
        prompts = [
            (
                f"Write an Instagram caption for a photo about: {r.get('topic', 'general')}. "
                f"Day {r.get('day', 0)}, slot {r.get('slot', 0)}. Max 30 words. Add 2-3 hashtags."
            )
            for r in requests
        ]
        return self._batch_generate(prompts, method_name="generate_caption")

    def decide_reaction(self, caption: str, cluster_id: int = 0) -> str:
        prompt = (
            f"Read this Instagram caption and reply ONLY with one word: "
            f"LIKE, LOVE, LAUGH, WOW, SAD, ANGRY, or IGNORE.\n\nCaption: {caption}"
        )
        results = self._batch_generate([prompt], method_name="decide_reaction")
        result = results[0].upper() if results else "LIKE"
        allowed = {"LIKE", "LOVE", "LAUGH", "WOW", "SAD", "ANGRY", "IGNORE"}
        return result if result in allowed else "LIKE"

    def batch_decide_reactions(self, requests: List[dict]) -> List[str]:
        prompts = [
            (
                f"Read this Instagram caption and reply ONLY with one word: "
                f"LIKE, LOVE, LAUGH, WOW, SAD, ANGRY, or IGNORE.\n\nCaption: {r.get('caption', '')}"
            )
            for r in requests
        ]
        results = self._batch_generate(prompts, method_name="decide_reaction")
        allowed = {"LIKE", "LOVE", "LAUGH", "WOW", "SAD", "ANGRY", "IGNORE"}
        return [r.upper() if r.upper() in allowed else "LIKE" for r in results]

    def generate_comment(self, caption: str, author: str,
                         cluster_id: int = 0, agent_attrs: Optional[dict] = None) -> str:
        prompt = (
            f'{author} posted: "{caption}"\n\n'
            f"Write a brief Instagram comment (under 100 characters). "
            f"You may @mention the author."
        )
        results = self._batch_generate([prompt], method_name="generate_comment")
        return results[0] if results else ""

    def batch_generate_comments(self, requests: List[dict]) -> List[str]:
        prompts = [
            (
                f'{r.get("author", "user")} posted: "{r.get("caption", "")}"\n\n'
                f"Write a brief Instagram comment (under 100 characters)."
            )
            for r in requests
        ]
        return self._batch_generate(prompts, method_name="generate_comment")

    def decide_follow(self, username: str, bio: str, topics: str,
                      cluster_id: int = 0) -> str:
        prompt = (
            f"Should you follow @{username}?\n"
            f"Bio: {bio}\nRecent topics: {topics}\n"
            f"Reply ONLY with: FOLLOW or SKIP."
        )
        results = self._batch_generate([prompt], method_name="decide_follow")
        result = results[0].upper() if results else "SKIP"
        return "FOLLOW" if "FOLLOW" in result else "SKIP"

    def describe_photo(self, url: str) -> str:
        if not self.llm_v:
            return ""
        outputs = self.llm_v.generate(
            [f"Describe this photo: <img {url}>"], self.sampling_params_v
        )
        result = outputs[0].outputs[0].text.strip() if outputs else ""
        if self.usage_tracker:
            self.usage_tracker.record_call(
                "describe_photo",
                input_tokens=_estimate_tokens_from_text(url),
                output_tokens=_estimate_tokens_from_text(result),
            )
        return result

    def extract_emotions(self, text: str) -> List[str]:
        prompt = (
            "Identify emotions from this text using ONLY GoEmotions labels: "
            "admiration, amusement, anger, annoyance, approval, caring, confusion, "
            "curiosity, desire, disappointment, disapproval, disgust, embarrassment, "
            "excitement, fear, gratitude, grief, joy, love, nervousness, optimism, "
            "pride, realization, relief, remorse, sadness, surprise, trust.\n\n"
            f'Text: "{text}"\n\nReturn emotions as a comma-separated list.'
        )
        results = self._batch_generate([prompt], method_name="extract_emotions")
        raw = results[0] if results else ""
        parsed = [token.strip().lower() for token in raw.split(",") if token.strip()]
        return [emotion for emotion in parsed if emotion in _GOEMOTIONS]

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "vllm",
            "model": self.model_name,
            "supports_native_batching": True,
            "supports_vision": self.llm_v is not None,
        }

    def shutdown(self) -> dict:
        self.llm = None
        self.llm_v = None
        return {"status": "shutdown"}
