"""Built-in tools that agents can use out of the box."""

from __future__ import annotations

import json
import operator
from datetime import datetime
from typing import Any

from langchain_core.tools import tool


@tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression and return the result.

    Args:
        expression: A mathematical expression as a string (e.g. "2 + 3 * 4").

    Returns:
        The result of the evaluation as a string.
    """
    allowed_ops: dict[str, Any] = {
        "+": operator.add,
        "-": operator.sub,
        "*": operator.mul,
        "/": operator.truediv,
        "**": operator.pow,
        "//": operator.floordiv,
        "%": operator.mod,
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "pow": pow,
    }
    allowed_names = {**allowed_ops, "__builtins__": {}}
    try:
        result = eval(expression, allowed_names, {})
        return str(result)
    except Exception as e:
        return f"Error evaluating expression: {e}"


@tool
def current_time() -> str:
    """Get the current date and time in ISO 8601 format."""
    return datetime.now().isoformat()


@tool
def web_search(query: str) -> str:
    """Search the web for information (placeholder).

    Args:
        query: The search query string.

    Returns:
        Placeholder search results.
    """
    # TODO: Integrate with a real search API (Tavily, SerpAPI, etc.)
    return json.dumps({
        "query": query,
        "results": [],
        "note": "Web search not yet configured. Set SEARCH_API_KEY in .env.",
    })
