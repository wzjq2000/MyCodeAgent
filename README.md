# MyCodeAgent

A Python agent framework for building intelligent agents.

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run the example
python examples/basic_agent.py

# Run via CLI
my-agent run --prompt "Hello, world!"
```

## Project Structure

```
MyCodeAgent/
├── src/my_code_agent/   # Main package
│   ├── agent/           # Agent core (base classes, orchestration)
│   ├── models/          # Pydantic data models
│   ├── tools/           # Tool definitions
│   ├── utils/           # Configuration, logging, helpers
│   └── __main__.py      # CLI entry point
├── examples/            # Usage examples
├── tests/               # Unit and integration tests
├── configs/             # YAML/JSON config files
└── scripts/             # Utility scripts
```

## Development

```bash
# Run tests
pytest

# Lint
ruff check src/

# Type check
mypy src/
```
