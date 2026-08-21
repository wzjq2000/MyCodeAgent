"""
Tool registry — the single LangChain touch point for the framework-agnostic
tool implementations below (mirrors how claude-code tools are independent
modules wrapped by buildTool()).

Each tool class stays free of LangChain dependencies; this module adapts them
into langchain_core StructuredTools that the graph can bind to the model.
"""

from typing import TYPE_CHECKING

from langchain_core.tools import StructuredTool

from .constants import FILE_EDIT_TOOL_NAME, FILE_READ_TOOL_NAME, FILE_WRITE_TOOL_NAME
from .file_edit_tool import EDIT_DESCRIPTION, FileEditInput, FileEditTool
from .file_read_tool import (
    READ_DESCRIPTION,
    FileReadInput,
    FileReadResult,
    FileReadTool,
)
from .file_write_tool import WRITE_DESCRIPTION, FileWriteInput, FileWriteTool

if TYPE_CHECKING:
    from my_code_agent.state import FileReadState

__all__ = [
    "FILE_EDIT_TOOL_NAME",
    "FILE_READ_TOOL_NAME",
    "FILE_WRITE_TOOL_NAME",
    "FileEditTool",
    "FileReadTool",
    "FileWriteTool",
    "build_tools",
]


def _format_read_result(result: FileReadResult) -> str:
    """Render a Read result the way claude-code feeds it back to the model."""
    end_line = result.start_line + result.num_lines - 1
    return (
        f"{result.file_path} (lines {result.start_line}-{end_line} of "
        f"{result.total_lines}):\n\n{result.content}"
    )


def build_tools(read_state: "FileReadState") -> list[StructuredTool]:
    """Create the Read/Write/Edit tools, sharing one session read state."""
    read_tool = FileReadTool(read_state=read_state)
    write_tool = FileWriteTool(read_state=read_state)
    edit_tool = FileEditTool(read_state=read_state)

    async def _read(file_path: str, offset: int = 1, limit: int | None = None) -> str:
        result = await read_tool.call(file_path, offset=offset, limit=limit)
        return _format_read_result(result)

    async def _write(file_path: str, content: str) -> str:
        return await write_tool.call(file_path, content)

    async def _edit(
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        return await edit_tool.call(file_path, old_string, new_string, replace_all)

    return [
        StructuredTool.from_function(
            name=FILE_READ_TOOL_NAME,
            description=READ_DESCRIPTION,
            args_schema=FileReadInput,
            coroutine=_read,
        ),
        StructuredTool.from_function(
            name=FILE_WRITE_TOOL_NAME,
            description=WRITE_DESCRIPTION,
            args_schema=FileWriteInput,
            coroutine=_write,
        ),
        StructuredTool.from_function(
            name=FILE_EDIT_TOOL_NAME,
            description=EDIT_DESCRIPTION,
            args_schema=FileEditInput,
            coroutine=_edit,
        ),
    ]