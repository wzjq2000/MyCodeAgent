"""Graph smoke tests — compile the graph without making API calls."""

from langchain_anthropic import ChatAnthropic

from my_code_agent.agent import build_agent
from my_code_agent.settings import Settings


def test_graph_compiles():
    settings = Settings(_env_file=None)  # bypass .env so the test is hermetic
    model = ChatAnthropic(
        model="claude-opus-5",
        anthropic_api_key="test-key",
        max_tokens=1024,
    )
    graph = build_agent(settings, model=model)

    nodes = set(graph.get_graph().nodes)
    assert {"agent", "tools"} <= nodes