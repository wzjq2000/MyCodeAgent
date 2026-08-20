"""CLI entry point for MyCodeAgent."""

from __future__ import annotations

from langgraph.graph import StateGraph
from my_code_agent.agent.agent_state import CodeAgentState

if __name__ == "__main__":
    workflow = StateGraph(CodeAgentState)
    workflow.add_node()


