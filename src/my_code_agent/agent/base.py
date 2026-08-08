"""Base agent class that all agents should inherit from."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for an agent."""

    name: str = Field(default="agent", description="Agent name")
    model: str = Field(default="gpt-4o", description="Model identifier")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_iterations: int = Field(default=10, ge=1)
    verbose: bool = Field(default=False)


class AgentState(BaseModel):
    """State tracked during agent execution."""

    messages: list[Any] = Field(default_factory=list)
    iteration: int = Field(default=0)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class BaseAgent(ABC):
    """Abstract base class for all agents.

    Provides the common interface and lifecycle hooks:
        1. on_start()   - Called before the agent loop begins
        2. on_step()    - Called on each iteration
        3. on_finish()  - Called when the agent loop ends
        4. on_error()   - Called when an error occurs
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        tools: list[BaseTool] | None = None,
    ) -> None:
        self.config = config or AgentConfig()
        self.tools = tools or []
        self.state = AgentState()
        self._llm: BaseChatModel | None = None

    @property
    def llm(self) -> BaseChatModel:
        """Lazy-load the LLM. Override _build_llm to customise."""
        if self._llm is None:
            self._llm = self._build_llm()
        return self._llm

    @abstractmethod
    def _build_llm(self) -> BaseChatModel:
        """Build and return the chat model. Subclasses must implement."""
        ...

    async def run(self, prompt: str, **kwargs: Any) -> str:
        """Run the agent with a prompt. Returns the final response."""
        logger.info(f"Agent [{self.config.name}] starting with prompt: {prompt[:100]}...")
        await self.on_start(prompt, **kwargs)

        try:
            while self.state.iteration < self.config.max_iterations:
                await self.on_step(**kwargs)
                self.state.iteration += 1
        except Exception as e:
            await self.on_error(e)
            raise
        finally:
            await self.on_finish()

        return "Agent execution complete."  # Override in subclasses

    async def on_start(self, prompt: str, **kwargs: Any) -> None:
        """Hook called before the agent loop begins."""
        self.state = AgentState()
        self.state.messages.append({"role": "user", "content": prompt})

    async def on_step(self, **kwargs: Any) -> None:
        """Hook called on each iteration of the agent loop."""

    async def on_finish(self) -> None:
        """Hook called when the agent loop finishes."""
        logger.info(f"Agent [{self.config.name}] finished after {self.state.iteration} steps.")

    async def on_error(self, error: Exception) -> None:
        """Hook called when an error occurs."""
        logger.error(f"Agent [{self.config.name}] error: {error}")
