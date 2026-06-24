"""
Remote batch LLM service for YPhotoSharing.

Delegates inference to a remote Ollama or OpenAI-compatible endpoint while
exposing the same batched method surface as VLLMService.  No local GPU required.
Only client-side components may import this module.
"""

import logging
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import ray
import requests
from langchain_ollama import ChatOllama

from YPhotoSharing.YClient.LLM_interactions.usage_tracker import LLMUsageTracker

logger = logging.getLogger(__name__)


# -------------------------------------------------- URL helpers ------

def _coerce_http_base_url(config: Dict[str, Any]) -> str:
    address = config.get("address", "localhost")
    port = config.get("port", 11434)
    if address.startswith("http://") or address.startswith("https://"):
        return address.rstrip("/")
    if ":" in address:
        return f"http://{address}".rstrip("/")
    return f"http://{address}:{port}".rstrip("/")


def _ollama_base_url(config: Dict[str, Any]) -> str:
    base = _coerce_http_base_url(config)
    parsed = urlparse(base)
    path = parsed.path.rstrip("/").removesuffix("/v1")
    return parsed._replace(path=path).geturl().rstrip("/")


def _openai_base_url(config: Dict[str, Any]) -> str:
    base = _coerce_http_base_url(config)
    parsed = urlparse(base)
    path = parsed.path.rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    return parsed._replace(path=path).geturl().rstrip("/")


# -------------------------------------------------- Adapters ---------

class _OllamaAdapter:
    provider = "ollama"

    def __init__(self, config: Dict[str, Any]):
        kwargs = {
            "model": config["model"],
            "temperature": config.get("temperature", 0.7),
            "base_url": _ollama_base_url(config),
        }
        if "timeout" in config:
            kwargs["timeout"] = config["timeout"]
        self._chat = ChatOllama(**kwargs)

    def generate(self, prompts: List[str], temperature: float = 0.7,
                 max_tokens: int = 256) -> List[str]:
        if not prompts:
            return []
        if len(prompts) == 1:
            results = [self._chat.invoke(prompts[0])]
        else:
            results = self._chat.batch(prompts)
        return [_extract_text(r) for r in results]


