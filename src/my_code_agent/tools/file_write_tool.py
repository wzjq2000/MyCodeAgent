"""
Python port of FileWriteTool.ts — create or overwrite a file.

Mirrors the TS behavior:
- validateInput: absolute path; existing files require a prior full Read and
  must not have been modified since that read.
- call: re-checks staleness atomically, writes content verbatim (LF, as sent
  by the model), then updates the session read state.
- Result messages match mapToolResultToToolResultBlockParam in FileWriteTool.ts.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

from .constants import FILE_UNEXPECTEDLY_MODIFIED_ERROR, FILE_READ_TOOL_NAME

if TYPE_CHECKING:
    from my_code_agent.state import FileReadState

WRITE_DESCRIPTION = (
    "Writes a file to the local filesystem.\n\n"
    "Usage:\n"
    "- This tool will overwrite the existing file if there is one at the provided path.\n"
    f"- If this is an existing file, you MUST use the {FILE_READ_TOOL_NAME} tool first to "
    "read the file's contents. This tool will fail if you did not read the file first.\n"
    "- Prefer the Edit tool for modifying existing files — it only sends the diff. Only "
    "use this tool to create new files or for complete rewrites.\n"
    "- NEVER create documentation files (*.md) or README files unless explicitly "
    "requested by the User.\n"
    "- Only use emojis if the user explicitly requests it. Avoid writing emojis to "
    "files unless asked."
)


class FileWriteInput(BaseModel):
    """Input schema for the Write tool (mirrors FileWriteTool.ts inputSchema)."""

    file_path: str = Field(
        description="The absolute path to the file to write (must be absolute, not relative)"
    )
    content: str = Field(description="The content to write to the file")


# ---------------------------------------------------------------------------
# Errors (mirrors validateInput error messages in FileWriteTool.ts)
# ---------------------------------------------------------------------------


class FileWriteError(Exception):
    """Base error for FileWriteTool."""

    def __init__(self, message: str, error_code: int = 0):
        super().__init__(message)
        self.error_code = error_code


class NotReadYetError(FileWriteError):
    """File exists but has not been read in this session (errorCode 2)."""

    def __init__(self):
        super().__init__(
            "File has not been read yet. Read it first before writing to it.",
            error_code=2,
        )


class ModifiedSinceReadError(FileWriteError):
    """File was modified after the last read (errorCode 3)."""

    def __init__(self):
        super().__init__(
            "File has been modified since read, either by the user or by a linter. Read "
            "it again before attempting to write it.",
            error_code=3,
        )


# ---------------------------------------------------------------------------
# FileWriteTool
# ---------------------------------------------------------------------------


class FileWriteTool:
    """Writes a file to the local filesystem (create or complete overwrite)."""

    def __init__(self, read_state: Optional["FileReadState"] = None):
        self._read_state = read_state

    # -- Validation ----------------------------------------------------------

    def validate_input(self, file_path: str) -> str:
        """
        Validate before writing. Returns the resolved absolute path.

        Raises FileWriteError on invalid input.
        """
        # Path must be absolute
        if not file_path.startswith("/"):
            raise FileWriteError(
                f"The file_path parameter must be an absolute path, not a relative path. "
                f"Received: '{file_path}'",
                error_code=1,
            )

        full_path = str(Path(file_path).resolve())

        # New file — nothing to validate against the read state
        if not os.path.exists(full_path):
            return full_path

        # Existing file: must have been read (fully) in this session, and not
        # modified since. TS has a content-comparison fallback for Windows
        # cloud-sync false positives; skipped here (Linux/macOS timestamps).
        record = self._read_state.get(full_path) if self._read_state else None
        if record is None or record.is_partial_view:
            raise NotReadYetError()

        last_write_time = os.path.getmtime(full_path)
        if last_write_time > record.timestamp:
            raise ModifiedSinceReadError()

        return full_path

    # -- Core write ----------------------------------------------------------

    async def call(self, file_path: str, content: str) -> str:
        """
        Write content to file_path, creating it if needed.

        Returns the claude-code result message:
        - "File created successfully at: <path>" for new files
        - "The file <path> has been updated successfully." for existing files
        """
        full_path = self.validate_input(file_path)

        # Ensure parent directory exists before the read-modify-write section.
        # (Mirrors the TS comment: must happen outside the critical section.)
        Path(full_path).parent.mkdir(parents=True, exist_ok=True)

        # Load current state and confirm no changes since last read. No async
        # work between here and the write, to preserve atomicity.
        old_content: Optional[str] = None
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                old_content = f.read()
        except FileNotFoundError:
            old_content = None

        if old_content is not None:
            record = self._read_state.get(full_path) if self._read_state else None
            if record is None or os.path.getmtime(full_path) > record.timestamp:
                raise FileWriteError(FILE_UNEXPECTEDLY_MODIFIED_ERROR, error_code=3)

        # Write is a full content replacement — the model sent explicit line
        # endings in `content` and meant them. Do not rewrite them (newline=""
        # disables universal-newline translation).
        with open(full_path, "w", encoding="utf-8", newline="") as f:
            f.write(content)

        # Update read timestamp, to invalidate stale writes
        if self._read_state is not None:
            self._read_state.record(full_path, content)

        if old_content is None:
            return f"File created successfully at: {file_path}"
        return f"The file {file_path} has been updated successfully."