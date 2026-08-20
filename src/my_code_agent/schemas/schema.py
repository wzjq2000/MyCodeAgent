from dataclasses import dataclass

from pydantic import BaseModel, Field

from my_code_agent.constants.node_constants import NodeNameEnum


class ReadNodeArg(BaseModel):
    """Arguments for the READ_FILE node."""

    file_path: str = Field(
        default="",
        description="The path of the file to read, either relative to the project root or absolute.",
    )
    offset: int = Field(
        default=1,
        ge=1,
        description="The 1-based line number to start reading from.",
    )
    limit: int = Field(
        default=1000,
        ge=1,
        le=100000,
        description="The maximum number of lines to read.",
    )

@dataclass
class FileReadResult:
    file_path: str
    content: str
    num_lines: int
    start_line: int
    total_lines: int


class NodeDispatchResult(BaseModel):
    """The planner's decision on which node to execute next and its arguments."""

    next_node: NodeNameEnum = Field(
        description="The node that should be executed next.",
    )
    read_node: ReadNodeArg = Field(
        description="Arguments for the READ_FILE node. Only relevant when next_node is READ_FILE.",
    )