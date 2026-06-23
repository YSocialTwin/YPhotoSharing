"""
Standard (single-request) LLM service for YPhotoSharing clients.

Supports Ollama and any OpenAI-compatible endpoint.
Only client-side components may import this module.
"""

import logging
import os
from typing import Any, Dict, List, Optional

os.environ.setdefault("LANGCHAIN_VERBOSE", "false")

import ray
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

logger = logging.getLogger(__name__)


def _build_ollama_url(llm_config: dict) -> str:
    address = llm_config.get("address", "localhost")
    port = llm_config.get("port", 11434)
    # Strip protocol if accidentally included
    address = address.replace("http://", "").replace("https://", "")
    if ":" in address:
        return f"http://{address}"
    return f"http://{address}:{port}"


DEFAULT_PROMPTS = {
    "personas": {
        "0": "You are a casual Instagram user who shares travel and food photos.",
        "1": "You are a photography enthusiast focused on art and aesthetics.",
        "2": "You are a social influencer who posts lifestyle and fitness content.",
    },
    "generate_caption": {
        "system_template": "{persona}",
        "user_template": (
            "Write an Instagram caption for a photo about: {topic}.\n"
            "Day {day}, slot {slot}. Max 30 words. Add 2-3 relevant hashtags."
        ),
    },
    "decide_reaction": {
        "system_template": "You are an Instagram user. Read the photo caption and reply ONLY with: LIKE, LOVE, LAUGH, WOW, SAD, ANGRY, or IGNORE.",
        "user_template": "{caption}",
    },
    "generate_comment": {
        "system_template": "{persona} You engage with photos by leaving comments.",
        "user_template": (
            '{author} posted: "{caption}"\n\n'
            "Write a brief, authentic comment (under 100 characters). "
            "You may @mention the author."
        ),
    },
    "describe_photo": {
        "system_template": "You are an image description assistant. Describe images concisely.",
        "user_template": "Describe this photo: <img {url}>",
    },
    "decide_follow": {
        "system_template": "{persona} You are deciding whether to follow another user.",
        "user_template": (
            "User @{username} has the following bio: {bio}\n"
            "Their recent posts are about: {topics}\n"
            "Should you follow them? Reply ONLY with: FOLLOW or SKIP."
        ),
    },
}


