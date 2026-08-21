"""
Tool behavior tests.

Covers the behaviors ported from claude-code: read-before-write enforcement,
modified-since-read detection, Edit matching rules (uniqueness, replace_all,
create via empty old_string), curly-quote normalization, and line-ending
preservation.
"""

import os

import pytest

from my_code_agent.state import FileReadState
from my_code_agent.tools import file_edit_tool, file_read_tool, file_write_tool


@pytest.fixture
def read_state() -> FileReadState:
    return FileReadState()


def _write(path, content: str, *, mtime_delta: float | None = None) -> None:
    """Write content and optionally bump mtime forward (simulates external edit)."""
    path.write_text(content)
    if mtime_delta is not None:
        st = os.stat(path)
        os.utime(path, (st.st_atime + mtime_delta, st.st_mtime + mtime_delta))


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


async def test_read_numbers_lines(tmp_path, read_state):
    p = tmp_path / "a.txt"
    _write(p, "a\nb\nc\n")
    tool = file_read_tool.FileReadTool(read_state=read_state)
    result = await tool.call(str(p))
    assert result.content == "1\ta\n2\tb\n3\tc"
    assert (result.start_line, result.total_lines) == (1, 3)


async def test_read_requires_absolute_path(tmp_path, read_state):
    tool = file_read_tool.FileReadTool(read_state=read_state)
    with pytest.raises(file_read_tool.FileReadError):
        await tool.call("relative/path.txt")


async def test_read_offset_and_limit(tmp_path, read_state):
    p = tmp_path / "a.txt"
    _write(p, "a\nb\nc\n")
    tool = file_read_tool.FileReadTool(read_state=read_state)
    result = await tool.call(str(p), offset=2, limit=1)
    assert result.content == "2\tb"


async def test_read_records_full_vs_partial(tmp_path):
    p = tmp_path / "a.txt"
    _write(p, "a\nb\nc\n")

    full_state = FileReadState()
    await file_read_tool.FileReadTool(read_state=full_state).call(str(p))
    assert full_state.get(str(p)).is_partial_view is False

    partial_state = FileReadState()
    await file_read_tool.FileReadTool(read_state=partial_state).call(str(p), offset=1, limit=2)
    assert partial_state.get(str(p)).is_partial_view is True


async def test_read_empty_file_records_state(tmp_path, read_state):
    p = tmp_path / "empty.txt"
    _write(p, "")
    tool = file_read_tool.FileReadTool(read_state=read_state)
    with pytest.raises(file_read_tool.FileEmptyError):
        await tool.call(str(p))
    # TS records the read before surfacing the system reminder, so Edit can
    # later fill the empty file.
    assert read_state.get(str(p)) is not None


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


async def test_write_create(tmp_path, read_state):
    p = tmp_path / "new.txt"
    tool = file_write_tool.FileWriteTool(read_state=read_state)
    result = await tool.call(str(p), "hello\nworld\n")
    assert result == f"File created successfully at: {p}"
    assert p.read_text() == "hello\nworld\n"


async def test_write_update_after_read(tmp_path, read_state):
    p = tmp_path / "a.txt"
    _write(p, "old\n")
    read = file_read_tool.FileReadTool(read_state=read_state)
    await read.call(str(p))

    tool = file_write_tool.FileWriteTool(read_state=read_state)
    result = await tool.call(str(p), "new\n")
    assert result == f"The file {p} has been updated successfully."
    assert p.read_text() == "new\n"


async def test_write_requires_read(tmp_path, read_state):
    p = tmp_path / "a.txt"
    _write(p, "content\n")
    tool = file_write_tool.FileWriteTool(read_state=read_state)
    with pytest.raises(file_write_tool.NotReadYetError):
        await tool.call(str(p), "overwrite\n")


async def test_write_requires_full_read(tmp_path, read_state):
    p = tmp_path / "a.txt"
    _write(p, "a\nb\nc\n")
    read = file_read_tool.FileReadTool(read_state=read_state)
    await read.call(str(p), limit=1)  # partial view

    tool = file_write_tool.FileWriteTool(read_state=read_state)
    with pytest.raises(file_write_tool.NotReadYetError):
        await tool.call(str(p), "overwrite\n")


async def test_write_rejects_modified_since_read(tmp_path, read_state):
    p = tmp_path / "a.txt"
    _write(p, "old\n")
    read = file_read_tool.FileReadTool(read_state=read_state)
    await read.call(str(p))

    _write(p, "changed externally\n", mtime_delta=10)
    tool = file_write_tool.FileWriteTool(read_state=read_state)
    with pytest.raises(file_write_tool.ModifiedSinceReadError):
        await tool.call(str(p), "overwrite\n")