class _OpenAIAdapter:
    provider = "openai"

    def __init__(self, config: Dict[str, Any]):
        self.model = config["model"]
        self.base_url = _openai_base_url(config)
        self.api_key = config.get("llm_api_key")
        self.timeout = config.get("timeout", 30)

    def generate(self, prompts: List[str], temperature: float = 0.7,
                 max_tokens: int = 256) -> List[str]:
        if not prompts:
            return []
        headers = {"Content-Type": "application/json"}
        if self.api_key and str(self.api_key).upper() != "NULL":
            headers["Authorization"] = f"******"
        payload = {
            "model": self.model,
            "prompt": prompts if len(prompts) > 1 else prompts[0],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = requests.post(
            f"{self.base_url}/completions",
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        choices = resp.json().get("choices", [])
        texts = [""] * len(prompts)
        if len(prompts) == 1 and choices:
            texts[0] = (choices[0].get("text") or "").strip()
        else:
            for ch in choices:
                idx = ch.get("index", 0)
                if 0 <= idx < len(texts):
                    texts[idx] = (ch.get("text") or "").strip()
        return texts


def _extract_text(response: Any) -> str:
    if response is None:
        return ""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", ""))
        return "".join(parts).strip()
    return str(content).strip()


def _estimate_tokens_from_text(*parts: Any) -> int:
    text = " ".join(str(part) for part in parts if part is not None).strip()
    if not text:
        return 0
    return max(1, len(text) // 4)


# -------------------------------------------------- Auto-detect ------

def _probe_openai_batch(config: Dict[str, Any]) -> bool:
    try:
        base = _openai_base_url(config)
        headers = {"Content-Type": "application/json"}
        key = config.get("llm_api_key")
        if key and str(key).upper() != "NULL":
            headers["Authorization"] = f"******"
        resp = requests.post(
            f"{base}/completions",
            headers=headers,
            json={"model": config["model"], "prompt": ["OK.", "OK."],
                  "temperature": 0.0, "max_tokens": 4},
            timeout=config.get("timeout", 10),
        )
        if resp.status_code >= 400:
            return False
        choices = resp.json().get("choices", [])
        return len(choices) == 2
    except Exception:
        return False


def _probe_ollama_batch(config: Dict[str, Any]) -> bool:
    try:
        chat = ChatOllama(
            model=config["model"],
            temperature=0.0,
            base_url=_ollama_base_url(config),
        )
        result = chat.batch(["OK.", "OK."])
        return isinstance(result, list) and len(result) == 2
    except Exception:
        return False


def resolve_provider(config: Dict[str, Any]) -> Optional[str]:
    """Detect which provider supports batching for this endpoint."""
    api_format = str(config.get("api_format", "auto")).lower()
    backend = str(config.get("backend", "")).lower()

    if api_format not in {"auto", "ollama", "openai"}:
        api_format = "auto"

    if api_format != "auto":
        order = [api_format]
    elif backend == "ollama":
        order = ["ollama", "openai"]
    else:
        order = ["openai", "ollama"]

    for p in order:
        if p == "openai" and _probe_openai_batch(config):
            return "openai"
        if p == "ollama" and _probe_ollama_batch(config):
            return "ollama"
    return None


# -------------------------------------------------- Ray actor --------

@ray.remote
class RemoteBatchLLMService:
    """
    Remote-batch capable LLM service.

    Delegates generation to an Ollama or OpenAI-compatible endpoint.
    No local GPU required.  Exposes the same API surface as VLLMService.
    """

    def __init__(
        self,
        llm_config: Optional[Dict[str, Any]] = None,
        prompts_config: Optional[Dict[str, Any]] = None,
        llm_v_config: Optional[Dict[str, Any]] = None,
        logging_config: Optional[Dict[str, Any]] = None,
    ):
        llm_config = llm_config or {
            "address": "localhost",
            "port": 11434,
            "model": "llama3.2",
            "temperature": 0.7,
            "max_tokens": 256,
        }
        self.prompts_config = prompts_config or {}
        self.model_name = llm_config.get("model", "llama3.2")
        self.temperature = llm_config.get("temperature", 0.7)
        self.max_tokens = llm_config.get("max_tokens", 256)
        log_dir = os.path.expanduser(str((logging_config or {}).get("log_dir", ".")))
        instance_name = str((logging_config or {}).get("instance_name", "client"))
        self.usage_tracker = None
        if (logging_config or {}).get("enable_llm_usage_log", True):
            self.usage_tracker = LLMUsageTracker(
                logger=logging.getLogger(f"YPhotoSharing.LLMUsage.{instance_name}"),
                log_file_path=os.path.join(log_dir, f"{instance_name}_llm_usage.log"),
                enable_file_logging=True,
            )

        provider = llm_config.get("_resolved_remote_api") or resolve_provider(llm_config)
        if not provider:
            raise RuntimeError(
                "RemoteBatchLLMService: could not detect a batch-capable endpoint. "
                "Check that Ollama or a vLLM OpenAI-compatible server is running."
            )
        self.provider = provider
        if provider == "openai":
            self._adapter = _OpenAIAdapter(llm_config)
        else:
            self._adapter = _OllamaAdapter(llm_config)

        self.llm_v = None
        if llm_v_config:
            v_provider = llm_v_config.get("_resolved_remote_api") or resolve_provider(llm_v_config)
            if v_provider == "openai":
                self.llm_v = _OpenAIAdapter(llm_v_config)
            else:
                self.llm_v = _OllamaAdapter(llm_v_config)

        if self.usage_tracker:
            gpu_visible = os.environ.get("CUDA_VISIBLE_DEVICES")
            self.usage_tracker.log_gpu_selection(
                {
                    "physical_gpu_id": gpu_visible,
                    "logical_gpu_id": 0 if gpu_visible else None,
                    "assignment_method": "remote_batch",
                    "cuda_visible_devices": gpu_visible,
                },
                model_name=self.model_name,
                backend=f"remote_batch_{self.provider}",
            )

        logger.info(f"RemoteBatchLLMService ready (provider={provider}, model={self.model_name})")

    # ------------------------------------------------------------------

    def _gen(self, prompts: List[str], *, method_name: str) -> List[str]:
        results = self._adapter.generate(prompts, self.temperature, self.max_tokens)
        if self.usage_tracker:
            for prompt_text, result_text in zip(prompts, results):
                self.usage_tracker.record_call(
                    method_name,
                    input_tokens=_estimate_tokens_from_text(prompt_text),
                    output_tokens=_estimate_tokens_from_text(result_text),
                )
        return results

    def generate_caption(self, topic: str, day: int, slot: int,
                         cluster_id: int = 0, agent_attrs: Optional[dict] = None) -> str:
        prompt = (
            f"Write an Instagram caption for a photo about: {topic}. "
            f"Day {day}, slot {slot}. Max 30 words. Add 2-3 hashtags."
        )
        results = self._gen([prompt], method_name="generate_caption")
        return results[0] if results else ""

    def batch_generate_captions(self, requests: List[dict]) -> List[str]:
        prompts = [
            (
                f"Write an Instagram caption for a photo about: {r.get('topic', 'general')}. "
                f"Day {r.get('day', 0)}, slot {r.get('slot', 0)}. Max 30 words. Add 2-3 hashtags."
            )
            for r in requests
        ]
        return self._gen(prompts, method_name="generate_caption")

    def decide_reaction(self, caption: str, cluster_id: int = 0) -> str:
        prompt = (
            f"Read this Instagram caption and reply ONLY with one word: "
            f"LIKE, LOVE, LAUGH, WOW, SAD, ANGRY, or IGNORE.\n\nCaption: {caption}"
        )
        results = self._gen([prompt], method_name="decide_reaction")
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
        results = self._gen(prompts, method_name="decide_reaction")
        allowed = {"LIKE", "LOVE", "LAUGH", "WOW", "SAD", "ANGRY", "IGNORE"}
        return [r.upper() if r.upper() in allowed else "LIKE" for r in results]

    def generate_comment(self, caption: str, author: str,
                         cluster_id: int = 0, agent_attrs: Optional[dict] = None) -> str:
        prompt = (
            f'{author} posted: "{caption}"\n\n'
            f"Write a brief Instagram comment (under 100 characters)."
        )
        results = self._gen([prompt], method_name="generate_comment")
        return results[0] if results else ""

    def batch_generate_comments(self, requests: List[dict]) -> List[str]:
        prompts = [
            (
                f'{r.get("author", "user")} posted: "{r.get("caption", "")}"\n\n'
                f"Write a brief Instagram comment (under 100 characters)."
            )
            for r in requests
        ]
        return self._gen(prompts, method_name="generate_comment")

    def decide_follow(self, username: str, bio: str, topics: str,
                      cluster_id: int = 0) -> str:
        prompt = (
            f"Should you follow @{username}?\n"
            f"Bio: {bio}\nRecent topics: {topics}\n"
            f"Reply ONLY with: FOLLOW or SKIP."
        )
        results = self._gen([prompt], method_name="decide_follow")
        result = results[0].upper() if results else "SKIP"
        return "FOLLOW" if "FOLLOW" in result else "SKIP"

    def describe_photo(self, url: str) -> str:
        if not self.llm_v:
            return ""
        results = self.llm_v.generate(
            [f"Describe this photo: <img {url}>"],
            self.temperature, self.max_tokens,
        )
        result = results[0] if results else ""
        if self.usage_tracker:
            self.usage_tracker.record_call(
                "describe_photo",
                input_tokens=_estimate_tokens_from_text(url),
                output_tokens=_estimate_tokens_from_text(result),
            )
        return result

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": f"remote_batch_{self.provider}",
            "model": self.model_name,
            "supports_native_batching": True,
            "supports_vision": self.llm_v is not None,
        }

    def shutdown(self) -> dict:
        self._adapter = None
        self.llm_v = None
        return {"status": "shutdown"}
