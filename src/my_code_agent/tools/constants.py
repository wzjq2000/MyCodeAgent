"""Shared tool constants (mirrors FileEditTool/constants.ts + prompt.ts tool names)."""

FILE_READ_TOOL_NAME = "Read"
FILE_WRITE_TOOL_NAME = "Write"
FILE_EDIT_TOOL_NAME = "Edit"

# Same error message as FileEditTool/constants.ts
FILE_UNEXPECTEDLY_MODIFIED_ERROR = (
    "File has been unexpectedly modified. Read it again before attempting to write it."
)

# V8/Bun string length limit rationale from FileEditTool.ts: 1 GiB is a safe
# byte-level guard against OOM on multi-GB files.
MAX_EDIT_FILE_SIZE = 1024 * 1024 * 1024  # 1 GiB (stat bytes)