"""模式自动决策测试。"""

from __future__ import annotations

import pytest

from dreamtalk.core.errors import InvalidMode, NoMemoryMaterial
from dreamtalk.core.modes import ModeWeights, select_mode
from dreamtalk.core.models import Emotion
from tests.conftest import FixedRandom


def test_forced_memory_and_empty_rejection():
    mode, reason = select_mode(
        ["午后便利店的旧歌"],
        Emotion(),
        ModeWeights(),
        FixedRandom(0.0),
        forced="memory",
    )
    assert mode == "memory"
    assert "手动指定" in reason

    with pytest.raises(NoMemoryMaterial):
        select_mode([], Emotion(), ModeWeights(), FixedRandom(0.0), forced="memory")


def test_invalid_forced_mode():
    with pytest.raises(InvalidMode):
        select_mode(["a"], Emotion(), ModeWeights(), FixedRandom(0.0), forced="normal")


def test_no_memories_never_selects_memory():
    for roll in (0.0, 0.1, 0.5, 0.9, 0.999):
        mode, reason = select_mode([], Emotion(), ModeWeights(), FixedRandom(roll))
        assert mode in {"wild", "dreamless"}
        assert "记忆梦" not in reason or "没有" in reason


def test_no_memories_biases_dreamless():
    mode, reason = select_mode([], Emotion(), ModeWeights(), FixedRandom(0.99))
    assert mode == "dreamless"
    assert "记忆碎片" in reason or "无梦" in reason


def test_high_emotion_biases_wild():
    mode, reason = select_mode(
        ["地铁里有人吹口哨", "雨停在半空", "钥匙找不到锁"],
        Emotion(valence=-0.4, arousal=0.5),
        ModeWeights(),
        FixedRandom(0.5),
    )
    assert mode == "wild"
    assert "天马行空" in reason
    assert "情绪翻涌" in reason


def test_consecutive_dreamless_decays():
    memories = ["一封没有寄出的信", "窗台的灰"]
    normal_mode, _ = select_mode(
        memories, Emotion(), ModeWeights(), FixedRandom(0.9), last_mode="wild"
    )
    after_blank, _ = select_mode(
        memories, Emotion(), ModeWeights(), FixedRandom(0.9), last_mode="dreamless"
    )
    assert normal_mode == "dreamless"
    assert after_blank == "wild"


def test_all_zero_weights_fall_back_to_defaults():
    mode, _ = select_mode(
        ["一条旧围巾"],
        Emotion(),
        ModeWeights(memory=0.0, wild=0.0, dreamless=0.0),
        FixedRandom(0.0),
    )
    assert mode == "memory"