@ray.remote
class LLMService:
    """
    Standard (non-batched) LLM inference actor for Instagram-like agents.

    Uses Ollama via LangChain by default; swap the underlying model for any
    LangChain-compatible provider (OpenAI, Anthropic, etc.).
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
        }
        self.prompts_config = prompts_config or DEFAULT_PROMPTS
        base_url = _build_ollama_url(llm_config)
        self.llm = ChatOllama(
            model=llm_config.get("model", "llama3.2"),
            temperature=llm_config.get("temperature", 0.7),
            base_url=base_url,
        )
        self.llm_v = None
        if llm_v_config:
            v_url = _build_ollama_url(llm_v_config)
            self.llm_v = ChatOllama(
                model=llm_v_config.get("model", "llava"),
                temperature=llm_v_config.get("temperature", 0.5),
                base_url=v_url,
            )
        self._parser = StrOutputParser()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render(self, template_key: str, **kwargs) -> str:
        cfg = self.prompts_config.get(template_key, {})
        system_tpl = cfg.get("system_template", "{persona}")
        user_tpl = cfg.get("user_template", "{content}")
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_tpl),
            ("human", user_tpl),
        ])
        chain = prompt | self.llm | self._parser
        try:
            return chain.invoke(kwargs).strip()
        except Exception as exc:
            logger.warning(f"LLM call failed ({template_key}): {exc}")
            return ""

    def _get_persona(self, cluster_id: int) -> str:
        personas = self.prompts_config.get("personas", DEFAULT_PROMPTS["personas"])
        return personas.get(str(cluster_id), personas.get("0", "You are an Instagram user."))

    # ------------------------------------------------------------------
    # Public API (called via ray.remote)
    # ------------------------------------------------------------------

    def generate_caption(self, topic: str, day: int, slot: int,
                         cluster_id: int = 0, agent_attrs: Optional[dict] = None) -> str:
        """Generate an Instagram caption for a photo."""
        persona = self._get_persona(cluster_id)
        return self._render("generate_caption", persona=persona, topic=topic,
                            day=day, slot=slot)

    def decide_reaction(self, caption: str, cluster_id: int = 0) -> str:
        """Decide how to react to a photo (LIKE / LOVE / LAUGH / WOW / SAD / ANGRY / IGNORE)."""
        result = self._render("decide_reaction", caption=caption,
                              cluster_id=cluster_id).upper()
        allowed = {"LIKE", "LOVE", "LAUGH", "WOW", "SAD", "ANGRY", "IGNORE"}
        return result if result in allowed else "LIKE"

    def generate_comment(self, caption: str, author: str,
                         cluster_id: int = 0, agent_attrs: Optional[dict] = None,
                         image_url: Optional[str] = None) -> str:
        """Generate a comment on a photo."""
        persona = self._get_persona(cluster_id)
        
        # If we have an image and a vision model, route to vision
        if image_url and self.llm_v:
            cfg = self.prompts_config.get("generate_comment", DEFAULT_PROMPTS["generate_comment"])
            system_tpl = cfg.get("system_template", "{persona}")
            user_tpl = cfg.get("user_template", "{content}")
            
            # Append the image tag so the vision model parses it (following describe_photo convention)
            user_tpl += "\n<img {image_url}>"
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_tpl),
                ("human", user_tpl),
            ])
            chain = prompt | self.llm_v | self._parser
            try:
                return chain.invoke({"persona": persona, "caption": caption, "author": author, "image_url": image_url}).strip()
            except Exception as exc:
                logger.warning(f"Vision LLM call failed for comment: {exc}")
                # Fallback to standard text LLM below
                
        return self._render("generate_comment", persona=persona,
                            caption=caption, author=author)

    def describe_photo(self, url: str) -> str:
        """Generate an alt-text description for a photo URL (requires vision model)."""
        if not self.llm_v:
            return ""
        cfg = self.prompts_config.get("describe_photo", DEFAULT_PROMPTS["describe_photo"])
        prompt = ChatPromptTemplate.from_messages([
            ("system", cfg.get("system_template")),
            ("human", cfg.get("user_template")),
        ])
        chain = prompt | self.llm_v | self._parser
        try:
            return chain.invoke({"url": url}).strip()
        except Exception as exc:
            logger.warning(f"Vision LLM call failed: {exc}")
            return ""

    def decide_follow(self, username: str, bio: str, topics: str,
                      cluster_id: int = 0) -> str:
        """Decide whether to follow a user (FOLLOW / SKIP)."""
        persona = self._get_persona(cluster_id)
        result = self._render("decide_follow", persona=persona,
                              username=username, bio=bio or "", topics=topics or "").upper()
        return "FOLLOW" if "FOLLOW" in result else "SKIP"

    def decide_follow_request(self, username: str, bio: str,
                              cluster_id: int = 0) -> str:
        """Decide whether to accept a follow request (ACCEPT / REJECT)."""
        persona = self._get_persona(cluster_id)
        # Using a fallback text or custom template
        prompt = f"Your persona: {persona}\nUser '{username}' with bio '{bio}' requested to follow you. Do you ACCEPT or REJECT? Reply with exactly ACCEPT or REJECT."
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            resp = self.llm.invoke([SystemMessage(content=prompt)])
            text = resp.content.upper()
            return "ACCEPTED" if "ACCEPT" in text else "REJECTED"
        except Exception as exc:
            return "ACCEPTED"

    def batch_generate_captions(self, requests: List[dict]) -> List[str]:
        """Generate captions for a batch of requests sequentially."""
        return [
            self.generate_caption(
                topic=r.get("topic", "general"),
                day=r.get("day", 0),
                slot=r.get("slot", 0),
                cluster_id=r.get("cluster_id", 0),
                agent_attrs=r.get("agent_attrs"),
            )
            for r in requests
        ]

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "ollama",
            "supports_native_batching": False,
            "supports_vision": self.llm_v is not None,
        }
