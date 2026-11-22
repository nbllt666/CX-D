"""梦境内容闸门测试。"""

from __future__ import annotations

import pytest

from dreamtalk.core.filter import check_text, is_clean


@pytest.mark.parametrize(
    "text",
    [
        "你昨天答应过我要一起去看海。",
        "你刚才明明站在门口。",
        "你说过那盏灯不会灭。",
        "你曾经把它埋在树下。",
        "你做了那件谁都不愿提起的事。",
        "我记得你把钥匙放进了杯子。",
    ],
)
def test_factual_assertions_are_blocked(text):
    assert check_text(text)
    assert not is_clean(text)


@pytest.mark.parametrize(
    "text",
    [
        "雾从地板缝里升起来，走廊尽头有一盏不断换色的灯。",
        "我把影子折成纸船，放进铁轨之间的水里。",
        "",
    ],
)
def test_normal_dream_text_passes(text):
    assert check_text(text) == []
    assert is_clean(text)
