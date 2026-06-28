"""LLM client factory.

A single place that builds the ChatOpenAI model. The `base_url` is configurable
so the *exact same code* can either call OpenAI directly or be pointed at an AI
gateway (Obot's LLM proxy, LiteLLM, Helicone, ...) that tracks token spend in
USD without any change to the agent - the "AI gateway" story from Layer 4.
"""

from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from .config import get_settings


@lru_cache(maxsize=4)
def get_chat_model(temperature: float = 0.1) -> ChatOpenAI:
    s = get_settings()
    if not s.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and fill it in."
        )
    kwargs: dict = {
        "model": s.openai_model,
        "temperature": temperature,
        "api_key": s.openai_api_key,
    }
    # When an AI gateway is configured, every request flows through it. The
    # gateway sees prompt/response token usage and computes realized USD cost.
    if s.openai_base_url:
        kwargs["base_url"] = s.openai_base_url
    return ChatOpenAI(**kwargs)
