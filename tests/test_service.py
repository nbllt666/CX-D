"""双 LLM 梦境编排与服务门面测试（不启动 HTTP）。"""

from __future__ import annotations

import inspect

import pytest

from dreamtalk.adapters.llm import MockLLMClient
from dreamtalk.adapters.memory import CXOMemorySource, ManualMemorySource
from dreamtalk.adapters.store import MemorySessionStore
from dreamtalk.core.dialogue import DialogueConfig, DreamDialogue
from dreamtalk.core.errors import NoMemoryMaterial, SessionEnded, SessionNotFound
from dreamtalk.core.filter import DREAM_BROKEN_TEXT
from dreamtalk.core.modes import ModeWeights
from dreamtalk.core.models import Emotion, MemoryMaterial
from dreamtalk.service import DreamTalkService
from tests.conftest import (
    CollectingEvents,
    FixedClock,
    FixedRandom,
    RecordingLLM,
    SequencedLLM,
)


def build_service(
    *,
    max_rounds: int = 8,
    memory_source=None,
    dreamer=None,
    director=None,
    rng=None,
    store=None,
    events=None,
):
    store = store or MemorySessionStore()
    dreamer = dreamer or MockLLMClient(seed=0)
    director = director or MockLLMClient(seed=7)
    events = events or CollectingEvents()
    service = DreamTalkService(
        dreamer=dreamer,
        director=director,
        store=store,
        memory_source=memory_source,
        rng=rng or FixedRandom(0.0),
        clock=FixedClock(),
        events=events,
        dialogue_config=DialogueConfig(max_rounds=max_rounds),
        mode_weights=ModeWeights(),
    )
    return service, store, events, dreamer, director


@pytest.mark.asyncio
async def test_memory_session_opens_with_director_then_dreamer():
    service, store, events, _, _ = build_service()
    view = await service.start_session(
        day_memories=["午后在便利店听到一首旧歌", "和同事争了一句"],
        mode="memory",
    )
    assert view.session.mode == "memory"
    assert view.session.status == "active"
    assert [turn.speaker for turn in view.turns] == ["director", "dreamer"]
    assert [turn.seq for turn in view.turns] == [1, 2]
    assert all(turn.content for turn in view.turns)
    assert store.get_session(view.session.id).turn_count == 2
    assert [event["type"] for event in events.events][:3] == [
        "dream.session_started",
        "dream.turn_added",
        "dream.turn_added",
    ]


@pytest.mark.asyncio
async def test_interject_adds_awakened_then_two_turns():
    service, _, _, _, _ = build_service()
    view = await service.start_session(day_memories=["一条旧围巾"], mode="memory")
    session_id = view.session.id
    advanced = await service.interject(session_id, "我伸手推开那扇门")
    assert [turn.speaker for turn in advanced.turns[-3:]] == [
        "awakened",
        "director",
        "dreamer",
    ]
    assert advanced.turns[-3].content == "我伸手推开那扇门"
    assert len(advanced.turns) == 5


@pytest.mark.asyncio
async def test_advance_with_empty_content_adds_only_round():
    service, _, _, _, _ = build_service()
    view = await service.start_session(day_memories=["一条旧围巾"], mode="memory")
    advanced = await service.advance(view.session.id)
    assert len(advanced.turns) == len(view.turns) + 2
    assert advanced.turns[-2].speaker == "director"
    assert advanced.turns[-1].speaker == "dreamer"


@pytest.mark.asyncio
async def test_dreamless_uses_zero_llm_calls():
    service, store, events, dreamer, director = build_service()
    view = await service.start_session(day_memories=[], mode="dreamless")
    assert view.turns == []
    assert view.session.status == "ended"
    assert view.session.title == "一夜无梦"
    assert view.session.summary
    assert view.recall is not None
    assert dreamer.calls == 0 and director.calls == 0
    assert store.get_session(view.session.id).status == "ended"
    assert events.events[-1]["type"] == "dream.session_completed"


@pytest.mark.asyncio
async def test_forced_memory_without_memories_rejected():
    service, store, _, dreamer, director = build_service()
    with pytest.raises(NoMemoryMaterial):
        await service.start_session(day_memories=[], mode="memory")
    assert store.list_sessions() == []
    assert dreamer.calls == 0 and director.calls == 0


