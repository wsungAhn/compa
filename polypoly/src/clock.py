"""Live / replay time abstraction.

DO:  pass Clock into all time-dependent code so replay uses the same logic as live
DON'T: call datetime.now() or asyncio.sleep() directly in business logic modules
"""
from __future__ import annotations
import asyncio
import time
from abc import ABC, abstractmethod


class Clock(ABC):
    @abstractmethod
    def now(self) -> float: ...

    @abstractmethod
    async def sleep(self, seconds: float) -> None: ...


class LiveClock(Clock):
    def now(self) -> float:
        return time.time()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class ReplayClock(Clock):
    """Fast-forwards through a sorted sequence of recorded timestamps."""

    def __init__(self, timestamps: list[float]) -> None:
        self._ts = sorted(timestamps)
        self._idx = 0

    def now(self) -> float:
        if self._idx < len(self._ts):
            return self._ts[self._idx]
        return self._ts[-1] if self._ts else 0.0

    async def sleep(self, seconds: float) -> None:
        target = self.now() + seconds
        while self._idx < len(self._ts) and self._ts[self._idx] < target:
            self._idx += 1
