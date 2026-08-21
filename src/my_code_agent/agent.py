"""
The agent graph — the LangGraph equivalent of claude-code's query loop
(src/query.ts).

query.ts's while(true) loop with its continue sites collapses to a single
graph cycle here: agent -> (tools -> agent)* -> END. The mapping:

- next_turn                -> the tools -> agent cycle edge
- maxTurns / 终止路径       -> route_after_agent returning END
- 工具校验错误              -> ToolNode(handle_tool_errors=True), errors go back
  to the model as ToolMessages so it can self-correct
- readFileState            -> one FileReadState shared by all three tools
"""

from pathlib import Path
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import CompiledStateGraph, END, START, StateGraph
from langgraph.prebuilt import ToolNode

from my_code_agent.prompts import build_system_prompt
from my_code_agent.settings import Settings
from my_code_agent.state import AgentState, FileReadState
from my_code_agent.tools import build_tools


def build_agent(settings: Settings, model: BaseChatModel | None = None) -> CompiledStateGraph:
    """Build the agent graph.

    Args:
        settings: Model and turn-limit settings.
        model: Injectable chat model (for tests); defaults to
            ChatAnthropic(settings.agent_model).
    """
    read_state = FileReadState()
    tools = build_tools(read_state)

    if model is None:
        model = ChatAnthropic(
            model=settings.agent_model,
            max_tokens=64000,
        )
    model_with_tools = model.bind_tools(tools)

    # Stable prefix (frozen at build time) — good for prompt caching
    system_prompt = build_system_prompt(Path.cwd())

    def agent_node(state: AgentState) -> dict:
        """Call the model with the system prompt + history + bound tools."""
        response = model_with_tools.invoke(
            [SystemMessage(system_prompt), *state["messages"]]
        )
        return {
            "messages": [response],
            "turn_count": state.get("turn_count", 0) + 1,
        }

    def route_after_agent(state: AgentState) -> Literal["tools", END]:
        """query.ts 的循环判定: 有 tool_use 继续, 否则结束; maxTurns 终止."""
        if state.get("turn_count", 0) >= state.get("max_turns", settings.max_turns):
            return END
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    builder = StateGraph(AgentState)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route_after_agent, ["tools", END])
    builder.add_edge("tools", "agent")
    return builder.compile()