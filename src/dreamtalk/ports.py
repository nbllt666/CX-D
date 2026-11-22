"""DreamTalk 端口协议：核心层只依赖这些协议，便于整体移植回 CX-O。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Protocol, Sequence, runtime_checkable

if TYPE_CHECKING:
    from dreamtalk.core.models import DreamSession, MemoryMaterial, Message, Turn


@runtime_checkable
class LLMClient(Protocol):
    """异步 LLM 客户端：输入消息序列，返回纯文本。"""

    async def chat(self, messages: Sequence["Message"], *, temperature: float) -> str:
        ...


@runtime_checkable
class MemorySource(Protocol):
    """记忆源：入睡时解析一次素材快照；梦境回合期间不再访问。"""

    async def collect(self, agent_id: str = "default") -> "MemoryMaterial":
        ...


@runtime_checkable
class SessionStore(Protocol):
    """会话与回合存储。方法为同步短操作，由服务层放入线程池执行。"""

    def create_session(self, session: "DreamSession") -> None:
        ...

    def get_session(self, session_id: str) -> "DreamSession | None":
        ...

    def list_sessions(self, limit: int = 20) -> List["DreamSession"]:
        ...

    def append_turn(
        self,
        session_id: str,
        speaker: str,
        content: str,
        flagged: bool = False,
        created_at: str = "",
    ) -> "Turn":
        ...

    def get_turns(self, session_id: str) -> List["Turn"]:
        ...

    def end_session(
        self,
        session_id: str,
        *,
        title: str,
        summary: str,
        emotion_residue: Dict[str, float],
        ended_at: str,
    ) -> None:
        ...

    def last_mode(self) -> "str | None":
        ...


@runtime_checkable
class RandomSource(Protocol):
    """随机源：模式判定可注入固定值以便测试。"""

    def random(self) -> float:
        ...


@runtime_checkable
class Clock(Protocol):
    """时钟：可注入固定时间以便测试。"""

    def now(self) -> datetime:
        ...


@runtime_checkable
class EventSink(Protocol):
    """事件出口：默认空实现；回装 CX-O 后可接 WebSocket 广播。"""

    async def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        ...
