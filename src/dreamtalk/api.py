"""FastAPI 适配层：梦境面（档案）与清醒面（摘要）分离。"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from dreamtalk import CONTRACT_VERSION
from dreamtalk.adapters.llm import build_clients
from dreamtalk.adapters.settings import Settings
from dreamtalk.adapters.store import SQLiteSessionStore
from dreamtalk.core.errors import DreamTalkError
from dreamtalk.core.models import (
    MODE_LABELS,
    DreamRecall,
    DreamSession,
    Emotion,
    SessionView,
    Turn,
    mode_label,
)
from dreamtalk.service import DreamTalkService


class EmotionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valence: float = 0.0
    arousal: float = 0.0


class StartSessionRequest(BaseModel):
    """入睡请求：只接受本次记忆素材，拒绝任何梦外上下文注入字段。"""

    model_config = ConfigDict(extra="forbid")

    day_memories: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    emotion: Optional[EmotionIn] = None
    mode: str = "auto"


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = ""


def create_app(
    service: Optional[DreamTalkService] = None,
    *,
    settings: Optional[Settings] = None,
) -> FastAPI:
    """构建 FastAPI 应用；测试可注入自定义 service/settings。"""
    settings = settings or Settings.from_env()
    service = service or build_service(settings)

    app = FastAPI(title="DreamTalk", version=CONTRACT_VERSION)
    app.state.service = service
    app.state.settings = settings

    @app.exception_handler(DreamTalkError)
    async def _dreamtalk_error_handler(_: Request, exc: DreamTalkError):
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "mock": settings.is_mock,
            "contract_version": CONTRACT_VERSION,
            "modes": MODE_LABELS,
            "llm": {
                "base_url": settings.base_url,
                "model": settings.model,
                "dreamer_model": settings.dreamer_model_name,
                "director_model": settings.director_model_name,
            },
        }

    @app.post("/api/sessions")
    async def start_session(body: StartSessionRequest):
        emotion = (
            Emotion(valence=body.emotion.valence, arousal=body.emotion.arousal)
            if body.emotion is not None
            else Emotion()
        )
        view = await service.start_session(
            day_memories=body.day_memories,
            entities=body.entities,
            emotion=emotion,
            mode=body.mode or "auto",
        )
        return _view_dict(view)

    @app.get("/api/sessions")
    async def list_sessions():
        sessions = await service.list_sessions(limit=20)
        items = [_session_dict(session) for session in sessions]
        return {"items": items, "total": len(items)}

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str):
        view = await service.get_session(session_id)
        return _view_dict(view)

    @app.post("/api/sessions/{session_id}/message")
    async def post_message(session_id: str, body: MessageRequest):
        view = await service.interject(session_id, body.content)
        return _view_dict(view)

    @app.post("/api/sessions/{session_id}/wake")
    async def wake(session_id: str):
        view = await service.wake(session_id)
        return _view_dict(view)

    @app.get("/api/sessions/{session_id}/recall")
    async def get_recall(session_id: str):
        return _recall_dict(await service.get_recall(session_id))

    @app.get("/api/recall")
    async def list_recalls():
        recalls = await service.list_recalls(limit=20)
        return {"items": [_recall_dict(recall) for recall in recalls], "total": len(recalls)}

    web_dir = Path(__file__).resolve().parents[2] / "web"
    if web_dir.exists():
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")

    return app


def build_service(settings: Settings) -> DreamTalkService:
    """按配置装配服务：SQLite 存储 + 双 LLM 客户端 + 手动记忆源。"""
    dreamer, director = build_clients(settings)
    store = SQLiteSessionStore(Path(settings.data_dir) / "dreamtalk.db")
    return DreamTalkService(
        dreamer=dreamer,
        director=director,
        store=store,
        dialogue_config=settings.dialogue_config(),
        mode_weights=settings.mode_weights,
    )


# ------------------------------------------------------------------ 序列化
def _view_dict(view: SessionView) -> dict:
    payload = {
        "session": _session_dict(view.session),
        "turns": [_turn_dict(turn) for turn in view.turns],
    }
    if view.recall is not None:
        payload["recall"] = _recall_dict(view.recall)
    return payload


def _session_dict(session: DreamSession) -> dict:
    return {
        "id": session.id,
        "created_at": session.created_at,
        "contract_version": CONTRACT_VERSION,
        "mode": session.mode,
        "mode_label": mode_label(session.mode),
        "mode_reason": session.mode_reason,
        "status": session.status,
        "day_memories": list(session.material.day_memories),
        "entities": list(session.material.entities),
        "emotion": session.material.emotion.clamped().to_dict(),
        "material_source": session.material.source,
        "title": session.title,
        "summary": session.summary,
        "emotion_residue": dict(session.emotion_residue or {}),
        "ended_at": session.ended_at,
        "turn_count": session.turn_count,
    }


def _turn_dict(turn: Turn) -> dict:
    return {
        "seq": turn.seq,
        "speaker": turn.speaker,
        "content": turn.content,
        "flagged": turn.flagged,
        "created_at": turn.created_at,
    }


def _recall_dict(recall: DreamRecall) -> dict:
    return {
        "session_id": recall.session_id,
        "created_at": recall.created_at,
        "mode": recall.mode,
        "title": recall.title,
        "summary": recall.summary,
        "emotion_residue": dict(recall.emotion_residue or {}),
    }
