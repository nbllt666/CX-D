"""测试辅助：固定随机源、固定时钟、事件收集与录制客户端。"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Sequence

from dreamtalk.core.models import Message


class FixedRandom:
    def __init__(self, value: float):
        self.value = value

    def random(self) -> float:
        return self.value


class FixedClock:
    def __init__(self, start: str = "2026-11-22T22:00:00"):
        self._now = datetime.fromisoformat(start)

    def now(self) -> datetime:
        current = self._now
        self._now = self._now + timedelta(seconds=1)
        return current


class CollectingEvents:
    def __init__(self):
        self.events: List[Dict[str, Any]] = []

    async def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        self.events.append({"type": event_type, "data": data})


class RecordingLLM:
    """录制所有 messages 与温度的确定性客户端。"""

    def __init__(self, text: str = "雾从墙里慢慢溢出来，灯影在水面上折成一条路。"):
        self.text = text
        self.calls: List[List[Message]] = []
        self.temperatures: List[float] = []

    async def chat(self, messages: Sequence[Message], *, temperature: float) -> str:
        self.calls.append(
            [Message(role=m.role, content=m.content) for m in messages]
        )
        self.temperatures.append(temperature)
        return self.text


class SequencedLLM:
    """按顺序返回预设文本，用于验证纠正重写。"""

    def __init__(self, texts: Sequence[str]):
        self._texts = list(texts)
        self.calls: List[List[Message]] = []

    async def chat(self, messages: Sequence[Message], *, temperature: float) -> str:
        self.calls.append(
            [Message(role=m.role, content=m.content) for m in messages]
        )
        if self._texts:
            return self._texts.pop(0)
        return "我沿着灯影继续向前，脚下没有声音。"
