"""适配器测试：OpenAI 兼容客户端、CX-O 模型路由兼容层与 Mock 装配。"""

from __future__ import annotations

import json
from types import SimpleNamespace

import httpx

from dreamtalk.adapters.llm import (
    CXOModelRouterAdapter,
    MockLLMClient,
    OpenAICompatibleClient,
    _should_trust_env,
    build_clients,
)
from dreamtalk.adapters.settings import Settings
from dreamtalk.core.models import Message


class _FakeClient:
    def __init__(self, content: str = "来自 CX-O 的梦", error: str | None = None):
        self.content = content
        self.error = error
        self.seen: list[list[dict]] = []
        self.temperature = None

    async def chat(self, messages, stream=False, temperature=0.0):
        self.seen.append(messages)
        self.temperature = temperature
        return SimpleNamespace(content=self.content, error=self.error)


class _FakeRouter:
    def __init__(self, client):
        self.client = client

    def get_client(self, model):
        return self.client


async def test_cxo_router_adapter_maps_messages_and_response():
    client = _FakeClient()
    adapter = CXOModelRouterAdapter(_FakeRouter(client), "summary")
    text = await adapter.chat(
        [Message(role="system", content="你是梦者"), Message(role="user", content="继续")],
        temperature=0.9,
    )
    assert text == "来自 CX-O 的梦"
    assert client.seen[0][0] == {"role": "system", "content": "你是梦者"}
    assert client.temperature == 0.9


async def test_cxo_router_adapter_falls_back_on_error():
    client = _FakeClient(content="", error="boom")
    adapter = CXOModelRouterAdapter(_FakeRouter(client), "summary")
    text = await adapter.chat(
        [Message(role="system", content="【你的身份：梦者】"), Message(role="user", content="继续")],
        temperature=0.9,
    )
    assert text
    assert text != ""


def test_build_clients_uses_mock_when_configured():
    dreamer, director = build_clients(Settings(mock=True))
    assert isinstance(dreamer, MockLLMClient)
    assert isinstance(director, MockLLMClient)


async def test_openai_client_auto_discovers_docker_model():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            return httpx.Response(200, json={"data": [{"id": "qwen-docker"}]})
        if request.url.path == "/v1/chat/completions":
            body = json.loads(request.content)
            seen["model"] = body["model"]
            seen["auth"] = request.headers.get("authorization")
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "潮水退去，窗里长出一片森林。"}}
                    ]
                },
            )
        return httpx.Response(404)

    client = OpenAICompatibleClient(
        base_url="http://llm:8080/v1",
        api_key="local",
        model="auto",
        transport=httpx.MockTransport(handler),
    )
    text = await client.chat(
        [Message(role="system", content="你是梦者"), Message(role="user", content="开始")],
        temperature=0.9,
    )
    assert text.startswith("潮水")
    assert seen["model"] == "qwen-docker"
    assert seen["auth"] == "Bearer local"


async def test_openai_client_falls_back_when_service_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "starting"})

    client = OpenAICompatibleClient(
        base_url="http://llm:8080/v1",
        api_key="local",
        model="auto",
        transport=httpx.MockTransport(handler),
    )
    text = await client.chat(
        [Message(role="system", content="【你的身份：梦者】"), Message(role="user", content="继续")],
        temperature=0.9,
    )
    assert text.startswith(("我把", "我伸手", "我推开"))


def test_local_llm_bypasses_system_proxy():
    assert _should_trust_env("http://127.0.0.1:8080/v1") is False
    assert _should_trust_env("http://localhost:8080/v1") is False
    assert _should_trust_env("http://llm:8080/v1") is False
    assert _should_trust_env("http://host.docker.internal:8080/v1") is False
    assert _should_trust_env("http://192.168.1.10:8080/v1") is False
    assert _should_trust_env("https://api.openai.com/v1") is True
