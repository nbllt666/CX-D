"""DreamTalk 领域异常：由 API 层映射为 HTTP 状态码。"""

from __future__ import annotations


class DreamTalkError(Exception):
    """领域异常基类。"""

    status_code = 400


class SessionNotFound(DreamTalkError):
    """会话不存在。"""

    status_code = 404


class SessionEnded(DreamTalkError):
    """会话已结束，不能继续推进或重复醒来。"""

    status_code = 409


class NoMemoryMaterial(DreamTalkError):
    """记忆梦缺少当天记忆素材。"""

    status_code = 422


class InvalidMode(DreamTalkError):
    """非法模式。"""

    status_code = 422
