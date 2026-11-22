"""``python -m dreamtalk`` 启动入口。"""

from __future__ import annotations

import uvicorn

from dreamtalk.adapters.settings import Settings
from dreamtalk.api import create_app


def main() -> None:
    settings = Settings.from_env()
    app = create_app(settings=settings)
    mode = "Mock（离线）" if settings.is_mock else "LLM"
    print(f"DreamTalk 启动于 http://{settings.host}:{settings.port} · {mode}")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
