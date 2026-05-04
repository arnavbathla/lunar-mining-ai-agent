"""Anthropic Claude tool-use agent loop for Lunar MineOps AI OS."""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.agents.prompts import CORE_SYSTEM_PROMPT
from app.agents.tool_registry import execute_tool, get_tool_definitions
from app.config import settings
from app.db.models import AgentRun

MAX_ITERATIONS = 8


# ---------------------------------------------------------------------------
# Block normalisation - handles real SDK objects and our FakeMessage
# ---------------------------------------------------------------------------


def _block_attr(block: Any, name: str, default: Any = None) -> Any:
    if isinstance(block, dict):
        return block.get(name, default)
    return getattr(block, name, default)


def _block_dict(block: Any) -> Dict[str, Any]:
    """Normalise an Anthropic content block to a serialisable dict."""
    btype = _block_attr(block, "type")
    if btype == "tool_use":
        return {
            "type": "tool_use",
            "id": _block_attr(block, "id"),
            "name": _block_attr(block, "name"),
            "input": _block_attr(block, "input") or {},
        }
    if btype == "text":
        return {"type": "text", "text": _block_attr(block, "text") or ""}
    # Fallback - serialise unknown shapes verbatim
    return {"type": btype or "unknown", "raw": str(block)}


def _normalise_response(resp: Any) -> Tuple[List[Dict[str, Any]], str, str]:
    """Return (content_blocks, stop_reason, model)."""
    if isinstance(resp, dict):
        content = resp.get("content") or []
        return (
            [_block_dict(b) for b in content],
            resp.get("stop_reason", "end_turn"),
            resp.get("model", ""),
        )
    content = getattr(resp, "content", []) or []
    return (
        [_block_dict(b) for b in content],
        getattr(resp, "stop_reason", "end_turn"),
        getattr(resp, "model", ""),
    )


# ---------------------------------------------------------------------------
# Final JSON extraction
# ---------------------------------------------------------------------------


_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*(?P<body>\{.*?\})\s*```",
    re.DOTALL | re.IGNORECASE,
)


def parse_final_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    match = _JSON_FENCE_RE.search(text)
    candidate = match.group("body") if match else None
    if not candidate:
        # Try to find a top-level JSON object.
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            candidate = text[first : last + 1]
    if not candidate:
        return {}
    try:
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


class AgentLoopResult(Dict[str, Any]):
    """Returned by ``run_agent_loop``. Concrete keys:

    - agent_run_id
    - tool_calls (List[Dict])
    - final_text
    - final_json (Dict)
    - model
    - created_at (ISO 8601 string)
    """


def run_agent_loop(
    *,
    db: Session,
    client: Any,
    agent_type: str,
    mission_id: Optional[str],
    user_prompt: str,
    system_prompt: str = CORE_SYSTEM_PROMPT,
    max_iterations: int = MAX_ITERATIONS,
    model: Optional[str] = None,
) -> AgentLoopResult:
    """Run the iterative tool-use loop and persist an AgentRun.

    Raises ``RuntimeError`` if the SDK call fails (caller surfaces 502/400).
    """
    tools = get_tool_definitions()
    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": user_prompt},
    ]
    tool_calls: List[Dict[str, Any]] = []
    final_text = ""
    last_model = model or settings.ANTHROPIC_MODEL

    for iteration in range(1, max_iterations + 1):
        try:
            response = client.messages_create(
                model=last_model,
                system=system_prompt,
                tools=tools,
                messages=messages,
                max_tokens=4096,
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Anthropic call failed: {exc}") from exc

        blocks, stop_reason, response_model = _normalise_response(response)
        if response_model:
            last_model = response_model

        # Append assistant turn (text + tool_use) to message history
        messages.append({"role": "assistant", "content": blocks})

        tool_use_blocks = [b for b in blocks if b.get("type") == "tool_use"]
        text_blocks = [b for b in blocks if b.get("type") == "text"]

        if tool_use_blocks:
            tool_results: List[Dict[str, Any]] = []
            for tu in tool_use_blocks:
                name = tu.get("name") or ""
                tu_id = tu.get("id") or str(uuid.uuid4())
                payload = tu.get("input") or {}
                try:
                    output = execute_tool(db, name, payload)
                    is_error = False
                except Exception as exc:  # noqa: BLE001
                    output = {"error": str(exc)}
                    is_error = True

                tool_calls.append(
                    {
                        "iteration": iteration,
                        "tool": name,
                        "input": payload,
                        "output_summary": _summarise_output(output),
                        "is_error": is_error,
                    }
                )

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tu_id,
                        "content": _stringify_for_tool_result(output),
                        "is_error": is_error,
                    }
                )

            messages.append({"role": "user", "content": tool_results})

            if stop_reason in ("end_turn", "stop_sequence"):
                # Some models stop after tools when they have no more work.
                final_text = _join_text(text_blocks)
                break
            continue

        # Pure text response: terminal state
        final_text = _join_text(text_blocks)
        break
    else:
        # Loop exhausted without break - capture whatever final text we got
        pass

    final_json = parse_final_json(final_text)

    agent_run = AgentRun(
        id=str(uuid.uuid4()),
        mission_id=mission_id,
        agent_type=agent_type,
        model=last_model,
        input_prompt=user_prompt,
        tool_calls_json=tool_calls,
        final_response_json=final_json,
        final_markdown=final_text,
    )
    db.add(agent_run)
    db.flush()

    return AgentLoopResult(
        agent_run_id=agent_run.id,
        tool_calls=tool_calls,
        final_text=final_text,
        final_json=final_json,
        model=last_model,
        created_at=agent_run.created_at.isoformat() if agent_run.created_at else datetime.now(timezone.utc).isoformat(),
    )


def _join_text(blocks: List[Dict[str, Any]]) -> str:
    return "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()


def _summarise_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """Return a compact, JSON-serialisable summary for AgentRun storage."""
    if not isinstance(output, dict):
        return {"value": str(output)[:500]}
    summary: Dict[str, Any] = {}
    for k, v in output.items():
        if isinstance(v, list):
            summary[k] = f"list(len={len(v)})"
        elif isinstance(v, dict):
            summary[k] = f"object(keys={sorted(v.keys())[:6]})"
        else:
            s = str(v)
            summary[k] = s if len(s) < 300 else s[:300] + "..."
    return summary


def _stringify_for_tool_result(output: Dict[str, Any]) -> str:
    """Convert a tool's dict output into the string body Anthropic expects."""
    try:
        return json.dumps(output, default=str)
    except (TypeError, ValueError):
        return json.dumps({"error": "non-serialisable tool output"})
