"""Base class for all Clarity agents."""

from abc import ABC, abstractmethod
from ..core import logger


class BaseAgent(ABC):
    """Abstract base for all Clarity AI agents."""

    name: str = "BaseAgent"
    role: str = ""
    goal: str = ""

    def __init__(self):
        logger.info(f"{self.name} initialized.", role=self.role)

    @abstractmethod
    async def run(self, *args, **kwargs):
        """Execute the agent's primary workflow."""
        raise NotImplementedError
