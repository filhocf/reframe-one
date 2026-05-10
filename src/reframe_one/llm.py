"""Configurable LLM interface for text processing."""

import os
from dataclasses import dataclass

import httpx


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: str = "ollama"  # ollama, groq, openai
    model: str = "mistral"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    timeout: int = 30

    def __post_init__(self):
        # Auto-detect from env if not set
        if not self.api_key:
            env_map = {"groq": "GROQ_API_KEY", "openai": "OPENAI_API_KEY"}
            if self.provider in env_map:
                self.api_key = os.environ.get(env_map[self.provider], "")
        if self.provider == "groq" and self.base_url == "http://localhost:11434":
            self.base_url = "https://api.groq.com/openai/v1"
        if self.provider == "openai" and self.base_url == "http://localhost:11434":
            self.base_url = "https://api.openai.com/v1"


def llm_chat(config: LLMConfig, system: str, user: str) -> str | None:
    """Send a chat completion request. Returns response text or None on failure."""
    try:
        if config.provider == "ollama":
            return _ollama_chat(config, system, user)
        else:
            return _openai_chat(config, system, user)
    except httpx.TimeoutException:
        return None
    except httpx.HTTPStatusError:
        return None
    except (httpx.ConnectError, OSError):
        return None


def _ollama_chat(config: LLMConfig, system: str, user: str) -> str | None:
    resp = httpx.post(
        f"{config.base_url}/api/chat",
        json={
            "model": config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json",
        },
        timeout=config.timeout,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _openai_chat(config: LLMConfig, system: str, user: str) -> str | None:
    headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
    resp = httpx.post(
        f"{config.base_url}/chat/completions",
        headers=headers,
        json={
            "model": config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
        },
        timeout=config.timeout,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
