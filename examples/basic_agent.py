"""Basic agent example demonstrating the framework usage."""

from __future__ import annotations

from my_code_agent.utils.config import load_config
from my_code_agent.utils.logging import setup_logging


def main() -> None:
    """Run a basic agent demonstration."""
    config = load_config()
    setup_logging(level=config.log_level)

    print(f"Agent Model: {config.agent_model}")
    print("MyCodeAgent framework initialized successfully!")
    print()
    print("Next steps:")
    print("  1. Set your API keys in .env")
    print("  2. Implement a concrete agent by subclassing BaseAgent")
    print("  3. Add custom tools in src/my_code_agent/tools/")


if __name__ == "__main__":
    main()
