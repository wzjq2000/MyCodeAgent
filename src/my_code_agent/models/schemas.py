"""Shared Pydantic schemas used across the project."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    """Represents a single tool invocation."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    call_id: str | None = None


class ToolResult(BaseModel):
    """Result returned from a tool execution."""

    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


class AgentResponse(BaseModel):
    """Final response from an agent run."""

    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    iterations: int = 0
    started_at: datetime = Field(default_factory=datetime.now)
    finished_at: datetime | None = None
    model: str = ""
