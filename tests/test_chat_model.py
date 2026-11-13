"""The standard LLM services speak the right protocol and send the API key (hosted providers need both)."""

import pytest

from YPhotoSharing.YClient.LLM_interactions import chat_model as cm


def cfg(**kw):
    base = {"address": "localhost", "port": 11434, "model": "m"}
    base.update(kw)
    return base


def test_the_placeholders_are_not_keys():
    for value in (None, "", "NULL", "null", "None", "EMPTY"):
        assert cm.real_api_key(cfg(llm_api_key=value)) is None
    assert cm.real_api_key(cfg(llm_api_key=" sk-abc ")) == "sk-abc"


def test_the_scheme_and_the_path_of_the_address_are_kept():
    assert cm.base_url(cfg(address="https://api.deepseek.com/v1/")) == "https://api.deepseek.com/v1"
    assert cm.base_url(cfg(address="http://10.0.0.5:8000/v1")) == "http://10.0.0.5:8000/v1"
    assert cm.base_url(cfg(address="10.0.0.5:8000")) == "http://10.0.0.5:8000"
    assert cm.base_url(cfg(address="gpu-box")) == "http://gpu-box:11434"


def test_a_local_ollama_stays_on_the_native_protocol():
    assert not cm.uses_openai_protocol(cfg())
    assert not cm.uses_openai_protocol(cfg(address="http://127.0.0.1:11434/v1"))
    assert cm.ollama_url(cfg(address="http://127.0.0.1:11434/v1")) == "http://127.0.0.1:11434"


def test_a_hosted_provider_with_a_key_or_https_uses_the_openai_protocol():
    assert cm.uses_openai_protocol(cfg(address="https://api.deepseek.com/v1", llm_api_key="sk"))
    assert cm.uses_openai_protocol(cfg(address="http://api.example.com/v1", llm_api_key="sk"))
    assert cm.uses_openai_protocol(cfg(address="https://llm.example.org/v1"))


def test_an_authenticated_ollama_keeps_the_native_protocol_and_sends_the_key():
    c = cfg(address="https://ollama.com", llm_api_key="sk")
    assert not cm.uses_openai_protocol(c)
    assert cm.ollama_client_kwargs(c) == {"headers": {"Authorization": "Bearer sk"}}
    assert cm.ollama_client_kwargs(cfg()) == {}


def test_api_format_forces_the_protocol():
    assert cm.uses_openai_protocol(cfg(api_format="openai"))
    assert not cm.uses_openai_protocol(cfg(address="https://x.example/v1", llm_api_key="k", api_format="ollama"))


def test_the_chat_model_gets_the_key_and_the_url():
    pytest.importorskip("langchain_openai")
    model = cm.build_chat_model(
        cfg(address="https://api.deepseek.com/v1", model="deepseek-chat", llm_api_key="sk-secret", llm_max_tokens=-1)
    )
    assert model.model_name == "deepseek-chat"
    assert str(model.openai_api_base) == "https://api.deepseek.com/v1"
    assert model.openai_api_key.get_secret_value() == "sk-secret"
    assert model.max_tokens is None
