"""
Standard (single-request) LLM service for YPhotoSharing clients.

Supports Ollama and any OpenAI-compatible endpoint.
Only client-side components may import this module.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("LANGCHAIN_VERBOSE", "false")

import ray
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama

from YPhotoSharing.common_utils import build_structured_file_logger
from YPhotoSharing.YClient.LLM_interactions.usage_tracker import LLMUsageTracker

logger = logging.getLogger(__name__)


def _build_ollama_url(llm_config: dict) -> str:
    address = llm_config.get("address", "localhost")
    port = llm_config.get("port", 11434)
    # Strip protocol if accidentally included
    address = address.replace("http://", "").replace("https://", "")
    if ":" in address:
        url = f"http://{address}"
    else:
        url = f"http://{address}:{port}"
    return url.replace("/v1", "")



def _estimate_tokens_from_text(*parts: Any) -> int:
    text = " ".join(str(part) for part in parts if part is not None).strip()
    if not text:
        return 0
    return max(1, len(text) // 4)

def _join_nonempty(values: List[Any], separator: str = ", ") -> str:
    return separator.join(
        str(value).strip()
        for value in values
        if value is not None and str(value).strip()
    )


def _format_custom_features(agent_attrs: Optional[Dict[str, Any]]) -> str:
    custom_features = dict((agent_attrs or {}).get("custom_features") or {})
    if not custom_features:
        return ""

    parts: List[str] = []
    for key in sorted(custom_features.keys(), key=lambda value: str(value).lower()):
        label = str(key).strip()
        if not label:
            continue
        raw_value = custom_features.get(key)
        value = str(raw_value).strip() if raw_value is not None else ""
        parts.append(f"{label}: {value}" if value else label)

    if not parts:
        return ""
    return f"Additional personal details: {'; '.join(parts)}."


def _format_persona_context(agent_attrs: Optional[Dict[str, Any]]) -> str:
    attrs = agent_attrs or {}
    if not attrs:
        return ""

    clauses: List[str] = []

    age = attrs.get("age")
    gender = str(attrs.get("gender") or "").strip()
    nationality = str(attrs.get("nationality") or "").strip()
    education_level = str(attrs.get("education_level") or "").strip()
    profession = str(attrs.get("profession") or "").strip()
    leaning = str(attrs.get("leaning") or "").strip()
    activity_profile = str(attrs.get("activity_profile") or "").strip()
    archetype = str(attrs.get("archetype") or "").strip()
    language = str(attrs.get("language") or "").strip()
    bio = str(attrs.get("bio") or "").strip()

    profile_bits: List[str] = []
    if age not in (None, ""):
        profile_bits.append(f"{age}-year-old")
    if gender:
        profile_bits.append(gender)
    if nationality:
        profile_bits.append(f"from {nationality}")
    if education_level:
        profile_bits.append(f"educated to {education_level} level")
    if profession:
        profile_bits.append(f"working as a {profession}")
    if leaning:
        profile_bits.append(f"politically {leaning}")
    if activity_profile:
        profile_bits.append(f"activity profile {activity_profile}")
    if archetype:
        profile_bits.append(f"archetype {archetype}")
    if language:
        profile_bits.append(f"speaks {language}")
    if profile_bits:
        clauses.append(f"Profile: {', '.join(profile_bits)}.")

    trait_labels = [
        ("oe", "openness"),
        ("co", "conscientiousness"),
        ("ex", "extraversion"),
        ("ag", "agreeableness"),
        ("ne", "neuroticism"),
    ]
    trait_bits = [
        f"{label}={attrs.get(key)}"
        for key, label in trait_labels
        if attrs.get(key) not in (None, "")
    ]
    if trait_bits:
        clauses.append(f"Personality traits: {'; '.join(trait_bits)}.")

    status_bits: List[str] = []
    if attrs.get("is_verified"):
        status_bits.append("verified account")
    if attrs.get("is_private"):
        status_bits.append("private account")
    if attrs.get("is_page"):
        status_bits.append("page account")
    if attrs.get("toxicity") not in (None, ""):
        status_bits.append(f"toxicity preference {attrs.get('toxicity')}")
    if status_bits:
        clauses.append(f"Account status: {', '.join(status_bits)}.")

    interests = attrs.get("interests") or []
    if isinstance(interests, list) and interests:
        clauses.append(f"Interests: {_join_nonempty(interests)}.")

    if bio:
        clauses.append(f"Bio: {bio}.")

    photo_sharing = attrs.get("photo_sharing")
    if isinstance(photo_sharing, dict) and photo_sharing:
        photo_bits: List[str] = []
        favorite_filters = photo_sharing.get("favorite_filters") or []
        if isinstance(favorite_filters, list) and favorite_filters:
            photo_bits.append(f"favorite filters: {_join_nonempty(favorite_filters)}")
        story_visibility = str(photo_sharing.get("story_visibility") or "").strip()
        if story_visibility:
            photo_bits.append(f"story visibility: {story_visibility}")
        creator_tier = str(photo_sharing.get("creator_tier") or "").strip()
        if creator_tier:
            photo_bits.append(f"creator tier: {creator_tier}")
        if photo_bits:
            clauses.append(f"Photo-sharing profile: {'; '.join(photo_bits)}.")

    custom_features = _format_custom_features(attrs)
    if custom_features:
        clauses.append(custom_features)

    return " ".join(clauses)



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
        self.prompts_config = prompts_config or {}
        logging_config = logging_config or {}
        log_dir = Path(logging_config.get("log_dir", "."))
        instance_name = str(logging_config.get("instance_name", "client"))
        self.usage_tracker = None
        if logging_config.get("enable_llm_usage_log", True):
            self.usage_tracker = LLMUsageTracker(
                logger=logging.getLogger(f"YPhotoSharing.LLMUsage.{instance_name}"),
                log_file_path=log_dir / f"{instance_name}_llm_usage.log",
                enable_file_logging=True,
            )
        self.prompt_logger = None
        if logging_config.get("enable_prompt_log", False):
            self.prompt_logger = build_structured_file_logger(
                f"YPhotoSharing.ClientPrompts.{instance_name}",
                log_dir / "llm_prompts.log",
                level=logging.DEBUG,
                backup_count=3,
                max_bytes=50 * 1024 * 1024,
                indent=2,
                include_module=False,
                propagate=False,
            )
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
        self._setup_logger(logging_config)

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

        logger.info(f"LLMService logger configured to write to {log_file}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _log_prompt(self, template_key: str, payload: Dict[str, Any], response: str, *, backend: str) -> None:
        if not self.prompt_logger:
            return
        safe_payload = {}
        for key, value in payload.items():
            if key in {"image_url", "url"} and value:
                safe_payload[key] = "<redacted>"
            elif key == "agent_attrs" and isinstance(value, dict):
                safe_payload[key] = sorted(value.keys())
            elif key == "peers_opinions" and isinstance(value, list):
                safe_payload[key] = len(value)
            else:
                safe_payload[key] = value
        self.prompt_logger.info(
            "LLM prompt evaluated",
            extra={
                "extra_data": {
                    "template": template_key,
                    "backend": backend,
                    "input_keys": sorted(safe_payload.keys()),
                    "inputs": safe_payload,
                    "response": response[:400],
                    "response_length": len(response),
                }
            },
        )

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
            response = chain.invoke(kwargs).strip()
            self._log_prompt(template_key, kwargs, response, backend="text")
            if self.usage_tracker:
                self.usage_tracker.record_call(
                    template_key,
                    input_tokens=_estimate_tokens_from_text(kwargs),
                    output_tokens=_estimate_tokens_from_text(response),
                )
            return response
        except Exception as exc:
            logger.warning(f"LLM call failed ({template_key}): {exc}")
            return ""

    def _get_persona(self, cluster_id: int) -> str:
        personas = self.prompts_config.get("personas", {})
        return personas.get(str(cluster_id), personas.get("0", "You are an Instagram user."))

    def _build_persona(self, cluster_id: int, agent_attrs: Optional[dict] = None) -> str:
        persona = self._get_persona(cluster_id)
        agent_context = _format_persona_context(agent_attrs)
        if agent_context:
            return f"{persona.rstrip()} {agent_context}"
        return persona

    # ------------------------------------------------------------------
    # Public API (called via ray.remote)
    # ------------------------------------------------------------------

    def generate_caption(self, topic: str, day: int, slot: int,
                         cluster_id: int = 0, agent_attrs: Optional[dict] = None) -> str:
        """Generate an Instagram caption for a photo."""
        persona = self._build_persona(cluster_id, agent_attrs)
        mention_instruction = ""
        if agent_attrs and "following_usernames" in agent_attrs and agent_attrs["following_usernames"]:
            users = ", ".join([f"@{u}" for u in agent_attrs["following_usernames"]])
            mention_instruction = f"You may optionally mention these users: {users}"
            
        return self._render("generate_caption", persona=persona, topic=topic,
                            day=day, slot=slot, mention_instruction=mention_instruction)

    def decide_reaction(self, caption: str, cluster_id: int = 0, agent_attrs: Optional[dict] = None) -> str:
        """Decide how to react to a photo (LIKE / LOVE / LAUGH / WOW / SAD / ANGRY / IGNORE)."""
        result = self._render(
            "decide_reaction",
            caption=caption,
            cluster_id=cluster_id,
            persona=self._build_persona(cluster_id, agent_attrs),
        ).upper()
        allowed = {"LIKE", "LOVE", "LAUGH", "WOW", "SAD", "ANGRY", "IGNORE"}
        return result if result in allowed else "LIKE"

    def generate_comment(self, caption: str, author: str,
                         cluster_id: int = 0, agent_attrs: Optional[dict] = None,
                         image_url: Optional[str] = None) -> str:
        """Generate a comment on a photo."""
        persona = self._build_persona(cluster_id, agent_attrs)
        
        mention_instruction = f"You may @mention the author (@{author}). "
        memory_context = ""
        if agent_attrs:
            if agent_attrs.get("following_usernames"):
                users = ", ".join([f"@{u}" for u in agent_attrs["following_usernames"]])
                mention_instruction += f"You may also optionally mention these users: {users}"
            if agent_attrs.get("memory_context"):
                memory_context = agent_attrs["memory_context"]
                
        # Inject memory context into caption for standard prompt (lazy way since we can't easily alter all prompts_config structures safely without a larger refactor)
        if memory_context:
            caption = f"{caption}\n\n[System note: {memory_context}]"
            
        # If we have an image and a vision model, route to vision
        if image_url and self.llm_v:
            cfg = self.prompts_config.get("generate_comment", {})
            system_tpl = cfg.get("system_template", "{persona}")
            user_tpl = cfg.get("user_template", "{content}")
            
            # Append the image tag so the vision model parses it
            user_tpl += "\n<img {image_url}>"
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_tpl),
                ("human", user_tpl),
            ])
            chain = prompt | self.llm_v | self._parser
            try:
                response = chain.invoke({
                    "persona": persona, 
                    "caption": caption, 
                    "author": author, 
                    "image_url": image_url,
                    "mention_instruction": mention_instruction
                }).strip()
                self._log_prompt(
                    "generate_comment",
                    {
                        "persona": persona,
                        "caption": caption,
                        "author": author,
                        "image_url": image_url,
                        "mention_instruction": mention_instruction,
                    },
                    response,
                    backend="vision",
                )
                if self.usage_tracker:
                    self.usage_tracker.record_call(
                        "generate_comment",
                        input_tokens=_estimate_tokens_from_text(persona, caption, author, image_url, mention_instruction),
                        output_tokens=_estimate_tokens_from_text(response),
                    )
                return response
            except Exception as exc:
                logger.warning(f"Vision LLM call failed for comment: {exc}")
                # Fallback to standard text LLM below
                
        return self._render("generate_comment", persona=persona,
                            caption=caption, author=author, 
                            mention_instruction=mention_instruction)

    def describe_photo(self, url: str) -> str:
        """Generate an alt-text description for a photo URL (requires vision model)."""
        if not self.llm_v:
            return ""
        cfg = self.prompts_config.get("describe_photo", {})
        prompt = ChatPromptTemplate.from_messages([
            ("system", cfg.get("system_template")),
            ("human", cfg.get("user_template")),
        ])
        chain = prompt | self.llm_v | self._parser
        try:
            response = chain.invoke({"url": url}).strip()
            self._log_prompt("describe_photo", {"url": url}, response, backend="vision")
            if self.usage_tracker:
                self.usage_tracker.record_call(
                    "describe_photo",
                    input_tokens=_estimate_tokens_from_text(url),
                    output_tokens=_estimate_tokens_from_text(response),
                )
            return response
        except Exception as exc:
            logger.warning(f"Vision LLM call failed: {exc}")
            return ""

    def extract_emotions(self, text: str) -> List[str]:
        """Extract GoEmotions labels from text using the YSimulator-compatible prompt."""
        cfg = self.prompts_config.get("extract_emotions", {})
        system_template = cfg.get(
            "system_template",
            "You are an emotion classification assistant. Identify which emotions from the GoEmotions taxonomy the given text elicits.",
        )
        user_template = cfg.get(
            "user_template",
            'Identify emotions from this text. Choose ONLY from: {emotion_list}\n\nText: "{text}"\n\nReturn emotions as comma-separated list:',
        )
        emotion_list_text = (
            "admiration, amusement, anger, annoyance, approval, caring, confusion, curiosity, "
            "desire, disappointment, disapproval, disgust, embarrassment, excitement, fear, "
            "gratitude, grief, joy, love, nervousness, optimism, pride, realization, relief, "
            "remorse, sadness, surprise, trust"
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", user_template),
        ])
        chain = prompt | self.llm | self._parser
        try:
            result = chain.invoke({"text": text, "emotion_list": emotion_list_text}).strip()
            self._log_prompt(
                "extract_emotions",
                {"text": text, "emotion_list": emotion_list_text},
                result,
                backend="text",
            )
            if self.usage_tracker:
                self.usage_tracker.record_call(
                    "extract_emotions",
                    input_tokens=_estimate_tokens_from_text(text, emotion_list_text),
                    output_tokens=_estimate_tokens_from_text(result),
                )
        except Exception as exc:
            logger.warning(f"LLM call failed (extract_emotions): {exc}")
            return []
        emotion_list = {
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
        parsed = [
            token.strip().lower()
            for token in str(result).replace("[", "").replace("]", "").split(",")
            if token.strip()
        ]
        return [emotion for emotion in parsed if emotion in emotion_list]

    def extract_emotion(self, text: str) -> str:
        """Backward-compatible single-emotion helper."""
        emotions = self.extract_emotions(text)
        return emotions[0] if emotions else "neutral"

    def decide_follow(self, username: str, bio: str, topics: str,
                      cluster_id: int = 0, agent_attrs: Optional[dict] = None) -> str:
        """Decide whether to follow a user (FOLLOW / SKIP)."""
        persona = self._build_persona(cluster_id, agent_attrs)
        result = self._render(
            "decide_follow",
            persona=persona,
            username=username,
            bio=bio or "",
            topics=topics or "",
        ).upper()
        return "FOLLOW" if "FOLLOW" in result else "SKIP"

    def decide_follow_request(self, username: str, bio: str,
                              cluster_id: int = 0, agent_attrs: Optional[dict] = None) -> str:
        """Decide whether to accept a follow request (ACCEPT / REJECT)."""
        persona = self._build_persona(cluster_id, agent_attrs)
        result = self._render(
            "decide_follow_request",
            persona=persona,
            username=username,
            bio=bio or "",
        ).upper()
        return "ACCEPT" if "ACCEPT" in result else "REJECT"

    # ------------------------------------------------------------------
    # Stage 5 & 6 Handlers
    # ------------------------------------------------------------------

    def extract_sentiment(self, text: str) -> float:
        """Extract sentiment polarity as a float (1.0 = positive, -1.0 = negative, 0.0 = neutral)."""
        result = self._render("extract_sentiment", text=text).upper()
        if "POSITIVE" in result:
            return 1.0
        elif "NEGATIVE" in result:
            return -1.0
        else:
            return 0.0

    def infer_photo_opinion(self, photo_caption: str, topic: str, opinion_options: List[str], agent_id: str = "") -> str:
        """Infer the stance of a photo on a topic based on available opinion options."""
        options_str = ", ".join(opinion_options)
        result = self._render("infer_article_opinion", article_text=photo_caption, topic=topic, opinion_options=options_str).strip()
        for opt in opinion_options:
            if opt.lower() in result.lower():
                return opt
        return opinion_options[len(opinion_options) // 2]  # Fallback to middle option

    def evaluate_opinion(self, post_content: str, author_name: str, topic: str, current_opinion: float) -> float:
        """Legacy numeric opinion helper retained for compatibility."""
        result = self._render(
            "evaluate_opinion",
            post_content=post_content,
            author_name=author_name,
            topic=topic,
            current_opinion=current_opinion,
        ).strip()
        try:
            import re

            match = re.search(r"[-+]?\d*\.\d+|\d+", result)
            if match:
                score = float(match.group())
                return max(0.0, min(1.0, score))
        except ValueError:
            pass
        return current_opinion

    def evaluate_opinion_transition(
        self,
        post_content: str,
        author_name: str,
        topic: str,
        current_label: str,
        author_label: str,
        opinion_scale: List[str],
        peers_opinions: Optional[List[tuple]] = None,
        agent_id: str = "",
    ) -> str:
        """Return an AGREE / DISAGREE / NEUTRAL transition for discrete opinion updates."""
        result = self._render(
            "evaluate_opinion_transition",
            post_content=post_content,
            author_name=author_name,
            topic=topic,
            current_label=current_label,
            author_label=author_label,
            opinion_scale=" > ".join(opinion_scale),
            peers_opinions=peers_opinions or [],
            agent_id=agent_id,
        ).strip().upper()
        for token in ("AGREE", "DISAGREE", "NEUTRAL"):
            if token in result:
                return token
        return "NEUTRAL"

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
