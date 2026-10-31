"""证明「参考实现能过判分」。代码从 stage-p1.html 现抽。

    python3 labs/p1-3/tools/verify_reference.py

夹具另铺一个 `httpx` 替身：本卡的 `fake_llm` 用不到 client，
只需要一个能 `async with` 的对象。同时它数「建了几个 client」，
用来判「连接池有没有被复用」。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402

HTTPX_STUB = '''"""判分夹具：httpx 替身。数一下建了几个连接池。"""
from __future__ import annotations


class AsyncClient:
    made = 0

    def __init__(self, *args, **kwargs) -> None:
        AsyncClient.made += 1

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info) -> bool:
        return False

    async def get(self, *args, **kwargs):
        raise RuntimeError("夹具不提供网络")
'''


def build(tmp: Path, code: str) -> None:
    (tmp / "scripts").mkdir()
    (tmp / "scripts" / "async_demo.py").write_text(code, encoding="utf-8")
    (tmp / "httpx.py").write_text(HTTPX_STUB, encoding="utf-8")


def main() -> int:
    return verify_reference(page="stage-p1.html", card="p1-3", lab=LAB, build=build)


if __name__ == "__main__":
    sys.exit(main())
