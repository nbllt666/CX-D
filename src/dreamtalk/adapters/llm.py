"""LLM 适配器：OpenAI 兼容客户端、离线 Mock、CX-O 模型路由兼容层。"""

from __future__ import annotations

import ipaddress
import json
import logging
from typing import Optional, Sequence
from urllib.parse import urlparse

import httpx

from dreamtalk.adapters.settings import Settings

logger = logging.getLogger(__name__)

_DIRECTOR_LINES = (
    "潮水从天花板上退下去，露出一排倒挂的窗。窗里没有房间，只有缓慢移动的森林。"
    "远处有人叫你的名字，声音却像从水底传来。",
    "走廊尽头的灯忽然全部转向你。墙纸下面有细小的翅膀在扑动，"
    "一张没有地址的明信片从门缝滑进来，落在地板上，慢慢洇出蓝墨水。",
    "站台开始向上升，像被谁提起来的一块布。铁轨之间长出一片麦田，麦穗上挂着钥匙。"
    "风从相反的方向吹，把所有的钟表拨慢了一分钟。",
    "雨从地面往天上落，街角的邮筒慢慢长高。你听见有人在你背后翻动一本很厚的书，"
    "纸页间夹着细小的雷声。",
    "所有的门同时打开，门后是同一个月台。月台上站着一排撑伞的人，伞面上印着不同的天气。",
    "房间开始像抽屉一样被拉开，每一层都装着不同年份的下午。"
    "灰尘在光里悬停，像一群不肯落地的鸟。",
)

_DREAMER_LINES = (
    "我把那张明信片捡起来，纸面像皮肤一样温热。字迹在指尖下重新排列，"
    "变成一条我从未走过的街。我沿着街走下去，路灯一盏盏低头看我。",
    "我伸手碰了碰麦穗上的钥匙，整片田野忽然安静下来。"
    "远处有一扇门在麦浪里开合，我朝它跑去，脚下的土却像水一样漫过脚踝。",
    "我推开那扇没有把手的门，里面是白天的厨房，只是所有东西都浮在半空。"
    "我抓住一只杯子，杯底映出另一片天空。",
    "我走进那排撑伞的人中间，伞面上的天气开始下雨。"
    "我伸手接住一滴，它在我掌心里变成一枚小小的钥匙。",
    "我拉开最底层的抽屉，里面躺着一条没有尽头的河。"
    "我俯身去看，河面映出一个正在醒来的我。",
    "我把雷声揣进口袋，继续沿着月台走。"
    "身后的门一扇接一扇合上，脚步声却始终比我快半步。",
)

_MOCK_SUMMARIES = (
    {
        "title": "倒挂的窗",
        "summary": "潮水退去后，窗里长出一片森林。我一直走到麦田尽头，钥匙在口袋里发烫，像一句还没说出口的话。",
        "emotion_residue": {"valence": 0.2, "arousal": 0.4},
    },
    {
        "title": "月台上的雨",
        "summary": "所有的门同时打开，门后站着撑伞的人。我接住一滴雨，它变成钥匙；再抬头时，月台已经开往另一个年份。",
        "emotion_residue": {"valence": 0.1, "arousal": 0.5},
    },
    {
        "title": "抽屉里的河",
        "summary": "房间像抽屉一样被一层层拉开，最底层躺着一条河。我俯身去看，河面映出一个正在醒来的人。",
        "emotion_residue": {"valence": -0.1, "arousal": 0.3},
    },
)


class MockLLMClient:
    """确定性离线 LLM：无网络也能完整体验双 LLM 梦境。"""

    def __init__(self, seed: int = 0):
        self.calls = 0
        self._seed = seed

    async def chat(self, messages: Sequence, *, temperature: float) -> str:
        self.calls += 1
        system = ""
        for message in messages:
            if getattr(message, "role", "") == "system":
                system = str(getattr(message, "content", "") or "")
                break
        if "梦醒后的记录者" in system:
            summary = _MOCK_SUMMARIES[(self.calls + self._seed) % len(_MOCK_SUMMARIES)]
            return json.dumps(summary, ensure_ascii=False)
        index = (self.calls + self._seed) % len(_DIRECTOR_LINES)
        if "【你的身份：潜意识导演】" in system:
            return _DIRECTOR_LINES[index]
        return _DREAMER_LINES[index]


