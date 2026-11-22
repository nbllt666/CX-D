"""DreamTalk 领域模型：梦境会话、回合、记忆素材与醒来摘要。

本模块是纯数据定义，不依赖任何基础设施。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

CONTRACT_VERSION = "1.0"

# 模式：记忆梦 / 天马行空 / 一夜无梦
MODE_MEMORY = "memory"
MODE_WILD = "wild"
MODE_DREAMLESS = "dreamless"
MODES = (MODE_MEMORY, MODE_WILD, MODE_DREAMLESS)

MODE_LABELS = {
    MODE_MEMORY: "记忆梦",
    MODE_WILD: "天马行空",
    MODE_DREAMLESS: "一夜无梦",
}

# 说话人：潜意识导演 / 梦者 / 醒者
SPEAKER_DIRECTOR = "director"
SPEAKER_DREAMER = "dreamer"
SPEAKER_AWAKENED = "awakened"

SPEAKER_LABELS = {
    SPEAKER_DIRECTOR: "潜意识导演",
    SPEAKER_DREAMER: "梦者",
    SPEAKER_AWAKENED: "醒者",
}

STATUS_ACTIVE = "active"
STATUS_ENDED = "ended"


@dataclass
class Emotion:
    """情绪基调：效价（-1~1）与唤醒度（0~1）。"""

    valence: float = 0.0
    arousal: float = 0.0

    def intensity(self) -> float:
        """情绪强度：|valence| + arousal，截断到 1.0。"""
        return min(1.0, abs(float(self.valence)) + float(self.arousal))

    def clamped(self) -> "Emotion":
        """裁剪到合法区间，避免外部输入越界影响提示词。"""
        return Emotion(
            valence=max(-1.0, min(1.0, float(self.valence))),
            arousal=max(0.0, min(1.0, float(self.arousal))),
        )

    def to_dict(self) -> Dict[str, float]:
        return {"valence": float(self.valence), "arousal": float(self.arousal)}


@dataclass
class MemoryMaterial:
    """本次入睡时解析出的记忆素材快照（梦内唯一的外部输入）。"""

    day_memories: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    emotion: Emotion = field(default_factory=Emotion)
    source: str = "manual"

    def is_empty(self) -> bool:
        """没有任何可用素材（记忆与零散意象都为空）。"""
        has_memories = any(str(m).strip() for m in self.day_memories)
        has_entities = any(str(e).strip() for e in self.entities)
        return not (has_memories or has_entities)


@dataclass
class Message:
    """发送给 LLM 的一条消息。"""

    role: str
    content: str


@dataclass
class Turn:
    """梦境中的一个回合。"""

    seq: int
    speaker: str
    content: str
    flagged: bool = False
    created_at: str = ""


@dataclass
class DreamSession:
    """一场梦境会话。"""

    id: str
    created_at: str
    mode: str
    mode_reason: str
    status: str
    material: MemoryMaterial
    title: str = ""
    summary: str = ""
    emotion_residue: Dict[str, float] = field(default_factory=dict)
    ended_at: Optional[str] = None
    turn_count: int = 0


@dataclass
class DreamRecall:
    """清醒侧唯一可见的梦境摘要（不含原始回合）。"""

    session_id: str
    created_at: str
    mode: str
    title: str
    summary: str
    emotion_residue: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_session(cls, session: DreamSession) -> "DreamRecall":
        return cls(
            session_id=session.id,
            created_at=session.created_at,
            mode=session.mode,
            title=session.title,
            summary=session.summary,
            emotion_residue=dict(session.emotion_residue or {}),
        )


@dataclass
class DreamContext:
    """梦内上下文：素材快照 + 梦内回合 + 模式，绝不携带梦外历史。"""

    session_id: str
    mode: str
    material: MemoryMaterial
    turns: List[Turn] = field(default_factory=list)


@dataclass
class SessionView:
    """服务层返回：会话 + 可见回合（可选醒来摘要）。"""

    session: DreamSession
    turns: List[Turn] = field(default_factory=list)
    recall: Optional[DreamRecall] = None


def mode_label(mode: str) -> str:
    """模式的中文名；未知模式原样返回。"""
    return MODE_LABELS.get(mode, mode)


def speaker_label(speaker: str) -> str:
    """说话人的中文名；未知说话人原样返回。"""
    return SPEAKER_LABELS.get(speaker, speaker)


def emotion_to_dict(emotion: Emotion) -> Dict[str, float]:
    return emotion.clamped().to_dict()


def material_to_dict(material: MemoryMaterial) -> Dict[str, Any]:
    """素材快照的 JSON 友好表示。"""
    return {
        "day_memories": list(material.day_memories),
        "entities": list(material.entities),
        "emotion": emotion_to_dict(material.emotion),
        "source": material.source,
    }
