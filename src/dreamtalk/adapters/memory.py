"""记忆源适配器：手动素材 / CX-O 只读采集器兼容层。"""

from __future__ import annotations

import inspect
import logging
from typing import Any, List

from dreamtalk.core.models import Emotion, MemoryMaterial

logger = logging.getLogger(__name__)


class ManualMemorySource:
    """手动记忆源：直接返回构造时给定的素材快照。"""

    def __init__(self, material: MemoryMaterial | None = None):
        self._material = material or MemoryMaterial(source="manual")

    async def collect(self, agent_id: str = "default") -> MemoryMaterial:
        return self._material


class CXOMemorySource:
    """把 CX-O ``DreamMaterialCollector`` 的只读快照映射为 MemoryMaterial。

    采集失败或快照非法时返回空素材，不阻断入睡；服务层会回退请求素材。
    """

    def __init__(self, collector, *, agent_id: str = "default"):
        self._collector = collector
        self._agent_id = agent_id

    async def collect(self, agent_id: str = "default") -> MemoryMaterial:
        try:
            snapshot = self._collector.collect(self._agent_id or agent_id)
            if inspect.isawaitable(snapshot):
                snapshot = await snapshot
            return _snapshot_to_material(snapshot)
        except Exception as exc:  # noqa: BLE001 - 采集失败降级为空素材
            logger.warning("CX-O 记忆采集失败，返回空素材: %s", exc)
            return MemoryMaterial(source="cxo_memory")


def _snapshot_to_material(snapshot: Any) -> MemoryMaterial:
    """兼容 dataclass / dict 两种快照形态。"""
    memories = _field(snapshot, "memories", []) or []
    entities = _field(snapshot, "isolated_entities", None)
    if entities is None:
        entities = _field(snapshot, "entities", []) or []
    baseline = _field(snapshot, "emotion_baseline", None)
    raw_emotion = _field(snapshot, "emotion", None)

    emotion = Emotion()
    if isinstance(raw_emotion, Emotion):
        emotion = raw_emotion.clamped()
    elif isinstance(raw_emotion, dict):
        emotion = Emotion(
            valence=_to_float(raw_emotion.get("valence"), 0.0),
            arousal=_to_float(raw_emotion.get("arousal"), 0.0),
        ).clamped()
    elif baseline is not None:
        emotion = Emotion(valence=_to_float(baseline, 0.0), arousal=0.0).clamped()

    return MemoryMaterial(
        day_memories=_memory_lines(memories),
        entities=[str(entity).strip() for entity in entities if str(entity).strip()],
        emotion=emotion,
        source="cxo_memory",
    )


def _field(obj: Any, name: str, default: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _memory_lines(memories: Any) -> List[str]:
    lines: List[str] = []
    for memory in memories or []:
        if isinstance(memory, dict):
            content = str(memory.get("content") or "").strip()
        else:
            content = str(memory or "").strip()
        if content:
            lines.append(content)
    return lines


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
