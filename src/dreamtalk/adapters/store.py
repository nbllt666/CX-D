"""会话存储适配器：SQLite 短连接实现与测试用内存实现。"""

from __future__ import annotations

import copy
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dreamtalk.core.models import (
    STATUS_ENDED,
    DreamSession,
    Emotion,
    MemoryMaterial,
    Turn,
)


class SQLiteSessionStore:
    """会话/回合 SQLite 存储。

    每个公开方法使用独立短连接（沿用 CX-O ``buffer.py`` 模式），
    避免跨线程共享连接；数据库与主业务数据完全隔离。
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # -------------------------------------------------------------- 连接
    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=20.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    mode_reason TEXT,
                    status TEXT NOT NULL,
                    seeds_json TEXT,
                    entities_json TEXT,
                    emotion_json TEXT,
                    material_source TEXT DEFAULT 'manual',
                    title TEXT,
                    summary TEXT,
                    emotion_residue_json TEXT,
                    ended_at TEXT
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    speaker TEXT NOT NULL,
                    content TEXT NOT NULL,
                    flagged INTEGER DEFAULT 0,
                    created_at TEXT,
                    UNIQUE(session_id, seq)
                );
                CREATE INDEX IF NOT EXISTS idx_turns_session
                    ON turns(session_id, seq);
                CREATE INDEX IF NOT EXISTS idx_sessions_created
                    ON sessions(created_at DESC);
                """
            )
            conn.commit()
        finally:
            conn.close()

    # -------------------------------------------------------------- 会话
    def create_session(self, session: DreamSession) -> None:
        material = session.material
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO sessions (
                    id, created_at, mode, mode_reason, status,
                    seeds_json, entities_json, emotion_json, material_source,
                    title, summary, emotion_residue_json, ended_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.created_at,
                    session.mode,
                    session.mode_reason,
                    session.status,
                    _dump_json(material.day_memories),
                    _dump_json(material.entities),
                    _dump_json(material.emotion.clamped().to_dict()),
                    material.source,
                    session.title,
                    session.summary,
                    _dump_json(session.emotion_residue),
                    session.ended_at,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def get_session(self, session_id: str) -> Optional[DreamSession]:
        conn = self._connect()
        try:
            row = conn.execute(
                """
                SELECT s.*, (
                    SELECT COUNT(*) FROM turns t WHERE t.session_id = s.id
                ) AS turn_count
                FROM sessions s WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()
            return _row_to_session(row) if row else None
        finally:
            conn.close()

    def list_sessions(self, limit: int = 20) -> List[DreamSession]:
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT s.*, (
                    SELECT COUNT(*) FROM turns t WHERE t.session_id = s.id
                ) AS turn_count
                FROM sessions s
                ORDER BY s.created_at DESC, s.rowid DESC
                LIMIT ?
                """,
                (max(int(limit), 0),),
            ).fetchall()
            return [_row_to_session(row) for row in rows]
        finally:
            conn.close()

    # -------------------------------------------------------------- 回合
    def append_turn(
        self,
        session_id: str,
        speaker: str,
        content: str,
        flagged: bool = False,
        created_at: str = "",
    ) -> Turn:
        created = created_at or datetime.now().isoformat()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 AS next_seq FROM turns WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            seq = int(row["next_seq"])
            conn.execute(
                """
                INSERT INTO turns (session_id, seq, speaker, content, flagged, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, seq, speaker, content, 1 if flagged else 0, created),
            )
            conn.commit()
            return Turn(
                seq=seq,
                speaker=speaker,
                content=content,
                flagged=bool(flagged),
                created_at=created,
            )
        finally:
            conn.close()

    def get_turns(self, session_id: str) -> List[Turn]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT seq, speaker, content, flagged, created_at "
                "FROM turns WHERE session_id = ? ORDER BY seq ASC",
                (session_id,),
            ).fetchall()
            return [
                Turn(
                    seq=int(row["seq"]),
                    speaker=row["speaker"],
                    content=row["content"],
                    flagged=bool(row["flagged"]),
                    created_at=row["created_at"] or "",
                )
                for row in rows
            ]
        finally:
            conn.close()

    # -------------------------------------------------------------- 结束与查询
    def end_session(
        self,
        session_id: str,
        *,
        title: str,
        summary: str,
        emotion_residue: Dict[str, float],
        ended_at: str,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """
                UPDATE sessions
                SET status = ?, title = ?, summary = ?,
                    emotion_residue_json = ?, ended_at = ?
                WHERE id = ?
                """,
                (
                    STATUS_ENDED,
                    title,
                    summary,
                    _dump_json(emotion_residue),
                    ended_at,
                    session_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def last_mode(self) -> Optional[str]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT mode FROM sessions ORDER BY created_at DESC, rowid DESC LIMIT 1"
            ).fetchone()
            return row["mode"] if row else None
        finally:
            conn.close()


class MemorySessionStore:
    """内存存储：用于测试与无 HTTP 嵌入演示。"""

    def __init__(self):
        self._lock = threading.RLock()
        self._sessions: Dict[str, DreamSession] = {}
        self._turns: Dict[str, List[Turn]] = {}
        self._order: List[str] = []

    def create_session(self, session: DreamSession) -> None:
        with self._lock:
            self._sessions[session.id] = copy.deepcopy(session)
            self._turns[session.id] = []
            self._order.append(session.id)

    def get_session(self, session_id: str) -> Optional[DreamSession]:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            result = copy.deepcopy(session)
            result.turn_count = len(self._turns.get(session_id, []))
            return result

    def list_sessions(self, limit: int = 20) -> List[DreamSession]:
        with self._lock:
            ids = list(reversed(self._order))[: max(int(limit), 0)]
            return [self.get_session(session_id) for session_id in ids if session_id in self._sessions]

    def append_turn(
        self,
        session_id: str,
        speaker: str,
        content: str,
        flagged: bool = False,
        created_at: str = "",
    ) -> Turn:
        with self._lock:
            turns = self._turns.setdefault(session_id, [])
            turn = Turn(
                seq=len(turns) + 1,
                speaker=speaker,
                content=content,
                flagged=bool(flagged),
                created_at=created_at or datetime.now().isoformat(),
            )
            turns.append(turn)
            return copy.deepcopy(turn)

    def get_turns(self, session_id: str) -> List[Turn]:
        with self._lock:
            return [copy.deepcopy(turn) for turn in self._turns.get(session_id, [])]

    def end_session(
        self,
        session_id: str,
        *,
        title: str,
        summary: str,
        emotion_residue: Dict[str, float],
        ended_at: str,
    ) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return
            session.status = STATUS_ENDED
            session.title = title
            session.summary = summary
            session.emotion_residue = dict(emotion_residue or {})
            session.ended_at = ended_at

    def last_mode(self) -> Optional[str]:
        with self._lock:
            if not self._order:
                return None
            session = self._sessions.get(self._order[-1])
            return session.mode if session else None


# ------------------------------------------------------------------ 工具
def _dump_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _load_json(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    return value


def _row_to_session(row: sqlite3.Row) -> DreamSession:
    emotion_raw = _load_json(row["emotion_json"]) or {}
    if not isinstance(emotion_raw, dict):
        emotion_raw = {}
    memory_raw = _load_json(row["seeds_json"]) or []
    entity_raw = _load_json(row["entities_json"]) or []
    residue_raw = _load_json(row["emotion_residue_json"]) or {}
    return DreamSession(
        id=row["id"],
        created_at=row["created_at"],
        mode=row["mode"],
        mode_reason=row["mode_reason"] or "",
        status=row["status"],
        material=MemoryMaterial(
            day_memories=[str(item) for item in memory_raw if str(item).strip()],
            entities=[str(item) for item in entity_raw if str(item).strip()],
            emotion=Emotion(
                valence=_to_float(emotion_raw.get("valence"), 0.0),
                arousal=_to_float(emotion_raw.get("arousal"), 0.0),
            ),
            source=row["material_source"] or "manual",
        ),
        title=row["title"] or "",
        summary=row["summary"] or "",
        emotion_residue={
            str(key): _to_float(value, 0.0)
            for key, value in (residue_raw.items() if isinstance(residue_raw, dict) else [])
        },
        ended_at=row["ended_at"],
        turn_count=int(row["turn_count"] or 0),
    )


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
