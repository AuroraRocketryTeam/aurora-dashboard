"""Abstract base class for all telemetry data sources."""

from abc import ABC, abstractmethod
from typing import AsyncIterator

from models.telemetry import TelemetryFrame


class DataSource(ABC):
    """
    Every source must implement stream() as an async generator of
    TelemetryFrame.
    """

    @abstractmethod
    async def stream(self) -> AsyncIterator[TelemetryFrame]:
        """ TelemetryFrame objects as they become available. """
        ...

    async def close(self) -> None:
        """ Optional cleanup when the source is no longer needed. """