@pytest.mark.asyncio
async def test_max_rounds_auto_ends_and_conflicts():
    service, _, _, _, _ = build_service(max_rounds=1)
    view = await service.start_session(day_memories=["一条旧围巾"], mode="memory")
    assert view.session.status == "ended"
    assert view.session.summary
    assert view.recall is not None
    with pytest.raises(SessionEnded):
        await service.wake(view.session.id)
    with pytest.raises(SessionEnded):
        await service.interject(view.session.id, "还想继续")


@pytest.mark.asyncio
async def test_wake_and_recall():
    service, _, events, _, _ = build_service()
    view = await service.start_session(day_memories=["一条旧围巾"], mode="memory")
    session_id = view.session.id
    woken = await service.wake(session_id)
    assert woken.session.status == "ended"
    assert woken.recall is not None
    assert woken.recall.session_id == session_id
    assert woken.session.title
    assert woken.session.summary

    recall = await service.get_recall(session_id)
    assert recall.summary == woken.session.summary
    recalls = await service.list_recalls()
    assert [item.session_id for item in recalls] == [session_id]
    assert events.events[-1]["type"] == "dream.session_completed"

    with pytest.raises(SessionEnded):
        await service.wake(session_id)


@pytest.mark.asyncio
async def test_recall_requires_ended_session():
    service, _, _, _, _ = build_service()
    view = await service.start_session(day_memories=["一条旧围巾"], mode="memory")
    with pytest.raises(SessionEnded):
        await service.get_recall(view.session.id)
    with pytest.raises(SessionNotFound):
        await service.get_recall("missing")


@pytest.mark.asyncio
async def test_context_isolation_between_sessions():
    dreamer = RecordingLLM("我沿着没有尽头的走廊向前走。")
    director = RecordingLLM("灯一盏一盏亮起，像有人在远处呼吸。")
    service, _, _, _, _ = build_service(dreamer=dreamer, director=director)

    first = await service.start_session(day_memories=["A-素材-绝密"], mode="memory")
    await service.interject(first.session.id, "A-醒者-哨兵")
    dreamer_mark = len(dreamer.calls)
    director_mark = len(director.calls)

    await service.start_session(day_memories=["B-素材"], mode="memory")
    new_calls = dreamer.calls[dreamer_mark:] + director.calls[director_mark:]
    assert new_calls
    flat = "\n".join(message.content for call in new_calls for message in call)
    assert "A-醒者-哨兵" not in flat
    assert "A-素材-绝密" not in flat
    assert "B-素材" in flat


def test_build_messages_only_accepts_dream_context():
    signature = inspect.signature(DreamDialogue.build_messages)
    assert list(signature.parameters) == ["self", "speaker", "context"]


@pytest.mark.asyncio
async def test_factual_assertion_is_rewritten_once():
    dreamer = SequencedLLM(["你昨天答应过我，会在雪停之前回来。", "雪落在没有门牌的房间，我把约定折成一只纸鸟。"])
    director = SequencedLLM(["走廊尽头的雪越下越大，一扇窗在风里轻轻开合。"])
    service, _, _, _, _ = build_service(dreamer=dreamer, director=director)
    view = await service.start_session(day_memories=["雪"], mode="memory")
    dreamer_turn = [turn for turn in view.turns if turn.speaker == "dreamer"][0]
    assert dreamer_turn.flagged is False
    assert "你昨天" not in dreamer_turn.content
    assert len(dreamer.calls) == 2
    assert "梦的契约" in dreamer.calls[1][-1].content


@pytest.mark.asyncio
async def test_factual_assertion_remaining_is_flagged():
    dreamer = SequencedLLM(["你昨天答应过我。", "你曾经把那把钥匙埋在树下。"])
    director = SequencedLLM(["雪落在空无一人的站台上。"])
    service, _, _, _, _ = build_service(dreamer=dreamer, director=director)
    view = await service.start_session(day_memories=["雪"], mode="memory")
    dreamer_turn = [turn for turn in view.turns if turn.speaker == "dreamer"][0]
    assert dreamer_turn.flagged is True


@pytest.mark.asyncio
async def test_empty_text_retries_then_placeholder():
    dreamer = SequencedLLM(["", ""])
    director = SequencedLLM(["雾把站台的轮廓擦掉了。"])
    service, _, _, _, _ = build_service(dreamer=dreamer, director=director)
    view = await service.start_session(day_memories=["雾"], mode="memory")
    dreamer_turn = [turn for turn in view.turns if turn.speaker == "dreamer"][0]
    assert dreamer_turn.content == DREAM_BROKEN_TEXT
    assert len(dreamer.calls) == 2


