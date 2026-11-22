"""双 LLM 梦境编排：梦者 × 潜意识导演交替共演，含上下文隔离与醒来摘要。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from dreamtalk.core.errors import SessionEnded, SessionNotFound
from dreamtalk.core.filter import (
    CORRECTION_INSTRUCTION,
    DREAM_BROKEN_TEXT,
    check_text,
)
from dreamtalk.core.models import (
    MODE_DREAMLESS,
    MODE_WILD,
    SPEAKER_AWAKENED,
    SPEAKER_DREAMER,
    SPEAKER_DIRECTOR,
    SPEAKER_LABELS,
    STATUS_ACTIVE,
    STATUS_ENDED,
    DreamContext,
    DreamRecall,
    DreamSession,
    MemoryMaterial,
    Message,
    SessionView,
    Turn,
)
from dreamtalk.core.personas import material_block, system_prompt, turn_instruction

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DialogueConfig:
    """对话编排参数（由适配器 Settings 映射，核心不读环境变量）。"""

    max_rounds: int = 8
    context_turns: int = 16
    director_temperature: float = 0.85
    dreamer_temperature: float = 0.9
    wild_director_temperature: float = 1.0
    wild_dreamer_temperature: float = 1.1
    summary_temperature: float = 0.4
    summary_max_chars: int = 120
    title_max_chars: int = 12
    transcript_max_chars: int = 4000


class _SystemClock:
    def now(self) -> datetime:
        return datetime.now()


class _NullEventSink:
    async def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        return None


_DREAMLESS_SUMMARY = "没有画面，也没有声音。{reason}。你在黑暗里安静地沉下去。"

_DIRECTOR_FALLBACK = (
    "雾把四周的轮廓擦掉了。你站在一条没有尽头的走廊里，"
    "尽头的灯一盏一盏亮起，又在你回头时熄灭。"
)
_DREAMER_FALLBACK = (
    "我向前走，脚下的地板像水面一样泛起涟漪。"
    "走廊尽头传来纸张翻动的声音，我伸手推开了那扇没有把手的门。"
)

_SUMMARY_SYSTEM = (
    "你是梦醒后的记录者。根据一场梦的完整片段，写一份只保留余韵的摘要。"
    "不要复述原文，不要分析心理，不要给建议。"
    "只输出一个 JSON 对象："
    '{"title": "不超过12字的标题", "summary": "不超过120字的余韵", '
    '"emotion_residue": {"valence": 数值, "arousal": 数值}}。'
    "不要输出任何多余文字。"
)


class DreamDialogue:
    """梦境对话编排器。

    只通过构造注入的端口工作；梦内上下文仅由 ``MemoryMaterial`` 与
    本会话回合构成，不读取任何梦外数据。
    """

    def __init__(
        self,
        *,
        dreamer,
        director,
        store,
        clock=None,
        events=None,
        config: Optional[DialogueConfig] = None,
    ):
        self._dreamer = dreamer
        self._director = director
        self._store = store
        self._clock = clock or _SystemClock()
        self._events = events or _NullEventSink()
        self._config = config or DialogueConfig()
        self._locks: Dict[str, asyncio.Lock] = {}

    # ================================================================ 对外入口
    async def start(
        self,
        material: MemoryMaterial,
        mode: str,
        mode_reason: str,
    ) -> SessionView:
        """创建一场会话；无梦模式不调用 LLM，直接结束。"""
        now = self._clock.now().isoformat()
        session = DreamSession(
            id=uuid.uuid4().hex,
            created_at=now,
            mode=mode,
            mode_reason=mode_reason,
            status=STATUS_ACTIVE,
            material=material,
        )
        await self._store_call(self._store.create_session, session)
        await self._emit(
            "dream.session_started",
            {"session_id": session.id, "mode": mode, "status": STATUS_ACTIVE},
        )

        if mode == MODE_DREAMLESS:
            turns: List[Turn] = []
            session.summary = _truncate(
                _DREAMLESS_SUMMARY.format(reason=mode_reason),
                self._config.summary_max_chars,
            )
            session.title = "一夜无梦"
            session.emotion_residue = material.emotion.clamped().to_dict()
            session.status = STATUS_ENDED
            session.ended_at = self._clock.now().isoformat()
            await self._store_call(
                self._store.end_session,
                session.id,
                title=session.title,
                summary=session.summary,
                emotion_residue=session.emotion_residue,
                ended_at=session.ended_at,
            )
            await self._emit_completed(session)
            return SessionView(
                session=session,
                turns=turns,
                recall=DreamRecall.from_session(session),
            )

        turns = await self._run_round(session, [])
        if self._rounds_played(turns) >= self._config.max_rounds:
            await self._end_with_recall(session, turns)
        session.turn_count = len(turns)
        return SessionView(
            session=session,
            turns=turns,
            recall=DreamRecall.from_session(session) if session.status == STATUS_ENDED else None,
        )

    async def interject(self, session_id: str, content: str) -> SessionView:
        """醒者插话（内容为空等价于继续做梦）。"""
        lock = self._lock_for(session_id)
        async with lock:
            session = await self._load_active(session_id)
            turns = await self._store_call(self._store.get_turns, session_id)
            text = (content or "").strip()
            if text:
                turn = await self._append_turn(
                    session, SPEAKER_AWAKENED, text, flagged=False
                )
                turns.append(turn)
            await self._run_round(session, turns)
            recall = None
            if self._rounds_played(turns) >= self._config.max_rounds:
                recall = await self._end_with_recall(session, turns)
            session.turn_count = len(turns)
            return SessionView(session=session, turns=turns, recall=recall)

    async def advance(self, session_id: str) -> SessionView:
        """不插话，直接推进一轮。"""
        return await self.interject(session_id, "")

    async def wake(self, session_id: str) -> SessionView:
        """主动醒来：结束会话并生成摘要（幂等冲突）。"""
        lock = self._lock_for(session_id)
        async with lock:
            session = await self._load_active(session_id)
            turns = await self._store_call(self._store.get_turns, session_id)
            recall = await self._end_with_recall(session, turns)
            session.turn_count = len(turns)
            return SessionView(session=session, turns=turns, recall=recall)

    async def get_session(self, session_id: str) -> SessionView:
        """读取会话与全部回合（梦境档案）。"""
        session = await self._store_call(self._store.get_session, session_id)
        if session is None:
            raise SessionNotFound(f"梦境会话不存在: {session_id}")
        turns = await self._store_call(self._store.get_turns, session_id)
        session.turn_count = len(turns)
        recall = DreamRecall.from_session(session) if session.status == STATUS_ENDED else None
        return SessionView(session=session, turns=turns, recall=recall)

    async def list_sessions(self, limit: int = 20) -> List[DreamSession]:
        return await self._store_call(self._store.list_sessions, limit)

    async def get_recall(self, session_id: str) -> DreamRecall:
        """读取清醒侧摘要；未结束的会话不允许导出。"""
        session = await self._store_call(self._store.get_session, session_id)
        if session is None:
            raise SessionNotFound(f"梦境会话不存在: {session_id}")
        if session.status != STATUS_ENDED:
            raise SessionEnded("梦境尚未结束，暂时没有醒来摘要")
        return DreamRecall.from_session(session)

    async def list_recalls(self, limit: int = 20) -> List[DreamRecall]:
        sessions = await self._store_call(self._store.list_sessions, limit)
        return [
            DreamRecall.from_session(s) for s in sessions if s.status == STATUS_ENDED
        ]

    # ================================================================ 回合生成
    async def _run_round(
        self, session: DreamSession, turns: List[Turn]
    ) -> List[Turn]:
        """生成一轮：导演 -> 梦者。返回新回合列表。"""
        new_turns: List[Turn] = []
        for speaker in (SPEAKER_DIRECTOR, SPEAKER_DREAMER):
            context = DreamContext(
                session_id=session.id,
                mode=session.mode,
                material=session.material,
                turns=list(turns),
            )
            content, flagged = await self._generate_turn(speaker, context)
            turn = await self._append_turn(session, speaker, content, flagged)
            turns.append(turn)
            new_turns.append(turn)
        return new_turns

    async def _generate_turn(
        self, speaker: str, context: DreamContext
    ) -> Tuple[str, bool]:
        """生成单个回合；空文本重试一次，事实断言越界纠正一次。"""
        client = self._dreamer if speaker == SPEAKER_DREAMER else self._director
        temperature = self._temperature(speaker, context.mode)
        messages = self.build_messages(speaker, context)

        text = await self._safe_chat(client, messages, temperature)
        if not text.strip():
            text = await self._safe_chat(client, messages, temperature)
        if not text.strip():
            return DREAM_BROKEN_TEXT, False

        if not check_text(text):
            return text.strip(), False

        correction = list(messages) + [
            Message(role="assistant", content=text.strip()),
            Message(role="user", content=CORRECTION_INSTRUCTION),
        ]
        rewritten = await self._safe_chat(client, correction, temperature)
        if rewritten.strip():
            text = rewritten.strip()
        return text, bool(check_text(text))

    def build_messages(self, speaker: str, context: DreamContext) -> List[Message]:
        """构造发送给 LLM 的 messages：只含素材快照、梦内回合与本轮指令。"""
        system = system_prompt(speaker, context.mode) + "\n\n" + material_block(
            context.material
        )
        messages: List[Message] = [Message(role="system", content=system)]
        recent = context.turns[-max(int(self._config.context_turns), 0) :]
        for turn in recent:
            if turn.speaker == speaker:
                messages.append(Message(role="assistant", content=turn.content))
            else:
                label = SPEAKER_LABELS.get(turn.speaker, turn.speaker)
                messages.append(
                    Message(role="user", content=f"[{label}] {turn.content}")
                )
        last_speaker = recent[-1].speaker if recent else ""
        messages.append(
            Message(
                role="user",
                content=turn_instruction(speaker, bool(recent), last_speaker),
            )
        )
        return messages

    async def _safe_chat(self, client, messages: List[Message], temperature: float) -> str:
        """调用 LLM；异常时返回本地兜底文本，绝不向上抛出。"""
        try:
            result = await client.chat(messages, temperature=temperature)
            return str(result or "")
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - 梦境链路必须自愈
            logger.warning("梦境 LLM 调用失败，使用本地兜底文本: %s", exc)
            system = messages[0].content if messages else ""
            if "【你的身份：潜意识导演】" in system:
                return _DIRECTOR_FALLBACK
            return _DREAMER_FALLBACK

    def _temperature(self, speaker: str, mode: str) -> float:
        if mode == MODE_WILD:
            if speaker == SPEAKER_DREAMER:
                return self._config.wild_dreamer_temperature
            return self._config.wild_director_temperature
        if speaker == SPEAKER_DREAMER:
            return self._config.dreamer_temperature
        return self._config.director_temperature

    # ================================================================ 回合持久化
    async def _append_turn(
        self, session: DreamSession, speaker: str, content: str, flagged: bool
    ) -> Turn:
        turn = await self._store_call(
            self._store.append_turn,
            session.id,
            speaker,
            content,
            flagged,
            self._clock.now().isoformat(),
        )
        await self._emit(
            "dream.turn_added",
            {
                "session_id": session.id,
                "turn": {
                    "seq": turn.seq,
                    "speaker": turn.speaker,
                    "content": turn.content,
                    "flagged": turn.flagged,
                    "created_at": turn.created_at,
                },
            },
        )
        return turn

    # ================================================================ 醒来摘要
    async def _end_with_recall(
        self, session: DreamSession, turns: List[Turn]
    ) -> DreamRecall:
        """结束会话：生成标题与余韵，写入存储并发出完成事件。"""
        title, summary, residue = await self._compose_recall(session, turns)
        session.title = title
        session.summary = summary
        session.emotion_residue = residue
        session.status = STATUS_ENDED
        session.ended_at = self._clock.now().isoformat()
        await self._store_call(
            self._store.end_session,
            session.id,
            title=title,
            summary=summary,
            emotion_residue=residue,
            ended_at=session.ended_at,
        )
        await self._emit_completed(session)
        return DreamRecall.from_session(session)

    async def _compose_recall(
        self, session: DreamSession, turns: List[Turn]
    ) -> Tuple[str, str, Dict[str, float]]:
        """优先由导演客户端生成 JSON 摘要；失败时本地截断降级。"""
        transcript = _transcript(turns)
        if not transcript:
            return (
                "无名之梦",
                "梦还没有成形，就散了。",
                session.material.emotion.clamped().to_dict(),
            )
        messages = [
            Message(role="system", content=_SUMMARY_SYSTEM),
            Message(
                role="user",
                content=(
                    f"【今夜素材】\n{material_block(session.material)}\n\n"
                    f"【梦境全文】\n{transcript[:_truncate_len(self._config.transcript_max_chars)]}"
                ),
            ),
        ]
        raw = await self._safe_chat(self._director, messages, self._config.summary_temperature)
        parsed = _parse_summary(raw)
        if parsed is not None:
            title, summary, residue = parsed
            return (
                _truncate(title, self._config.title_max_chars),
                _truncate(summary, self._config.summary_max_chars),
                residue or session.material.emotion.clamped().to_dict(),
            )
        return self._local_recall(session, turns)

    def _local_recall(
        self, session: DreamSession, turns: List[Turn]
    ) -> Tuple[str, str, Dict[str, float]]:
        """本地降级：取最后一回合的片段，保留素材情绪。"""
        candidates = [t for t in turns if t.speaker == SPEAKER_DREAMER and t.content.strip()]
        if not candidates:
            candidates = [t for t in turns if t.content.strip()]
        text = candidates[-1].content.strip() if candidates else ""
        summary = _truncate(text or "梦醒时只剩下一点潮湿的光。", self._config.summary_max_chars)
        return "无名之梦", summary, session.material.emotion.clamped().to_dict()

    # ================================================================ 内部工具
    async def _load_active(self, session_id: str) -> DreamSession:
        session = await self._store_call(self._store.get_session, session_id)
        if session is None:
            raise SessionNotFound(f"梦境会话不存在: {session_id}")
        if session.status != STATUS_ACTIVE:
            raise SessionEnded("梦境已经结束，不能再继续")
        return session

    def _lock_for(self, session_id: str) -> asyncio.Lock:
        lock = self._locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[session_id] = lock
        return lock

    def _rounds_played(self, turns: Sequence[Turn]) -> int:
        return sum(1 for turn in turns if turn.speaker == SPEAKER_DIRECTOR)

    async def _store_call(self, func, *args, **kwargs):
        """把同步短存储操作放入线程池，避免阻塞事件循环。"""
        return await asyncio.to_thread(func, *args, **kwargs)

    async def _emit(self, event_type: str, data: Dict[str, Any]) -> None:
        try:
            await self._events.emit(event_type, data)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - 事件失败不得影响梦境
            logger.warning("梦境事件推送失败: %s (%s)", event_type, exc)

    async def _emit_completed(self, session: DreamSession) -> None:
        await self._emit(
            "dream.session_completed",
            {
                "session_id": session.id,
                "mode": session.mode,
                "title": session.title,
                "summary": session.summary,
                "status": session.status,
            },
        )


# ------------------------------------------------------------------ 工具函数
def _truncate(text: str, max_chars: int) -> str:
    content = (text or "").strip()
    if len(content) <= max_chars:
        return content
    if max_chars <= 1:
        return content[:max_chars]
    return content[: max_chars - 1] + "…"


def _truncate_len(max_chars: int) -> int:
    return max(int(max_chars), 0)


def _transcript(turns: Sequence[Turn]) -> str:
    lines = []
    for turn in turns:
        label = SPEAKER_LABELS.get(turn.speaker, turn.speaker)
        lines.append(f"[{label}] {turn.content.strip()}")
    return "\n".join(lines).strip()


def _parse_summary(text: str) -> Optional[Tuple[str, str, Dict[str, float]]]:
    """从模型输出中提取 JSON 摘要；失败返回 None。"""
    obj = _extract_json_object(text or "")
    if not isinstance(obj, dict):
        return None
    title = str(obj.get("title") or "").strip()
    summary = str(obj.get("summary") or "").strip()
    if not summary:
        return None
    residue = obj.get("emotion_residue")
    emotion_residue: Dict[str, float] = {}
    if isinstance(residue, dict):
        for key in ("valence", "arousal"):
            try:
                emotion_residue[key] = float(residue.get(key) or 0.0)
            except (TypeError, ValueError):
                emotion_residue[key] = 0.0
    return title or "无名之梦", summary, emotion_residue


def _extract_json_object(text: str) -> Any:
    """剥离代码块后取首个合法 JSON 对象（移植自 CX-O generator）。"""
    fence = re.search(r"```(?:json|JSON)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1)
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (ValueError, TypeError):
        pass
    decoder = json.JSONDecoder()
    index = 0
    length = len(text)
    while index < length:
        if text[index] in "{[":
            try:
                obj, end = decoder.raw_decode(text, index)
                if isinstance(obj, dict):
                    return obj
                index = end
                continue
            except ValueError:
                pass
        index += 1
    return None