class OpenAICompatibleClient:
    """OpenAI 兼容的 ``/chat/completions`` 客户端；失败时回退 Mock 文本。"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        fallback: Optional[MockLLMClient] = None,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        trust_env: Optional[bool] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout = timeout
        self._fallback = fallback or MockLLMClient()
        # 测试可注入 MockTransport；生产环境为 None，使用默认网络传输
        self._transport = transport
        # 本地 / 内网 LLM 默认绕过系统代理，避免 Windows 系统代理把 localhost 请求转成 502
        self._trust_env = _should_trust_env(self._base_url) if trust_env is None else bool(trust_env)
        self._resolved_model: Optional[str] = None

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _resolve_model(self) -> str:
        """解析实际模型名；``auto`` 时从 ``/v1/models`` 发现（适配 Docker vLLM）。"""
        if self._model and self._model.strip().lower() != "auto":
            return self._model
        if self._resolved_model:
            return self._resolved_model
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
            trust_env=self._trust_env,
        ) as client:
            response = await client.get(
                f"{self._base_url}/models", headers=self._headers()
            )
            response.raise_for_status()
            data = response.json()
        models = data.get("data") if isinstance(data, dict) else None
        if not models:
            raise ValueError("模型列表为空")
        model_id = str(models[0].get("id") or "").strip()
        if not model_id:
            raise ValueError("模型 ID 为空")
        self._resolved_model = model_id
        logger.info("已从 %s/models 发现模型: %s", self._base_url, model_id)
        return model_id

    async def chat(self, messages: Sequence, *, temperature: float) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": str(getattr(message, "role", "user")),
                    "content": str(getattr(message, "content", "")),
                }
                for message in messages
            ],
            "temperature": float(temperature),
            "stream": False,
        }
        try:
            payload["model"] = await self._resolve_model()
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                trust_env=self._trust_env,
            ) as client:
                response = await client.post(
                    f"{self._base_url}/chat/completions",
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("模型返回了空内容")
            return content
        except Exception as exc:  # noqa: BLE001 - 单回合失败降级，不阻断梦境
            logger.warning("LLM 请求失败，回退离线文本: %s", exc)
            return await self._fallback.chat(messages, temperature=temperature)


class CXOModelRouterAdapter:
    """把 CX-O 的 ``router.get_client(model).chat(...)`` 包装成本项目端口。

    回装 CX-O 时直接注入，无需改动核心编排。
    """

    def __init__(self, router, model: str, fallback: Optional[MockLLMClient] = None):
        self._router = router
        self._model = model
        self._fallback = fallback or MockLLMClient()

    async def chat(self, messages: Sequence, *, temperature: float) -> str:
        try:
            client = self._router.get_client(self._model)
            if client is None:
                raise RuntimeError(f"模型 {self._model} 不可用")
            response = await client.chat(
                messages=[
                    {
                        "role": str(getattr(message, "role", "user")),
                        "content": str(getattr(message, "content", "")),
                    }
                    for message in messages
                ],
                stream=False,
                temperature=float(temperature),
            )
            if getattr(response, "error", None):
                raise RuntimeError(str(response.error))
            content = getattr(response, "content", None)
            if content is None and isinstance(response, str):
                content = response
            if not isinstance(content, str) or not content.strip():
                raise ValueError("模型返回了空内容")
            return content
        except Exception as exc:  # noqa: BLE001
            logger.warning("CX-O 模型路由调用失败，回退离线文本: %s", exc)
            return await self._fallback.chat(messages, temperature=temperature)


def build_clients(settings: Settings):
    """按配置构造梦者 / 导演客户端；Mock 模式下两者均为离线实现。"""
    if settings.is_mock:
        return MockLLMClient(seed=0), MockLLMClient(seed=7)
    dreamer = OpenAICompatibleClient(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.dreamer_model_name,
        timeout=settings.timeout,
        fallback=MockLLMClient(seed=11),
        trust_env=settings.trust_env,
    )
    director = OpenAICompatibleClient(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.director_model_name,
        timeout=settings.timeout,
        fallback=MockLLMClient(seed=17),
        trust_env=settings.trust_env,
    )
    return dreamer, director


def _should_trust_env(base_url: str) -> bool:
    """本地 / 内网地址不读取系统代理；公网地址保持默认行为。

    Windows 系统代理可能把 ``127.0.0.1`` / Docker 服务名的请求转给代理，
    导致本可直连的 vLLM 返回 502。公网 OpenAI 等仍允许使用系统代理。
    """
    try:
        host = (urlparse(base_url).hostname or "").lower()
    except ValueError:
        return True
    if not host:
        return True
    if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0", "host.docker.internal"}:
        return False
    if host.endswith(".local") or host.endswith(".internal"):
        return False
    if "." not in host:
        # Docker / Compose 服务名（如 llm、cxo-llm）没有点号
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        address.is_loopback or address.is_private or address.is_link_local
    )
