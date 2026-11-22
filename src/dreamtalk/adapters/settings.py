"""环境配置适配器：把 ``DREAMTALK_*`` 环境变量映射为纯数据 Settings。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Mapping, Optional

from dreamtalk.core.dialogue import DialogueConfig
from dreamtalk.core.modes import ModeWeights

_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_MODEL = "gpt-4o-mini"
_TRUTHY = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    """运行期配置；由环境变量适配器构造，也可在代码中直接实例化。"""

    base_url: str = _DEFAULT_BASE_URL
    api_key: str = ""
    model: str = _DEFAULT_MODEL
    dreamer_model: str = ""
    director_model: str = ""
    mock: bool = False
    max_rounds: int = 8
    context_turns: int = 16
    data_dir: str = "data"
    mode_weights: ModeWeights = field(default_factory=ModeWeights)
    timeout: float = 60.0
    trust_env: Optional[bool] = None
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def is_mock(self) -> bool:
        """未配置密钥或显式要求 Mock 时，整个服务进入离线模式。"""
        return bool(self.mock or not self.api_key.strip())

    @property
    def dreamer_model_name(self) -> str:
        return self.dreamer_model.strip() or self.model.strip() or _DEFAULT_MODEL

    @property
    def director_model_name(self) -> str:
        return self.director_model.strip() or self.model.strip() or _DEFAULT_MODEL

    def dialogue_config(self) -> DialogueConfig:
        return DialogueConfig(
            max_rounds=self.max_rounds,
            context_turns=self.context_turns,
        )

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "Settings":
        """从环境变量（或显式映射）读取配置；非法数值回退默认。"""
        if env is None:
            try:
                from dotenv import load_dotenv

                load_dotenv()
            except Exception:  # noqa: BLE001 - 缺少 dotenv 时仍可读系统环境
                pass
            source: Mapping[str, str] = os.environ
        else:
            source = env

        def get(name: str, default: str = "") -> str:
            return str(source.get(name, default) or "").strip()

        return cls(
            base_url=(get("DREAMTALK_BASE_URL", _DEFAULT_BASE_URL).rstrip("/") or _DEFAULT_BASE_URL),
            api_key=get("DREAMTALK_API_KEY"),
            model=get("DREAMTALK_MODEL", _DEFAULT_MODEL) or _DEFAULT_MODEL,
            dreamer_model=get("DREAMTALK_DREAMER_MODEL"),
            director_model=get("DREAMTALK_DIRECTOR_MODEL"),
            mock=get("DREAMTALK_MOCK").lower() in _TRUTHY,
            max_rounds=_parse_int(get("DREAMTALK_MAX_ROUNDS"), 8, minimum=1),
            context_turns=_parse_int(get("DREAMTALK_CONTEXT_TURNS"), 16, minimum=0),
            data_dir=get("DREAMTALK_DATA_DIR", "data") or "data",
            mode_weights=_parse_mode_weights(get("DREAMTALK_MODE_WEIGHTS")),
            timeout=_parse_float(get("DREAMTALK_TIMEOUT"), 60.0, minimum=1.0),
            trust_env=_parse_optional_bool(get("DREAMTALK_TRUST_ENV")),
            host=get("DREAMTALK_HOST", "127.0.0.1") or "127.0.0.1",
            port=_parse_int(get("DREAMTALK_PORT"), 8000, minimum=1, maximum=65535),
        )


def _parse_int(raw: str, default: int, *, minimum: int = 0, maximum: Optional[int] = None) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    if maximum is not None and value > maximum:
        return default
    return value


def _parse_float(raw: str, default: float, *, minimum: float = 0.0) -> float:
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if value >= minimum else default


def _parse_optional_bool(raw: str) -> Optional[bool]:
    """auto / 空 → None（由客户端按地址自动判断）；1/0 显式覆盖。"""
    value = str(raw or "").strip().lower()
    if value in _TRUTHY:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _parse_mode_weights(raw: str) -> ModeWeights:
    """解析 ``memory=0.5,wild=0.3,dreamless=0.2``；全空/非法回退默认。"""
    if not raw:
        return ModeWeights()
    values: Dict[str, float] = {}
    for part in raw.split(","):
        if "=" not in part:
            continue
        key, raw_value = part.split("=", 1)
        key = key.strip().lower()
        if key not in {"memory", "wild", "dreamless"}:
            continue
        try:
            values[key] = float(raw_value.strip())
        except (TypeError, ValueError):
            continue
    if not values or sum(max(v, 0.0) for v in values.values()) <= 0:
        return ModeWeights()
    return ModeWeights(
        memory=values.get("memory", 0.0),
        wild=values.get("wild", 0.0),
        dreamless=values.get("dreamless", 0.0),
    ).sanitized()
