"""
CLI entry point.

Usage:
    my-agent "把 foo.py 里的 bug 修掉"     # single prompt
    my-agent                              # interactive REPL
    my-agent --max-turns 40 "..."         # override the turn limit
    my-agent --model claude-opus-5 "..."  # override the model
"""

import asyncio
from pathlib import Path
from typing import Annotated, Any, Optional

import typer
from dotenv import load_dotenv
from langchain_core.messages import AIMessageChunk, AnyMessage, HumanMessage
from rich.console import Console

from my_code_agent.agent import build_agent
from my_code_agent.settings import Settings

app = typer.Typer(add_completion=False, help="claude-code 风格的 coding agent(Read/Write/Edit)。")
console = Console()


async def _run_turn(graph: Any, messages: list[AnyMessage], max_turns: int) -> list[AnyMessage]:
    """Run one turn, streaming tokens and tool calls to the console.

    Mirrors the query.ts yield-based event stream: token chunks go straight
    to the UI, and the final state's messages become the next turn's history.
    Returns the full message history including this turn.
    """
    final_messages = messages
    input_state = {
        "messages": messages,
        "turn_count": 0,
        "max_turns": max_turns,
    }
    async for mode, chunk in graph.astream(input_state, stream_mode=["messages", "values"]):
        if mode == "messages":
            message, _metadata = chunk
            if isinstance(message, AIMessageChunk):
                for tool_chunk in message.tool_call_chunks or []:
                    name = tool_chunk.get("name")
                    if name:
                        console.print(f"  [cyan]▸ {name}[/cyan]")
                if message.content:
                    console.print(message.content, end="", markup=False, highlight=False)
        else:  # mode == "values" — full state after each super-step
            final_messages = chunk["messages"]
    console.print()
    return final_messages


async def _run(prompt: Optional[str], max_turns: Optional[int], model: Optional[str]) -> None:
    overrides: dict[str, Any] = {}
    if model is not None:
        overrides["agent_model"] = model
    if max_turns is not None:
        overrides["max_turns"] = max_turns
    settings = Settings(**overrides)

    graph = build_agent(settings)
    console.print(
        f"[dim]模型: {settings.agent_model} | 工作目录: {Path.cwd()} | "
        f"max_turns: {settings.max_turns}[/dim]"
    )

    if prompt is not None:
        try:
            await _run_turn(graph, [HumanMessage(prompt)], settings.max_turns)
        except Exception as e:  # noqa: BLE001 — CLI boundary, show and exit
            console.print(f"[red]错误: {e}[/red]")
            raise typer.Exit(code=1)
        return

    # Interactive REPL: keep the conversation in memory across turns
    messages: list[AnyMessage] = []
    console.print("[dim]交互模式 — 输入 exit 退出[/dim]")
    while True:
        try:
            text = console.input("[bold green]> [/bold green]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n再见!")
            return
        if text.lower() in ("exit", "quit", "/exit"):
            return
        if not text:
            continue
        try:
            messages = await _run_turn(graph, messages + [HumanMessage(text)], settings.max_turns)
        except Exception as e:  # noqa: BLE001 — keep the REPL alive on errors
            console.print(f"[red]错误: {e}[/red]")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: Annotated[Optional[str], typer.Argument()] = None,
    max_turns: Annotated[
        Optional[int],
        typer.Option("--max-turns", "-n", help="单轮最多循环次数(默认读 MAX_TURNS 环境变量, 30)"),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="Claude 模型 ID(默认读 AGENT_MODEL 环境变量, claude-opus-5)"),
    ] = None,
) -> None:
    """claude-code 风格的 coding agent,带 Read / Write / Edit 三个文件工具。"""
    if ctx.invoked_subcommand is not None:
        return
    load_dotenv()  # put .env into os.environ so langchain-anthropic picks up the key
    asyncio.run(_run(prompt, max_turns, model))


if __name__ == "__main__":
    app()