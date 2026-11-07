"""Chat model factory for the standard (non batched) LLM services.

The services used to build a ``ChatOllama`` against ``http://<address>:<port>`` whatever the configuration said:
the scheme was thrown away, the API key was ignored and only the native Ollama protocol was spoken. That cannot
reach a hosted provider (OpenAI, DeepSeek, ...), which needs HTTPS, an ``Authorization: Bearer`` header and the
OpenAI-compatible ``/chat/completions`` protocol.

``build_chat_model(llm_config, ...)`` picks the protocol and returns a LangChain chat model:

* ``api_format`` ``"openai"`` / ``"ollama"`` force the protocol;
* ``"auto"`` (default) talks Ollama to local-looking endpoints (no key, plain ``http``, port 11434 or a host that
  names Ollama) and the OpenAI-compatible protocol to everything else that has a real API key or uses ``https``;
* the key (``llm_api_key``; ``NULL``, ``None`` and ``EMPTY`` mean "no key") is sent as a bearer token with both
  protocols, so an authenticated Ollama endpoint also works;
* the scheme and the path of the configured address are kept.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlparse

NO_KEY = {"", "NULL", "NONE", "EMPTY"}


def real_api_key(config: Optional[Dict[str, Any]]) -> Optional[str]:
    """The API key of an LLM configuration, or ``None`` when it has none (placeholders count as none)."""
    value = str((config or {}).get("llm_api_key") or "").strip()
    return None if value.upper() in NO_KEY else value


def base_url(config: Dict[str, Any]) -> str:
    """The endpoint of a configuration, keeping its scheme and path (``http`` is assumed when there is none)."""
    address = str(config.get("address") or "localhost").strip()
    port = config.get("port", 11434)
    if address.startswith(("http://", "https://")):
        return address.rstrip("/")
    if ":" in address or "/" in address:
        return f"http://{address}".rstrip("/")
    return f"http://{address}:{port}".rstrip("/")


def _looks_like_ollama(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return "ollama" in host or parsed.port == 11434


def uses_openai_protocol(config: Dict[str, Any]) -> bool:
    """True when the configuration has to be served with the OpenAI-compatible protocol."""
    api_format = str(config.get("api_format") or "auto").strip().lower()
    if api_format == "openai":
        return True
    if api_format == "ollama":
        return False
    url = base_url(config)
    if _looks_like_ollama(url):
        return False
    if real_api_key(config):
        return True
    return urlparse(url).scheme == "https"


def ollama_url(config: Dict[str, Any]) -> str:
    """Ollama's native API lives at the root of the server: drop a trailing ``/v1``."""
    url = base_url(config)
    return url[: -len("/v1")] if url.endswith("/v1") else url


def ollama_client_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
    """``client_kwargs`` of ``ChatOllama`` carrying the bearer token, empty when there is no key."""
    key = real_api_key(config)
    return {"headers": {"Authorization": f"Bearer {key}"}} if key else {}


def build_chat_model(
    config: Dict[str, Any], default_model: str = "llama3.2", default_temperature: float = 0.7
):
    """A LangChain chat model for *config* (see the module docstring)."""
    model = str(config.get("model") or default_model)
    temperature = config.get("temperature", default_temperature)
    if uses_openai_protocol(config):
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - depends on the installation
            raise RuntimeError(
                "An OpenAI-compatible LLM endpoint needs the `langchain-openai` package: "
                "pip install langchain-openai"
            ) from exc
        kwargs: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "base_url": base_url(config),
            "api_key": real_api_key(config) or "EMPTY",
        }
        max_tokens = config.get("llm_max_tokens", config.get("max_tokens"))
        if isinstance(max_tokens, (int, float)) and max_tokens > 0:
            kwargs["max_tokens"] = int(max_tokens)
        if config.get("timeout") is not None:
            kwargs["timeout"] = config["timeout"]
        return ChatOpenAI(**kwargs)

    from langchain_ollama import ChatOllama

    kwargs = {"model": model, "temperature": temperature, "base_url": ollama_url(config)}
    client_kwargs = ollama_client_kwargs(config)
    if client_kwargs:
        kwargs["client_kwargs"] = client_kwargs
    return ChatOllama(**kwargs)
