"""Tests for the BaseAgent class."""

from __future__ import annotations

import pytest
from langchain_core.language_models import BaseChatModel

from my_code_agent.agent.base import AgentConfig, AgentState, BaseAgent


class FakeLLM(BaseChatModel):
    """A fake LLM for testing purposes."""

    model_name: str = "fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    def _llm_type(self) -> str:
        return "fake"


class TestAgent(BaseAgent):
    """Concrete agent implementation for testing."""

    def _build_llm(self) -> BaseChatModel:
        return FakeLLM()


class TestAgentConfig:
    def test_default_config(self) -> None:
        config = AgentConfig()
        assert config.name == "agent"
        assert config.model == "gpt-4o"
        assert config.temperature == 0.0
        assert config.max_iterations == 10

    def test_custom_config(self) -> None:
        config = AgentConfig(name="test", max_iterations=5)
        assert config.name == "test"
        assert config.max_iterations == 5


class TestAgentState:
    def test_initial_state(self) -> None:
        state = AgentState()
        assert state.messages == []
        assert state.iteration == 0
        assert state.tool_calls == []


class TestBaseAgent:
    @pytest.mark.asyncio
    async def test_agent_initialization(self) -> None:
        agent = TestAgent(config=AgentConfig(name="test"))
        assert agent.config.name == "test"
        assert agent.tools == []

    @pytest.mark.asyncio
    async def test_agent_run_lifecycle(self) -> None:
        agent = TestAgent(config=AgentConfig(name="test", max_iterations=3))
        result = await agent.run("Hello!")
        assert agent.state.iteration == 3
        assert "complete" in result.lower()


class TestAgentSubclass:
    """Ensure BaseAgent cannot be instantiated directly."""

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore[abstract]
