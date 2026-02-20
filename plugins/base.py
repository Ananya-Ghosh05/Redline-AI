"""Base classes for plugins in the Redline AI system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import asyncio
from pydantic import BaseModel


class BasePlugin(ABC):
    """Abstract base class for all plugins.

    Plugins provide implementations for various AI components that can be
    swapped dynamically. Each plugin has a name, version, and configuration.
    """

    def __init__(self, name: str, version: str, config: Optional[Dict[str, Any]] = None):
        self.name = name
        self.version = version
        self.config = config or {}

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the plugin with its configuration."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources when shutting down the plugin."""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Return the capabilities and metadata of this plugin."""
        pass

    async def execute_with_timeout(self, coro: asyncio.coroutines.Coroutine, timeout: float = 30.0):
        """Execute a coroutine with a timeout.

        Args:
            coro: The coroutine to execute.
            timeout: Timeout in seconds.

        Returns:
            The result of the coroutine.

        Raises:
            asyncio.TimeoutError: If the execution times out.
        """
        return await asyncio.wait_for(coro, timeout=timeout)