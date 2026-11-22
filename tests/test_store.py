"""会话存储测试（SQLite 与内存两套实现）。"""

from __future__ import annotations

import pytest

from dreamtalk.adapters.store import MemorySessionStore, SQLiteSessionStore
from dreamtalk.core.models import (
    STATUS_ACTIVE,
    DreamSession,
    Emotion,
    MemoryMaterial,
)


def _session(session_id: str, created_at: str, mode: str = "memory") -> DreamSession:
    return DreamSession(
        id=session_id,
        created_at=created_at,
        mode=mode,
        mode_reason="测试",
        status=STATUS_ACTIVE,
        material=MemoryMaterial(
            day_memories=["便利店的旧歌", "窗台的灰"],
            entities=["钥匙"],
            emotion=Emotion(valence=0.2, arousal=0.3),
        ),
    )


@pytest.fixture(params=["sqlite", "memory"])
def store(request, tmp_path):
    if request.param == "sqlite":
        return SQLiteSessionStore(tmp_path / "dreamtalk.db")
    return MemorySessionStore()


def test_create_get_and_turns(store):
    store.create_session(_session("s1", "2026-11-22T22:00:00"))
    session = store.get_session("s1")
    assert session is not None
    assert session.mode == "memory"
    assert session.material.day_memories == ["便利店的旧歌", "窗台的灰"]
    assert session.material.entities == ["钥匙"]
    assert session.material.emotion.arousal == 0.3

    first = store.append_turn("s1", "director", "第一段", False, "2026-11-22T22:00:01")
    second = store.append_turn("s1", "dreamer", "第二段", True, "2026-11-22T22:00:02")
    assert first.seq == 1
    assert second.seq == 2
    assert [turn.speaker for turn in store.get_turns("s1")] == ["director", "dreamer"]
    assert store.get_turns("s1")[1].flagged is True
    assert store.get_session("s1").turn_count == 2


def test_list_order_and_last_mode(store):
    store.create_session(_session("s1", "2026-11-22T22:00:00"))
    store.create_session(_session("s2", "2026-11-23T22:00:00", mode="dreamless"))
    sessions = store.list_sessions(limit=10)
    assert [session.id for session in sessions] == ["s2", "s1"]
    assert store.last_mode() == "dreamless"


def test_end_session(store):
    store.create_session(_session("s1", "2026-11-22T22:00:00"))
    store.end_session(
        "s1",
        title="倒挂的窗",
        summary="潮水退去后，窗里长出一片森林。",
        emotion_residue={"valence": 0.2, "arousal": 0.4},
        ended_at="2026-11-22T23:00:00",
    )
    session = store.get_session("s1")
    assert session.status == "ended"
    assert session.title == "倒挂的窗"
    assert session.summary.startswith("潮水")
    assert session.emotion_residue["arousal"] == 0.4
    assert session.ended_at == "2026-11-22T23:00:00"
