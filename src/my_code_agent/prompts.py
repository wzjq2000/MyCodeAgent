"""
System prompt assembly — mirrors how claude-code composes its system prompt:
a fixed instruction block plus memory files (project CLAUDE.md and the
user-level ~/.claude/CLAUDE.md).
"""

from pathlib import Path

_SYSTEM_PROMPT_TEMPLATE = """\
You are a coding agent that helps the user with software engineering tasks in the \
working directory {cwd}.

You have three tools: Read, Write and Edit. Follow these rules when using them:
- Always pass absolute paths, never relative paths.
- You MUST Read a file before Writing or Editing it — the tools enforce this and \
will return an error otherwise.
- Prefer Edit over Write for modifying existing files: Edit applies a minimal \
diff, while Write replaces the whole file. Only use Write for new files or \
complete rewrites.
- Make the smallest change that accomplishes the task. Match the surrounding \
code's style, naming, and idioms.
- Never create documentation files (*.md) or README files unless the user \
explicitly asks.
- Only use emojis if the user explicitly requests it.
- If a tool returns an error, read the message, fix the problem (often by \
re-reading the file or adjusting old_string), and try again."""


def _read_memory_file(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8") if path.exists() else None
    except OSError:
        return None


def build_system_prompt(cwd: Path) -> str:
    """Assemble the system prompt: instructions + memory files if present."""
    sections = [_SYSTEM_PROMPT_TEMPLATE.format(cwd=cwd)]

    project_memory = _read_memory_file(cwd / "CLAUDE.md")
    if project_memory:
        sections.append(
            f"<project-context>\nContents of {cwd / 'CLAUDE.md'} — follow these "
            f"project instructions:\n\n{project_memory}\n</project-context>"
        )

    user_memory = _read_memory_file(Path.home() / ".claude" / "CLAUDE.md")
    if user_memory:
        sections.append(
            "<user-memory>\nThe user's global preferences ("
            f"{Path.home() / '.claude' / 'CLAUDE.md'}):\n\n{user_memory}\n</user-memory>"
        )

    return "\n\n".join(sections)