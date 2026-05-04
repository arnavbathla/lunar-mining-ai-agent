"""Scriptable fake Anthropic client used by tests.

Mirrors the response shape of ``anthropic.Anthropic.messages.create``. The
constructor takes a list of pre-built turns; each turn is either a final
text response or a list of tool_use blocks. The agent loop appends tool
results and the fake client advances to the next scripted turn.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FakeBlock:
    type: str  # "text" | "tool_use"
    text: Optional[str] = None
    id: Optional[str] = None
    name: Optional[str] = None
    input: Optional[Dict[str, Any]] = None


@dataclass
class FakeMessage:
    content: List[FakeBlock]
    stop_reason: str = "end_turn"
    model: str = "fake-claude"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stop_reason": self.stop_reason,
            "model": self.model,
            "content": [
                {
                    "type": b.type,
                    "text": b.text,
                    "id": b.id,
                    "name": b.name,
                    "input": b.input,
                }
                for b in self.content
            ],
        }


@dataclass
class FakeTurn:
    """One scripted Claude response."""

    blocks: List[FakeBlock]
    stop_reason: str = "tool_use"


@dataclass
class FakeAnthropicClient:
    turns: List[FakeTurn]
    _index: int = field(default=0, init=False)

    def messages_create(
        self,
        *,
        model: str,
        system: str,
        tools: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        max_tokens: int = 4096,
    ) -> FakeMessage:
        if self._index >= len(self.turns):
            # Default to a deterministic end_turn so the agent loop terminates.
            return FakeMessage(
                content=[FakeBlock(type="text", text="```json\n{}\n```")],
                stop_reason="end_turn",
                model=model,
            )
        turn = self.turns[self._index]
        self._index += 1
        return FakeMessage(
            content=turn.blocks,
            stop_reason=turn.stop_reason,
            model=model,
        )


def tool_use_turn(name: str, tool_id: str, payload: Dict[str, Any]) -> FakeTurn:
    return FakeTurn(
        blocks=[FakeBlock(type="tool_use", id=tool_id, name=name, input=payload)],
        stop_reason="tool_use",
    )


def final_text_turn(text: str) -> FakeTurn:
    return FakeTurn(
        blocks=[FakeBlock(type="text", text=text)],
        stop_reason="end_turn",
    )
