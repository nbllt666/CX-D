"""Mock LLM 与角色提示词测试。"""

from __future__ import annotations

from dreamtalk.adapters.llm import MockLLMClient
from dreamtalk.core.models import (
    MODE_MEMORY,
    MODE_WILD,
    SPEAKER_DIRECTOR,
    SPEAKER_DREAMER,
    Emotion,
    MemoryMaterial,
    Message,
)
from dreamtalk.core.personas import material_block, system_prompt


async def test_mock_respects_speaker_role():
    director = MockLLMClient(seed=0)
    dreamer = MockLLMClient(seed=0)
    director_text = await director.chat(
        [
            Message(role="system", content=system_prompt(SPEAKER_DIRECTOR, MODE_MEMORY)),
            Message(role="user", content="梦境开始。"),
        ],
        temperature=0.9,
    )
    dreamer_text = await dreamer.chat(
        [
            Message(role="system", content=system_prompt(SPEAKER_DREAMER, MODE_MEMORY)),
            Message(role="user", content="请以第一人称回应。"),
        ],
        temperature=0.9,
    )
    assert director_text.startswith(("潮水", "走廊", "站台"))
    assert dreamer_text.startswith(("我把", "我伸手", "我推开"))


def test_prompts_contain_role_boundaries():
    director = system_prompt(SPEAKER_DIRECTOR, MODE_MEMORY)
    dreamer = system_prompt(SPEAKER_DREAMER, MODE_MEMORY)
    wild = system_prompt(SPEAKER_DREAMER, MODE_WILD)
    assert "禁止替梦者行动" in director
    assert "禁止代替其他角色说话" in dreamer
    assert "不给选项" in director
    assert "你昨天" in director
    assert "天马行空" in wild


def test_material_block_marks_memories_as_latent_images():
    block = material_block(
        MemoryMaterial(
            day_memories=["便利店的旧歌"],
            entities=["旧钥匙"],
            emotion=Emotion(0.2, 0.3),
        )
    )
    assert "只作潜在意象" in block
    assert "便利店的旧歌" in block
    assert "旧钥匙" in block
