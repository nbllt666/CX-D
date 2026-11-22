"""环境配置解析测试。"""

from __future__ import annotations

from dreamtalk.adapters.settings import Settings


def test_env_parsing_and_defaults():
    settings = Settings.from_env(
        {
            "DREAMTALK_API_KEY": "key",
            "DREAMTALK_BASE_URL": "https://example.com/v1/",
            "DREAMTALK_MAX_ROUNDS": "3",
            "DREAMTALK_CONTEXT_TURNS": "6",
            "DREAMTALK_MODE_WEIGHTS": "memory=1,wild=0,dreamless=0",
            "DREAMTALK_TIMEOUT": "12.5",
            "DREAMTALK_HOST": "0.0.0.0",
            "DREAMTALK_PORT": "9000",
        }
    )
    assert settings.is_mock is False
    assert settings.base_url == "https://example.com/v1"
    assert settings.max_rounds == 3
    assert settings.context_turns == 6
    assert settings.mode_weights.memory == 1.0
    assert settings.mode_weights.wild == 0.0
    assert settings.timeout == 12.5
    assert settings.host == "0.0.0.0"
    assert settings.port == 9000


def test_invalid_values_fall_back():
    settings = Settings.from_env(
        {
            "DREAMTALK_MAX_ROUNDS": "abc",
            "DREAMTALK_CONTEXT_TURNS": "-2",
            "DREAMTALK_PORT": "99999",
            "DREAMTALK_MODE_WEIGHTS": "memory=0,wild=0,dreamless=0",
        }
    )
    assert settings.max_rounds == 8
    assert settings.context_turns == 16
    assert settings.port == 8000
    assert settings.mode_weights.memory == 0.5


def test_missing_key_enters_mock():
    settings = Settings.from_env({})
    assert settings.is_mock is True

    forced = Settings.from_env({"DREAMTALK_API_KEY": "key", "DREAMTALK_MOCK": "1"})
    assert forced.is_mock is True


def test_auto_model_is_kept_for_discovery():
    settings = Settings.from_env(
        {"DREAMTALK_API_KEY": "local", "DREAMTALK_MODEL": "auto"}
    )
    assert settings.is_mock is False
    assert settings.model == "auto"
    assert settings.dreamer_model_name == "auto"


def test_trust_env_override():
    assert Settings.from_env({"DREAMTALK_API_KEY": "k"}).trust_env is None
    assert (
        Settings.from_env({"DREAMTALK_API_KEY": "k", "DREAMTALK_TRUST_ENV": "0"}).trust_env
        is False
    )
    assert (
        Settings.from_env({"DREAMTALK_API_KEY": "k", "DREAMTALK_TRUST_ENV": "1"}).trust_env
        is True
    )


def test_role_model_overrides():
    settings = Settings.from_env(
        {
            "DREAMTALK_API_KEY": "key",
            "DREAMTALK_MODEL": "base-model",
            "DREAMTALK_DREAMER_MODEL": "dreamer-model",
        }
    )
    assert settings.dreamer_model_name == "dreamer-model"
    assert settings.director_model_name == "base-model"
