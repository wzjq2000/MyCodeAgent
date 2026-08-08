"""CLI entry point for MyCodeAgent."""

from __future__ import annotations

import typer
from rich.console import Console

from my_code_agent.utils.config import load_config
from my_code_agent.utils.logging import setup_logging

app = typer.Typer(help="MyCodeAgent - Build and run intelligent agents")
console = Console()


@app.command()
def run(
    prompt: str = typer.Option(..., "--prompt", "-p", help="Prompt to send to the agent"),
    model: str = typer.Option("gpt-4o", "--model", "-m", help="Model to use"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """Run the agent with a given prompt."""
    config = load_config()
    setup_logging(level="DEBUG" if verbose else config.log_level)

    console.print(f"[bold green]Running agent with model: {model}[/bold green]")
    console.print(f"[bold]Prompt:[/bold] {prompt}")

    # TODO: Wire up actual agent execution
    console.print("[yellow]Agent execution not yet implemented.[/yellow]")


@app.command()
def version() -> None:
    """Print the version."""
    from my_code_agent import __version__

    console.print(f"MyCodeAgent v{__version__}")


if __name__ == "__main__":
    app()