@pytest.mark.asyncio
async def test_memory_source_can_be_swapped():
    class FakeCollector:
        def collect(self, agent_id):
            return {
                "memories": [{"content": "采集到的边缘记忆"}],
                "isolated_entities": ["旧灯"],
                "emotion_baseline": 0.4,
            }

    service, _, _, _, _ = build_service(memory_source=CXOMemorySource(FakeCollector()))
    view = await service.start_session(day_memories=[], mode="memory")
    assert view.session.material.day_memories == ["采集到的边缘记忆"]
    assert view.session.material.entities == ["旧灯"]
    assert view.session.material.source == "cxo_memory"
    assert view.session.material.emotion.valence == 0.4

    manual = ManualMemorySource(
        MemoryMaterial(day_memories=["手动素材"], emotion=Emotion(0.1, 0.2))
    )
    service, _, _, _, _ = build_service(memory_source=manual)
    view = await service.start_session(day_memories=[], mode="memory")
    assert view.session.material.day_memories == ["手动素材"]


@pytest.mark.asyncio
async def test_wild_mode_uses_higher_temperatures():
    dreamer = RecordingLLM("我把钥匙抛向空中，它变成一只发亮的鸟。")
    director = RecordingLLM("站台忽然竖了起来，像一页被风翻开的纸。")
    service, _, _, _, _ = build_service(dreamer=dreamer, director=director)
    await service.start_session(day_memories=["一条旧围巾"], mode="wild")
    assert director.temperatures[0] == 1.0
    assert dreamer.temperatures[0] == 1.1


@pytest.mark.asyncio
async def test_memory_mode_uses_default_temperatures():
    dreamer = RecordingLLM("我沿着走廊慢慢向前走。")
    director = RecordingLLM("灯在走廊尽头一盏一盏亮起来。")
    service, _, _, _, _ = build_service(dreamer=dreamer, director=director)
    await service.start_session(day_memories=["一条旧围巾"], mode="memory")
    assert director.temperatures[0] == 0.85
    assert dreamer.temperatures[0] == 0.9


@pytest.mark.asyncio
async def test_memory_material_reaches_llm_as_latent_image():
    dreamer = RecordingLLM("我沿着走廊向前走，灯一盏一盏亮起来。")
    director = RecordingLLM("雾从墙里溢出来，你站在没有尽头的走廊里。")
    service, _, _, _, _ = build_service(dreamer=dreamer, director=director)
    view = await service.start_session(
        day_memories=["午后便利店的旧歌"], mode="memory"
    )
    flat_prompts = "\n".join(
        message.content
        for call in dreamer.calls + director.calls
        for message in call
    )
    assert "午后便利店的旧歌" in flat_prompts
    assert "午后便利店的旧歌" not in "\n".join(turn.content for turn in view.turns)


@pytest.mark.asyncio
async def test_auto_mode_selects_all_three_modes():
    service, _, _, _, _ = build_service(rng=FixedRandom(0.0))
    memory_view = await service.start_session(day_memories=["a", "b"], mode="auto")
    assert memory_view.session.mode == "memory"

    service, _, _, _, _ = build_service(rng=FixedRandom(0.5))
    wild_view = await service.start_session(
        day_memories=["a", "b", "c"],
        emotion=Emotion(valence=-0.4, arousal=0.5),
        mode="auto",
    )
    assert wild_view.session.mode == "wild"

    service, _, _, _, _ = build_service(rng=FixedRandom(0.99))
    blank_view = await service.start_session(day_memories=[], mode="auto")
    assert blank_view.session.mode == "dreamless"
    assert blank_view.turns == []


@pytest.mark.asyncio
async def test_memory_source_is_collected_only_once():
    class CountingSource:
        def __init__(self):
            self.calls = 0

        async def collect(self, agent_id):
            self.calls += 1
            return MemoryMaterial(day_memories=["采集一次"], source="fake")

    source = CountingSource()
    service, _, _, _, _ = build_service(memory_source=source)
    view = await service.start_session(day_memories=[], mode="memory")
    await service.interject(view.session.id, "我继续往前走")
    await service.advance(view.session.id)
    assert source.calls == 1


@pytest.mark.asyncio
async def test_memory_source_failure_falls_back_to_request():
    class BrokenCollector:
        def collect(self, agent_id):
            raise RuntimeError("boom")

    service, _, _, _, _ = build_service(memory_source=CXOMemorySource(BrokenCollector()))
    view = await service.start_session(day_memories=["请求里的记忆"], mode="memory")
    assert view.session.material.day_memories == ["请求里的记忆"]
