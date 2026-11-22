"""DreamTalk 应用门面：解析素材、选择模式，并把调用转交给梦境编排器。

CX-O 回装时可直接构造本类，无需启动 HTTP 服务。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import random
from typing import List, Optional, Sequence

from dreamtalk.core.dialogue import DreamDialogue, DialogueConfig
from dreamtalk.core.modes import ModeWeights, select_mode
from dreamtalk.core.models import (
    DreamRecall,
    DreamSession,
    Emotion,
    MemoryMaterial,
    SessionView,
)

logger = logging.getLogger(__name__)


class DreamTalkService:
    """独立项目与 CX-O 共用的应用门面。"""

    def __init__(
        self,
        *,
        dreamer,
        director,
        store,
        memory_source=None,
        rng=None,
        clock=None,
        events=None,
        dialogue_config: Optional[DialogueConfig] = None,
        mode_weights: Optional[ModeWeights] = None,
    ):
        self._dialogue = DreamDialogue(
            dreamer=dreamer,
            director=director,
            store=store,
            clock=clock,
            events=events,
            config=dialogue_config,
        )
        self._store = store
        self._memory_source = memory_source
        self._mode_weights = mode_weights or ModeWeights()
        self._rng = rng or _SystemRandom()

    # ================================================================ 入睡
    async def start_session(
        self,
        *,
        day_memories: Optional[Sequence[str]] = None,
        entities: Optional[Sequence[str]] = None,
        emotion: Optional[Emotion] = None,
        mode: str = "auto",
        agent_id: str = "default",
    ) -> SessionView:
        """创建一场梦境会话。

        - 有注入 ``memory_source`` 时优先使用其快照；快照为空则回退请求素材；
        - ``mode="auto"`` 走自动决策，其余值视为显式指定；
        - 记忆梦无当天记忆时由模式层抛出 ``NoMemoryMaterial``。
        """
        request_material = MemoryMaterial(
            day_memories=_clean_list(day_memories),
            entities=_clean_list(entities),
            emotion=(emotion or Emotion()).clamped(),
            source="manual",
        )
        material = await self._resolve_material(request_material, agent_id)
        last_mode = await asyncio.to_thread(self._store.last_mode)
        forced = None if (mode or "auto") == "auto" else mode
        chosen, reason = select_mode(
            material.day_memories,
            material.emotion,
            self._mode_weights,
            self._rng,
            forced=forced,
            last_mode=last_mode,
        )
        return await self._dialogue.start(material, chosen, reason)

    async def _resolve_material(
        self, request_material: MemoryMaterial, agent_id: str
    ) -> MemoryMaterial:
        """入睡时解析一次素材快照；此后梦境不再访问记忆源。"""
        if self._memory_source is None:
            return request_material
        try:
            snapshot = self._memory_source.collect(agent_id)
            if inspect.isawaitable(snapshot):
                snapshot = await snapshot
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - 记忆源失败不得阻断入睡
            logger.warning("记忆源采集失败，回退请求素材: %s", exc)
            return request_material
        if not isinstance(snapshot, MemoryMaterial):
            logger.warning("记忆源返回了非 MemoryMaterial 快照，回退请求素材")
            return request_material
        if snapshot.is_empty() and not request_material.is_empty():
            logger.info("记忆源快照为空，回退请求素材")
            return request_material
        return snapshot

    # ================================================================ 梦境推进
    async def interject(self, session_id: str, content: str) -> SessionView:
        return await self._dialogue.interject(session_id, content)

    async def advance(self, session_id: str) -> SessionView:
        return await self._dialogue.advance(session_id)

    async def wake(self, session_id: str) -> SessionView:
        return await self._dialogue.wake(session_id)

    # ================================================================ 读取
    async def get_session(self, session_id: str) -> SessionView:
        return await self._dialogue.get_session(session_id)

    async def list_sessions(self, limit: int = 20) -> List[DreamSession]:
        return await self._dialogue.list_sessions(limit)

    async def get_recall(self, session_id: str) -> DreamRecall:
        return await self._dialogue.get_recall(session_id)

    async def list_recalls(self, limit: int = 20) -> List[DreamRecall]:
        return await self._dialogue.list_recalls(limit)


class _SystemRandom:
    def random(self) -> float:
        return random.random()


def _clean_list(values: Optional[Sequence[str]]) -> List[str]:
    return [str(value).strip() for value in (values or []) if str(value).strip()]
