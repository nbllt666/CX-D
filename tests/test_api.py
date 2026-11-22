"""FastAPI 接口测试：梦境面 / 清醒面分离与错误码。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dreamtalk.adapters.llm import MockLLMClient
from dreamtalk.adapters.settings import Settings
from dreamtalk.adapters.store import MemorySessionStore
from dreamtalk.api import create_app
from dreamtalk.core.dialogue import DialogueConfig
from dreamtalk.core.modes import ModeWeights
from dreamtalk.service import DreamTalkService
from tests.conftest import CollectingEvents, FixedClock, FixedRandom

RECALL_KEYS = {
    "session_id",
    "created_at",
    "mode",
    "title",
    "summary",
    "emotion_residue",
}


@pytest.fixture()
def api(tmp_path):
    settings = Settings(mock=True, data_dir=str(tmp_path))
    dreamer = MockLLMClient(seed=0)
    director = MockLLMClient(seed=7)
    service = DreamTalkService(
        dreamer=dreamer,
        director=director,
        store=MemorySessionStore(),
        rng=FixedRandom(0.0),
        clock=FixedClock(),
        events=CollectingEvents(),
        dialogue_config=DialogueConfig(max_rounds=8),
        mode_weights=ModeWeights(),
    )
    app = create_app(service, settings=settings)
    with TestClient(app) as client:
        yield client, dreamer, director


def test_health(api):
    client, _, _ = api
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mock"] is True
    assert data["contract_version"] == "1.0"
    assert data["llm"]["model"] == "gpt-4o-mini"


def test_full_memory_dream_flow(api):
    client, _, _ = api
    response = client.post(
        "/api/sessions",
        json={"day_memories": ["便利店的旧歌", "窗台的灰"], "mode": "memory"},
    )
    assert response.status_code == 200
    data = response.json()
    session = data["session"]
    session_id = session["id"]
    assert session["mode"] == "memory"
    assert session["mode_label"] == "记忆梦"
    assert session["contract_version"] == "1.0"
    assert session["status"] == "active"
    assert [turn["speaker"] for turn in data["turns"]] == ["director", "dreamer"]
    assert all(turn["seq"] for turn in data["turns"])

    response = client.post(
        f"/api/sessions/{session_id}/message", json={"content": "我伸手推开那扇门"}
    )
    assert response.status_code == 200
    turns = response.json()["turns"]
    assert [turn["speaker"] for turn in turns[-3:]] == [
        "awakened",
        "director",
        "dreamer",
    ]

    response = client.post(f"/api/sessions/{session_id}/wake")
    assert response.status_code == 200
    woken = response.json()
    assert woken["session"]["status"] == "ended"
    assert woken["recall"]["session_id"] == session_id
    assert woken["session"]["summary"]

    response = client.get(f"/api/sessions/{session_id}/recall")
    assert response.status_code == 200
    assert set(response.json()) == RECALL_KEYS

    response = client.get("/api/recall")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert set(payload["items"][0]) == RECALL_KEYS

    response = client.get("/api/sessions")
    items = response.json()["items"]
    assert items and "turns" not in items[0]

    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    archive = response.json()
    assert archive["turns"]
    assert archive["recall"]["session_id"] == session_id


def test_dreamless_api(api):
    client, dreamer, director = api
    response = client.post(
        "/api/sessions", json={"day_memories": [], "mode": "dreamless"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["turns"] == []
    assert data["session"]["status"] == "ended"
    assert data["session"]["mode"] == "dreamless"
    assert data["session"]["summary"]
    assert data["recall"]["title"] == "一夜无梦"
    assert dreamer.calls == 0 and director.calls == 0


def test_error_codes(api):
    client, _, _ = api

    response = client.post("/api/sessions", json={"day_memories": [], "mode": "memory"})
    assert response.status_code == 422

    response = client.post("/api/sessions", json={"day_memories": [], "mode": "normal"})
    assert response.status_code == 422

    response = client.post(
        "/api/sessions",
        json={"day_memories": ["a"], "mode": "memory", "waking_history": "外部上下文"},
    )
    assert response.status_code == 422

    assert client.get("/api/sessions/missing").status_code == 404
    assert client.get("/api/sessions/missing/recall").status_code == 404

    response = client.post(
        "/api/sessions", json={"day_memories": ["a"], "mode": "memory"}
    )
    session_id = response.json()["session"]["id"]
    assert client.get(f"/api/sessions/{session_id}/recall").status_code == 409
    assert client.post(f"/api/sessions/{session_id}/wake").status_code == 200
    assert client.post(f"/api/sessions/{session_id}/wake").status_code == 409
    assert (
        client.post(
            f"/api/sessions/{session_id}/message", json={"content": "继续"}
        ).status_code
        == 409
    )


def test_static_chat_page(api):
    client, _, _ = api
    response = client.get("/")
    assert response.status_code == 200
    assert "DreamTalk" in response.text
