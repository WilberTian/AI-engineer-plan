"""证明「参考实现能过判分」。代码从 stage-p1.html 现抽。

    python3 labs/p1-8/tools/verify_reference.py

夹具铺三样：
    openai.py             替身 SDK：按参数抛不同形状的异常，并记录每次调用
    agentlab/config.py    PRIMARY（api_key / base_url / model）
    scripts/error_probe.py  被判对象

参考实现目前是**全绿**的（11/11）。

Fix 记录（2026-10-31）：原先 `create(model=..., messages=[], **kwargs)` 把 `messages`
写成固定参数，而五次探测又都传了 `messages=...`，于是五次全部变成
`TypeError: got multiple values for keyword argument 'messages'`，一次都没真正调到 SDK。
现已改为 `kwargs.setdefault("messages", [])` + `kwargs.setdefault("model", PRIMARY.model)`，
默认值在函数里给、调用方传了就以调用方为准。这段教训留在
`stage-p1.html#p1-8` 的代码注释里，别再改回去。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import verify_reference  # noqa: E402

# 手册修好后这里应该为空；一旦又红了，把条目名填回来，
# 让它在输出里明确报「已知偏差命中」而不是假装全绿。
KNOWN_RED: list[str] = []

OPENAI_STUB = '''"""判分夹具：openai 替身。按参数抛不同形状的异常，并记录每次调用。"""
from __future__ import annotations

CALLS: list[dict] = []
RAISE = True
PRIMARY_MODEL = "gpt-4.1-mini"


class StatusError(Exception):
    def __init__(self, message: str, status: int) -> None:
        super().__init__(message)
        self.status_code = status


class _Completions:
    def create(self, *, model=None, messages=None, **kw):
        CALLS.append({"model": model, "messages": messages, **kw})
        if not RAISE:
            return {"choices": [{"message": {"content": "ok"}}]}

        max_tokens = kw.get("max_tokens")
        if isinstance(max_tokens, int) and max_tokens < 0:
            # 参数校验类错误：没有 status_code
            raise ValueError("max_tokens must be greater than 0")

        if model != PRIMARY_MODEL:
            raise StatusError(f"The model `{model}` does not exist", 404)

        text = str(messages)
        if "image_url" in text:
            raise StatusError("invalid image url: failed to fetch", 400)
        if text.count("啊") > 1000:
            # 超长错误体：整页响应体都会塞进 message
            raise StatusError("context_length_exceeded: " + "啊" * 500, 400)
        if not messages:
            raise StatusError("messages must not be empty", 400)

        raise StatusError("unexpected request", 400)


class _Chat:
    def __init__(self) -> None:
        self.completions = _Completions()


class OpenAI:
    def __init__(self, api_key=None, base_url=None) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.chat = _Chat()
'''

CONFIG = '''"""判分夹具：PRIMARY。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    api_key: str
    base_url: str
    model: str


PRIMARY = Provider(api_key="sk-stub", base_url="https://stub.invalid/v1",
                   model="gpt-4.1-mini")
'''


def build(tmp: Path, code: str) -> None:
    (tmp / "scripts").mkdir()
    (tmp / "agentlab").mkdir()
    (tmp / "scripts" / "error_probe.py").write_text(code, encoding="utf-8")
    (tmp / "openai.py").write_text(OPENAI_STUB, encoding="utf-8")
    (tmp / "agentlab" / "__init__.py").write_text("", encoding="utf-8")
    (tmp / "agentlab" / "config.py").write_text(CONFIG, encoding="utf-8")


def main() -> int:
    return verify_reference(
        page="stage-p1.html", card="p1-8", lab=LAB, build=build, expect_red=KNOWN_RED,
    )


if __name__ == "__main__":
    sys.exit(main())
