"""Base classes for agents in the Redline AI system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, TypeVar
from pydantic import BaseModel

TInput = TypeVar('TInput', bound=BaseModel)
TOutput = TypeVar('TOutput', bound=BaseModel)


class BaseAgent(ABC):
    """Abstract base class for all agents in the system.

    Agents are responsible for processing structured data through the pipeline.
    Each agent takes a Pydantic model as input and returns a Pydantic model as output.
    """

    @abstractmethod
    async def process(self, input_data: TInput) -> TOutput:
        """Process the input data and return structured output.

        Args:
            input_data: Structured input data as a Pydantic model.

        Returns:
            Structured output data as a Pydantic model.

        Raises:
            AgentProcessingError: If processing fails.
        """
        pass

    @abstractmethod
    def get_input_schema(self) -> type[TInput]:
        """Return the Pydantic model class for input validation."""
        pass

    @abstractmethod
    def get_output_schema(self) -> type[TOutput]:
        """Return the Pydantic model class for output validation."""
        pass