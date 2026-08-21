"""
Graph state and session-scoped file-read state.

- AgentState mirrors query.ts's State (trimmed): the messages list flows
  around the loop with an add_messages reducer, plus the turn counter used
  for the maxTurns check.
- FileReadState mirrors readFileState in claude-code's ToolUseContext:
  Write/Edit use it to enforce read-before-write and modified-since-read.
"""

import time
from dataclasses import dataclass
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    """State shared by all graph nodes (query.ts State, trimmed)."""

    messages: Annotated[list[AnyMessage], add_messages]
    turn_count: int
    max_turns: int


@dataclass
class FileReadRecord:
    content: str
    timestamp: float
    is_partial_view: bool = False


class FileReadState:
    """Session-scoped record of which files were read, when, and how much."""

    def __init__(self) -> None:
        self._records: dict[str, FileReadRecord] = {}

    def get(self, path: str) -> FileReadRecord | None:
        return self._records.get(path)

    def record(self, path: str, content: str, *, partial: bool = False) -> None:
        self._records[path] = FileReadRecord(
            content=content,
            timestamp=time.time(),
            is_partial_view=partial,
        )