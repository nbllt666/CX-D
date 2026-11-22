"""核心层纯净度与 CX-O 解耦检查。"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "src" / "dreamtalk" / "core"
FORBIDDEN = {"fastapi", "uvicorn", "httpx", "sqlite3", "dotenv", "os"}


def _import_roots(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module.split(".")[0]


def test_core_has_no_infrastructure_imports():
    for path in CORE.glob("*.py"):
        roots = set(_import_roots(path))
        assert not (roots & FORBIDDEN), f"{path.name} 引入了基础设施依赖: {roots & FORBIDDEN}"


def test_core_does_not_read_environment():
    for path in CORE.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "os.environ" not in source
        assert "getenv(" not in source


def test_src_has_no_cxo_runtime_dependency():
    for path in (ROOT / "src").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "from server" not in source
        assert "import server" not in source
        assert "C:\\CX-O" not in source
