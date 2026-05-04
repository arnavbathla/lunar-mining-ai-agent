"""Thin wrapper around the official Anthropic SDK."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol

from app.config import settings


class ClaudeClient(Protocol):
    """Minimal interface used by the agent loop."""

    def messages_create(
        self,
        *,
        model: str,
        system: str,
        tools: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        max_tokens: int = 4096,
    ) -> Any:  # SDK returns a Message object
        ...


class AnthropicClient:
    """Real Anthropic client wrapper."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY required for Claude agent execution."
            )
        # Imported lazily so the backend boots without the dependency installed.
        from anthropic import Anthropic  # type: ignore

        self._client = Anthropic(api_key=api_key)

    def messages_create(
        self,
        *,
        model: str,
        system: str,
        tools: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        max_tokens: int = 4096,
    ) -> Any:
        return self._client.messages.create(
            model=model,
            system=system,
            tools=tools,
            messages=messages,
            max_tokens=max_tokens,
        )


def make_real_client() -> AnthropicClient:
    """Construct the real Anthropic client using settings from env."""
    if not settings.anthropic_configured:
        raise ValueError(
            "ANTHROPIC_API_KEY required for Claude agent execution."
        )
    return AnthropicClient(api_key=settings.ANTHROPIC_API_KEY)