# ---------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------


async def _read(tmp_path, read_state, name, content):
    p = tmp_path / name
    _write(p, content)
    await file_read_tool.FileReadTool(read_state=read_state).call(str(p))
    return p


async def test_edit_basic(tmp_path, read_state):
    p = await _read(tmp_path, read_state, "a.txt", "a\nb\nc\n")
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    result = await tool.call(str(p), "b", "B")
    assert result == f"The file {p} has been updated successfully."
    assert p.read_text() == "a\nB\nc\n"


async def test_edit_replace_all(tmp_path, read_state):
    p = await _read(tmp_path, read_state, "a.txt", "x x x\n")
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    result = await tool.call(str(p), "x", "y", replace_all=True)
    assert "All occurrences were successfully replaced" in result
    assert p.read_text() == "y y y\n"


async def test_edit_multiple_matches_requires_replace_all(tmp_path, read_state):
    p = await _read(tmp_path, read_state, "a.txt", "x x\n")
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    with pytest.raises(file_edit_tool.MultipleMatchesError) as exc:
        await tool.call(str(p), "x", "y")
    assert "Found 2 matches" in str(exc.value)


async def test_edit_string_not_found(tmp_path, read_state):
    p = await _read(tmp_path, read_state, "a.txt", "hello\n")
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    with pytest.raises(file_edit_tool.StringNotFoundError):
        await tool.call(str(p), "nope", "y")


async def test_edit_old_equals_new(tmp_path, read_state):
    p = await _read(tmp_path, read_state, "a.txt", "hello\n")
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    with pytest.raises(file_edit_tool.NoChangesError):
        await tool.call(str(p), "hello", "hello")


async def test_edit_requires_read(tmp_path, read_state):
    p = tmp_path / "a.txt"
    _write(p, "hello\n")
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    with pytest.raises(file_edit_tool.NotReadYetError):
        await tool.call(str(p), "hello", "bye")


async def test_edit_create_via_empty_old_string(tmp_path, read_state):
    p = tmp_path / "new.txt"
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    result = await tool.call(str(p), "", "content\n")
    assert "updated successfully" in result
    assert p.read_text() == "content\n"


async def test_edit_empty_old_string_on_existing_file(tmp_path, read_state):
    p = await _read(tmp_path, read_state, "a.txt", "content\n")
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    with pytest.raises(file_edit_tool.FileExistsForCreateError):
        await tool.call(str(p), "", "x")


async def test_edit_fills_empty_file(tmp_path, read_state):
    p = tmp_path / "empty.txt"
    _write(p, "")
    with pytest.raises(file_read_tool.FileEmptyError):
        await file_read_tool.FileReadTool(read_state=read_state).call(str(p))

    tool = file_edit_tool.FileEditTool(read_state=read_state)
    await tool.call(str(p), "", "filled\n")
    assert p.read_text() == "filled\n"


async def test_edit_file_missing_nonempty_old_string(tmp_path, read_state):
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    with pytest.raises(file_edit_tool.FileDoesNotExistError):
        await tool.call(str(tmp_path / "nope.txt"), "x", "y")


async def test_edit_rejects_modified_since_read(tmp_path, read_state):
    p = await _read(tmp_path, read_state, "a.txt", "hello\n")
    _write(p, "changed\n", mtime_delta=10)
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    with pytest.raises(file_edit_tool.ModifiedSinceReadError):
        await tool.call(str(p), "changed", "x")


async def test_edit_curly_quote_normalization(tmp_path, read_state):
    # File uses curly quotes; the model sends straight quotes. findActualString
    # must match, and preserveQuoteStyle must keep the file's curly style.
    p = await _read(tmp_path, read_state, "a.txt", "“hello” world\n")
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    await tool.call(str(p), '"hello"', '"goodbye"')
    assert p.read_text() == "“goodbye” world\n"


async def test_edit_empty_new_string_strips_trailing_newline(tmp_path, read_state):
    p = await _read(tmp_path, read_state, "a.txt", "foo()\nbar\n")
    tool = file_edit_tool.FileEditTool(read_state=read_state)
    await tool.call(str(p), "foo()", "")
    assert p.read_text() == "bar\n"


async def test_edit_preserves_crlf(tmp_path, read_state):
    p = tmp_path / "a.txt"
    _write(p, "a\r\nb\r\nc\r\n")
    await file_read_tool.FileReadTool(read_state=read_state).call(str(p))

    tool = file_edit_tool.FileEditTool(read_state=read_state)
    await tool.call(str(p), "b", "B")
    assert p.read_text() == "a\r\nB\r\nc\r\n"