"""
Python port of FileEditTool.ts — exact string replacement in files.

Mirrors the TS behavior:
- validateInput chain (same error codes and messages as FileEditTool.ts):
  old_string == new_string → size limit → missing file / create via empty
  old_string → .ipynb → read-before-write → modified-since-read → string not
  found → multiple matches without replace_all.
- Quote normalization (utils.ts): find_actual_string matches straight quotes
  against curly quotes in the file, and preserve_quote_style re-applies the
  file's curly style to new_string.
- call: re-checks staleness, applies the edit, preserves the original line
  endings on write, and updates the session read state.
- Result messages match mapToolResultToToolResultBlockParam in FileEditTool.ts.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel, Field

from .constants import (
    FILE_UNEXPECTEDLY_MODIFIED_ERROR,
    FILE_READ_TOOL_NAME,
    MAX_EDIT_FILE_SIZE,
)

if TYPE_CHECKING:
    from my_code_agent.state import FileReadState

EDIT_DESCRIPTION = (
    "Performs exact string replacements in files.\n\n"
    f"Usage:\n- You must use your {FILE_READ_TOOL_NAME} tool at least once in the "
    "conversation before editing. This tool will error if you attempt an edit without "
    "reading the file. \n"
    "- When editing text from Read tool output, ensure you preserve the exact "
    "indentation (tabs/spaces) as it appears AFTER the line number prefix. The line "
    "number prefix format is: line number + tab. Everything after that is the actual "
    "file content to match. Never include any part of the line number prefix in the "
    "old_string or new_string.\n"
    "- ALWAYS prefer editing existing files in the codebase. NEVER write new files "
    "unless explicitly required.\n"
    "- Only use emojis if the user explicitly requests it. Avoid adding emojis to "
    "files unless asked.\n"
    "- The edit will FAIL if `old_string` is not unique in the file. Either provide a "
    "larger string with more surrounding context to make it unique or use `replace_all` "
    "to change every instance of `old_string`.\n"
    "- Use `replace_all` for replacing and renaming strings across the file. This "
    "parameter is useful if you want to rename a variable for instance."
)


class FileEditInput(BaseModel):
    """Input schema for the Edit tool (mirrors FileEditTool types.ts inputSchema)."""

    file_path: str = Field(
        description="The absolute path to the file to modify (must be absolute, not "
        "relative)"
    )
    old_string: str = Field(description="The text to replace")
    new_string: str = Field(description="The text to replace it with")
    replace_all: bool = Field(
        default=False,
        description="Replace all occurrences of old_string instead of just the first. "
        "Set when there are multiple matches that should all be updated.",
    )


# ---------------------------------------------------------------------------
# Errors (mirrors validateInput error codes/messages in FileEditTool.ts)
# ---------------------------------------------------------------------------


class FileEditError(Exception):
    """Base error for FileEditTool."""

    def __init__(self, message: str, error_code: int = 0):
        super().__init__(message)
        self.error_code = error_code


class NoChangesError(FileEditError):
    """old_string and new_string are identical (errorCode 1)."""

    def __init__(self):
        super().__init__(
            "No changes to make: old_string and new_string are exactly the same.",
            error_code=1,
        )


class FileExistsForCreateError(FileEditError):
    """Empty old_string on a non-empty file (errorCode 3)."""

    def __init__(self):
        super().__init__("Cannot create new file - file already exists.", error_code=3)


class FileDoesNotExistError(FileEditError):
    """File missing and old_string non-empty (errorCode 4)."""

    def __init__(self, file_path: str):
        cwd = os.getcwd()
        super().__init__(
            f"File does not exist. The current working directory is {cwd}.",
            error_code=4,
        )


class NotebookError(FileEditError):
    """File is a Jupyter notebook (errorCode 5)."""

    def __init__(self, file_path: str):
        super().__init__(
            f"File is a Jupyter Notebook. Editing notebooks is not supported in this "
            f"Python port: {file_path}",
            error_code=5,
        )


class NotReadYetError(FileEditError):
    """File has not been read in this session (errorCode 6)."""

    def __init__(self):
        super().__init__(
            "File has not been read yet. Read it first before writing to it.",
            error_code=6,
        )


class ModifiedSinceReadError(FileEditError):
    """File was modified after the last read (errorCode 7)."""

    def __init__(self):
        super().__init__(
            "File has been modified since read, either by the user or by a linter. Read "
            "it again before attempting to write it.",
            error_code=7,
        )


class StringNotFoundError(FileEditError):
    """old_string not found in file (errorCode 8)."""

    def __init__(self, old_string: str):
        super().__init__(
            f"String to replace not found in file.\nString: {old_string}",
            error_code=8,
        )


class MultipleMatchesError(FileEditError):
    """Multiple matches but replace_all is false (errorCode 9)."""

    def __init__(self, count: int, old_string: str):
        super().__init__(
            f"Found {count} matches of the string to replace, but replace_all is false. "
            "To replace all occurrences, set replace_all to true. To replace only one "
            "occurrence, please provide more context to uniquely identify the "
            f"instance.\nString: {old_string}",
            error_code=9,
        )


class FileTooLargeError(FileEditError):
    """File exceeds MAX_EDIT_FILE_SIZE (errorCode 10)."""

    def __init__(self, file_path: str, size_bytes: int):
        super().__init__(
            f"File is too large to edit ({size_bytes} bytes). Maximum editable file "
            f"size is {MAX_EDIT_FILE_SIZE} bytes.",
            error_code=10,
        )


# ---------------------------------------------------------------------------
# Quote normalization (ports of FileEditTool/utils.ts)
# ---------------------------------------------------------------------------

LEFT_SINGLE_CURLY_QUOTE = "‘"  # ‘
RIGHT_SINGLE_CURLY_QUOTE = "’"  # ’
LEFT_DOUBLE_CURLY_QUOTE = "“"  # “
RIGHT_DOUBLE_CURLY_QUOTE = "”"  # ”


def normalize_quotes(text: str) -> str:
    """Normalizes curly quotes to straight quotes (utils.ts normalizeQuotes)."""
    return (
        text.replace(LEFT_SINGLE_CURLY_QUOTE, "'")
        .replace(RIGHT_SINGLE_CURLY_QUOTE, "'")
        .replace(LEFT_DOUBLE_CURLY_QUOTE, '"')
        .replace(RIGHT_DOUBLE_CURLY_QUOTE, '"')
    )


def find_actual_string(file_content: str, search_string: str) -> Optional[str]:
    """
    Finds the actual string in the file that matches search_string, accounting
    for quote normalization. Returns None if not found (utils.ts findActualString).
    """
    # First try exact match
    if search_string in file_content:
        return search_string

    # Try with normalized quotes
    normalized_search = normalize_quotes(search_string)
    normalized_file = normalize_quotes(file_content)
    search_index = normalized_file.find(normalized_search)
    if search_index != -1:
        # Find the actual string in the file that matches
        return file_content[search_index : search_index + len(search_string)]

    return None


def _is_opening_context(chars: str, index: int) -> bool:
    """Open/close heuristic from utils.ts isOpeningContext."""
    if index == 0:
        return True
    prev = chars[index - 1]
    return prev in " \t\n\r([{—–"  # includes em dash and en dash


def _apply_curly_double_quotes(text: str) -> str:
    chars = list(text)
    for i, ch in enumerate(chars):
        if ch == '"':
            chars[i] = (
                LEFT_DOUBLE_CURLY_QUOTE
                if _is_opening_context(text, i)
                else RIGHT_DOUBLE_CURLY_QUOTE
            )
    return "".join(chars)


def _apply_curly_single_quotes(text: str) -> str:
    chars = list(text)
    for i, ch in enumerate(chars):
        if ch == "'":
            prev = chars[i - 1] if i > 0 else ""
            next_ch = chars[i + 1] if i < len(chars) - 1 else ""
            prev_is_letter = bool(prev) and prev.isalpha()
            next_is_letter = bool(next_ch) and next_ch.isalpha()
            if prev_is_letter and next_is_letter:
                # Apostrophe in a contraction — use right single curly quote
                chars[i] = RIGHT_SINGLE_CURLY_QUOTE
            else:
                chars[i] = (
                    LEFT_SINGLE_CURLY_QUOTE
                    if _is_opening_context(text, i)
                    else RIGHT_SINGLE_CURLY_QUOTE
                )
    return "".join(chars)


def preserve_quote_style(old_string: str, actual_old_string: str, new_string: str) -> str:
    """
    When old_string matched via quote normalization (curly quotes in file,
    straight quotes from model), apply the same curly quote style to new_string
    so the edit preserves the file's typography (utils.ts preserveQuoteStyle).
    """
    # If they're the same, no normalization happened
    if old_string == actual_old_string:
        return new_string

    has_double_quotes = (
        LEFT_DOUBLE_CURLY_QUOTE in actual_old_string
        or RIGHT_DOUBLE_CURLY_QUOTE in actual_old_string
    )
    has_single_quotes = (
        LEFT_SINGLE_CURLY_QUOTE in actual_old_string
        or RIGHT_SINGLE_CURLY_QUOTE in actual_old_string
    )
    if not has_double_quotes and not has_single_quotes:
        return new_string

    result = new_string
    if has_double_quotes:
        result = _apply_curly_double_quotes(result)
    if has_single_quotes:
        result = _apply_curly_single_quotes(result)
    return result


def apply_edit_to_file(
    original_content: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> str:
    """
    Applies an edit and returns the updated content (utils.ts applyEditToFile).
    When new_string is empty and old_string is not at the end of a line, the
    trailing newline is stripped along with it.
    """
    count = -1 if replace_all else 1  # Python replace: -1 replaces all occurrences

    if new_string != "":
        return original_content.replace(old_string, new_string, count)

    strip_trailing_newline = (
        not old_string.endswith("\n") and old_string + "\n" in original_content
    )
    if strip_trailing_newline:
        return original_content.replace(old_string + "\n", new_string, count)
    return original_content.replace(old_string, new_string, count)


# ---------------------------------------------------------------------------
# FileEditTool
# ---------------------------------------------------------------------------


class FileEditTool:
    """Modifies file contents in place via exact string replacement."""

    def __init__(self, read_state: Optional["FileReadState"] = None):
        self._read_state = read_state

    # -- Validation ----------------------------------------------------------

    def validate_input(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        """
        Validate the edit before applying it. Returns the resolved absolute path.

        Raises FileEditError with the same codes/messages as FileEditTool.ts.
        """
        full_path = str(Path(file_path).resolve())

        if old_string == new_string:
            raise NoChangesError()

        # Prevent OOM on multi-GB files
        try:
            size = os.path.getsize(full_path)
            if size > MAX_EDIT_FILE_SIZE:
                raise FileTooLargeError(file_path, size)
        except FileNotFoundError:
            pass

        # Read the file (normalize CRLF so matches work against LF, as TS does)
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                file_content = f.read().replace("\r\n", "\n")
        except FileNotFoundError:
            file_content = None

        # File doesn't exist
        if file_content is None:
            # Empty old_string on nonexistent file means new file creation — valid
            if old_string == "":
                return full_path
            raise FileDoesNotExistError(file_path)

        # File exists with empty old_string — only valid if file is empty
        if old_string == "":
            if file_content.strip() != "":
                raise FileExistsForCreateError()
            # Empty file with empty old_string is valid - replacing empty with content
            return full_path

        if full_path.endswith(".ipynb"):
            raise NotebookError(file_path)

        # Read-before-write enforcement
        record = self._read_state.get(full_path) if self._read_state else None
        if record is None or record.is_partial_view:
            raise NotReadYetError()

        # Modified-since-read check. TS has a content-comparison fallback for
        # Windows cloud-sync false positives; skipped here (Linux/macOS timestamps).
        if os.path.getmtime(full_path) > record.timestamp:
            raise ModifiedSinceReadError()

        # Use find_actual_string to handle quote normalization
        actual_old_string = find_actual_string(file_content, old_string)
        if actual_old_string is None:
            raise StringNotFoundError(old_string)

        matches = file_content.count(actual_old_string)
        if matches > 1 and not replace_all:
            raise MultipleMatchesError(matches, old_string)

        return full_path

    # -- Core edit -----------------------------------------------------------

    async def call(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        """
        Apply the edit and return the claude-code result message:
        - "The file <path> has been updated successfully."
        - "... All occurrences were successfully replaced." when replace_all.
        """
        full_path = self.validate_input(file_path, old_string, new_string, replace_all)

        # 1. Load current state and confirm no changes since last read.
        # No async work between here and the write, to preserve atomicity.
        # newline="" keeps line endings intact so CRLF files can be detected
        # and preserved on write (mirrors TS readFileSyncWithMetadata endings).
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace", newline="") as f:
                raw_content = f.read()
            line_endings = "CRLF" if "\r\n" in raw_content else "LF"
            original_file_contents = raw_content.replace("\r\n", "\n")
        except FileNotFoundError:
            line_endings = "LF"
            original_file_contents = ""

        file_exists = os.path.exists(full_path)
        if file_exists:
            record = self._read_state.get(full_path) if self._read_state else None
            if record is None or os.path.getmtime(full_path) > record.timestamp:
                raise FileEditError(FILE_UNEXPECTEDLY_MODIFIED_ERROR, error_code=7)

        # 2. Use find_actual_string to handle quote normalization
        actual_old_string = find_actual_string(original_file_contents, old_string) or old_string

        # Preserve curly quotes in new_string when the file uses them
        actual_new_string = preserve_quote_style(old_string, actual_old_string, new_string)

        # 3. Apply the edit
        updated_file = apply_edit_to_file(
            original_file_contents, actual_old_string, actual_new_string, replace_all
        )

        # 4. Write to disk, preserving the original line endings
        if line_endings == "CRLF":
            updated_file = updated_file.replace("\n", "\r\n")
        with open(full_path, "w", encoding="utf-8", newline="") as f:
            f.write(updated_file)

        # 5. Update read timestamp, to invalidate stale writes
        if self._read_state is not None:
            self._read_state.record(full_path, updated_file)

        if replace_all:
            return (
                f"The file {file_path} has been updated. All occurrences were "
                "successfully replaced."
            )
        return f"The file {file_path} has been updated successfully."