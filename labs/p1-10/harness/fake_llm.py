"""判分专用：脚本化的假 provider。

它不是教学代码，也不要放进你的 agentlab。
它的唯一职责是**按脚本吐出响应**，让 loop 在离线、不花额度、结果可复现的条件下被驱动。

为什么不用真模型：真模型每次回答不同，判据就不成立了。
这里的形状严格照 CONTRACT.md 第 4 节，你的 loop 只消费那几个属性。
"""
from __future__ import annotations

from typing import Any


class _Fn:
    __slots__ = ("name", "arguments")

    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    __slots__ = ("id", "type", "function")

    def __init__(self, id: str, name: str, arguments: str):
        self.id = id
        self.type = "function"
        self.function = _Fn(name, arguments)


class Message:
    """模仿 openai SDK 的 ChatCompletionMessage。"""

    __slots__ = ("role", "content", "tool_calls")

    def __init__(self, content: str | None = None, tool_calls: list[_ToolCall] | None = None):
        self.role = "assistant"
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none: bool = False) -> dict[str, Any]:
        d: dict[str, Any] = {"role": "assistant"}
        if self.content is not None or not exclude_none:
            d["content"] = self.content
        if self.tool_calls is not None or not exclude_none:
            d["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in (self.tool_calls or [])
            ]
        return d


class _Choice:
    __slots__ = ("message",)

    def __init__(self, message: Message):
        self.message = message


class Response:
    __slots__ = ("choices",)

    def __init__(self, message: Message):
        self.choices = [_Choice(message)]


def resp(content: str | None = None, calls: list[tuple[str, str, str]] | None = None) -> Response:
    """一条脚本响应。calls 的每项是 (id, 工具名, arguments 原始字符串)。"""
    tcs = [_ToolCall(i, n, a) for i, n, a in (calls or [])] or None
    return Response(Message(content=content, tool_calls=tcs))


class FakeLLM:
    """按脚本返回；脚本剩最后一条时重复它。"""

    def __init__(self, script: list[Response]):
        if not script:
            raise ValueError("script 不能为空")
        self.script = list(script)
        self.requests: list[list[dict[str, Any]]] = []   # 每次请求的 messages 快照

    @property
    def calls(self) -> int:
        return len(self.requests)

    def with_tools(self, messages, tools=None, **kw):
        # 深拷贝一层：loop 会在返回后继续 append 到自己的 messages 列表，
        # 不拷贝的话快照会被后续追加污染，第 5 条断言就测不准了。
        self.requests.append([dict(m) for m in messages if isinstance(m, dict)] or [dict(m) for m in messages])
        return self.script.pop(0) if len(self.script) > 1 else self.script[0]
