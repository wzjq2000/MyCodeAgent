
"""
Python port of FileReadTool.ts — text file reading only (no images, PDFs, notebooks).

Usage:
    tool = FileReadTool()
    result = await tool.call("/absolute/path/to/file.txt", offset=1, limit=50)
"""

import os
import stat
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from my_code_agent.schemas.schema import FileReadResult

# ---------------------------------------------------------------------------
# Constants (mirrors prompt.ts)
# ---------------------------------------------------------------------------

MAX_LINES_TO_READ = 2000
MAX_SIZE_BYTES = 256 * 1024  # 256 KB

# Device files that would hang the process (infinite output or blocking input)
BLOCKED_DEVICE_PATHS: set[str] = {
    "/dev/zero",
    "/dev/random",
    "/dev/urandom",
    "/dev/full",
    "/dev/stdin",
    "/dev/tty",
    "/dev/console",
    "/dev/stdout",
    "/dev/stderr",
    "/dev/fd/0",
    "/dev/fd/1",
    "/dev/fd/2",
}

# Extensions considered binary (not readable as text)
BINARY_EXTENSIONS: set[str] = {
    ".bin", ".exe", ".dll", ".so", ".dylib", ".o", ".obj",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar",
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv",
    ".ttf", ".otf", ".woff", ".woff2",
    ".pyc", ".class",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".ipynb",       # notebook — excluded from text path
    ".DS_Store",
}


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class FileReadError(Exception):
    """Base error for FileReadTool."""
    def __init__(self, message: str, error_code: int = 0):
        super().__init__(message)
        self.error_code = error_code


class FileNotFoundError_(FileReadError):
    """File does not exist (ENOENT)."""
    def __init__(self, file_path: str, suggestion: Optional[str] = None):
        cwd = os.getcwd()
        msg = f"File does not exist. The current working directory is {cwd}."
        if suggestion:
            msg += f" Did you mean {suggestion}?"
        super().__init__(msg, error_code=2)


class FileEmptyError(FileReadError):
    """File exists but is empty."""
    def __init__(self, file_path: str):
        super().__init__(
            f"<system-reminder>Warning: the file '{file_path}' exists but the contents are empty."
            f"</system-reminder>",
            error_code=3,
        )


class BinaryFileError(FileReadError):
    """File has a binary extension."""
    def __init__(self, file_path: str, ext: str):
        super().__init__(
            f"This tool cannot read binary files. The file appears to be a binary {ext} file.",
            error_code=4,
        )


class BlockedDeviceError(FileReadError):
    """File is a blocked device path."""
    def __init__(self, file_path: str):
        super().__init__(
            f"Cannot read '{file_path}': this device file would block or produce infinite output.",
            error_code=9,
        )


class MaxSizeExceededError(FileReadError):
    """File exceeds the maximum allowed size."""
    def __init__(self, file_path: str, size_bytes: int, max_bytes: int):
        super().__init__(
            f"File '{file_path}' ({_format_size(size_bytes)}) exceeds maximum allowed size "
            f"({_format_size(max_bytes)}). Use offset and limit parameters to read specific "
            f"portions of the file.",
            error_code=5,
        )


class OffsetBeyondFileError(FileReadError):
    """Offset is beyond the file's total lines."""
    def __init__(self, file_path: str, offset: int, total_lines: int):
        super().__init__(
            f"<system-reminder>Warning: the file '{file_path}' exists but is shorter than the "
            f"provided offset ({offset}). The file has {total_lines} lines.</system-reminder>",
            error_code=6,
        )





# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_size(size_bytes: int) -> str:
    """Human-readable file size, mirroring formatFileSize."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def _is_binary_extension(file_path: str) -> bool:
    ext = Path(file_path).suffix.lower()
    return ext in BINARY_EXTENSIONS


def _is_blocked_device(file_path: str) -> bool:
    if file_path in BLOCKED_DEVICE_PATHS:
        return True
    # Linux /proc/self/fd/0-2 and /proc/<pid>/fd/0-2 aliases for stdio
    if file_path.startswith("/proc/") and (
        file_path.endswith("/fd/0")
        or file_path.endswith("/fd/1")
        or file_path.endswith("/fd/2")
    ):
        return True
    return False


def _add_line_numbers(content: str, start_line: int = 1) -> str:
    """Format content with cat -n style line numbers."""
    if not content:
        return ""
    lines = content.split("\n")
    # Remove trailing empty string from split if content ends with newline
    if lines and lines[-1] == "":
        lines = lines[:-1]
    width = len(str(start_line + len(lines) - 1))
    numbered = []
    for i, line in enumerate(lines):
        num = start_line + i
        # Tab after line number (cat -n style)
        numbered.append(f"{num:>{width}}\t{line}")
    return "\n".join(numbered)


# ---------------------------------------------------------------------------
# FileReadTool
# ---------------------------------------------------------------------------

class FileReadTool:
    """
    Reads text files from the local filesystem.

    Only supports reading plain text files.
    """

    def __init__(self, max_size_bytes: int = MAX_SIZE_BYTES):
        self._max_size_bytes = max_size_bytes

    # -- Validation ----------------------------------------------------------

    def validate_input(
        self,
        file_path: str,
        offset: int = 1,
        limit: Optional[int] = None,
    ) -> None:
        """
        Validate input parameters before attempting to read.

        Raises FileReadError on invalid input.
        """
        # Path must be absolute
        if not file_path.startswith("/"):
            raise FileReadError(
                f"The file_path parameter must be an absolute path, not a relative path. "
                f"Received: '{file_path}'",
                error_code=1,
            )

        # Resolve symlinks / normalize
        resolved = str(Path(file_path).resolve())

        # Block device files
        if _is_blocked_device(resolved):
            raise BlockedDeviceError(file_path)

        # Binary extension check
        if _is_binary_extension(resolved):
            ext = Path(resolved).suffix.lower()
            raise BinaryFileError(file_path, ext)

        # Offset must be >= 1
        if offset < 1:
            raise FileReadError(
                f"Offset must be >= 1. Received: {offset}", error_code=7
            )

        # Limit must be > 0 if specified
        if limit is not None and limit < 1:
            raise FileReadError(
                f"Limit must be > 0. Received: {limit}", error_code=8
            )

    # -- Core read -----------------------------------------------------------

    async def call(
        self,
        file_path: str,
        offset: int = 1,
        limit: Optional[int] = None,
    ) -> FileReadResult:
        """
        Read a text file and return its content with line numbers.

        Args:
            file_path: Absolute path to the file.
            offset: 1-indexed line number to start from (default: 1).
            limit: Maximum number of lines to read (default: up to MAX_LINES_TO_READ).

        Returns:
            FileReadResult with content, line counts, and metadata.

        Raises:
            FileReadError: On validation failure, missing file, or read errors.
        """
        # Validate
        self.validate_input(file_path, offset, limit)
        resolved = str(Path(file_path).resolve())

        # Stat the file (checks existence, size, and gets mtime)
        try:
            file_stat = os.stat(resolved)
        except FileNotFoundError:
            raise FileNotFoundError_(file_path) from None
        except PermissionError:
            raise FileReadError(
                f"Permission denied: '{file_path}'", error_code=10
            ) from None
        except OSError as e:
            raise FileReadError(
                f"Cannot access '{file_path}': {e.strerror}", error_code=11
            ) from None

        # Re-check: stat may succeed on a device file not in our list
        if stat.S_ISCHR(file_stat.st_mode) or stat.S_ISBLK(file_stat.st_mode):
            raise BlockedDeviceError(file_path)

        # Size check (entire file, not the slice)
        if file_stat.st_size > self._max_size_bytes and limit is None:
            raise MaxSizeExceededError(file_path, file_stat.st_size, self._max_size_bytes)

        # Read the file
        try:
            with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
        except UnicodeDecodeError:
            raise BinaryFileError(file_path, Path(resolved).suffix) from None
        except OSError as e:
            raise FileReadError(
                f"Error reading '{file_path}': {e.strerror}", error_code=12
            ) from None

        total_lines = len(all_lines)

        # Empty file
        if total_lines == 0:
            raise FileEmptyError(file_path)

        # Slice by offset
        if offset > total_lines:
            raise OffsetBeyondFileError(file_path, offset, total_lines)

        start_idx = offset - 1  # convert 1-indexed to 0-indexed
        end_idx = min(total_lines, start_idx + (limit or MAX_LINES_TO_READ))

        sliced = all_lines[start_idx:end_idx]
        raw_content = "".join(sliced).rstrip("\n")

        # Line-numbered output
        content = _add_line_numbers(raw_content, start_line=offset)
        num_lines = len(sliced)

        return FileReadResult(
            file_path=file_path,
            content=content,
            num_lines=num_lines,
            start_line=offset,
            total_lines=total_lines,
        )

    # -- Synchronous convenience wrapper ------------------------------------

    def call_sync(
        self,
        file_path: str,
        offset: int = 1,
        limit: Optional[int] = None,
    ) -> FileReadResult:
        """Synchronous wrapper around call()."""
        import asyncio
        return asyncio.run(self.call(file_path, offset, limit))


# ---------------------------------------------------------------------------
# LangChain tool
# ---------------------------------------------------------------------------

_file_read_tool = FileReadTool()


@tool
async def read_file(file_path: str, offset: int = 1, limit: int = 1000) -> str:
    """Read a text file from the local filesystem and return its content with line numbers.

    Use this tool when you need to read, view, or inspect a file's content, or to
    understand existing code before making changes.

    Args:
        file_path: The path of the file to read, either relative to the project root or absolute.
        offset: The 1-based line number to start reading from.
        limit: The maximum number of lines to read.
    """
    if not file_path.strip():
        return "No file path provided."

    # The underlying FileReadTool requires absolute paths; resolve relative ones against the cwd.
    resolved = str(Path(file_path).resolve())
    try:
        result = await _file_read_tool.call(resolved, offset=offset, limit=limit)
    except FileReadError as e:
        return f"[{e.error_code}] {e}"

    return (
        f"{result.file_path} (lines {result.start_line}-"
        f"{result.start_line + result.num_lines - 1} of {result.total_lines}):\n"
        f"{result.content}"
    )


# ---------------------------------------------------------------------------
# Example / quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    tool = FileReadTool()
    path = sys.argv[1] if len(sys.argv) > 1 else __file__

    try:
        result = tool.call_sync(path)
        print(f"File: {result.file_path}")
        print(f"Lines: {result.start_line}-{result.start_line + result.num_lines - 1}"
              f" of {result.total_lines}")
        print("-" * 40)
        print(result.content)
    except FileReadError as e:
        print(f"Error [{e.error_code}]: {e}", file=sys.stderr)
        sys.exit(1)
