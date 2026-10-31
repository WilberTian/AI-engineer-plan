"""判分器体检：把并发、超时、复用各改坏一处。

    python3 labs/p1-3/tools/self_test.py

跑得慢（约 30 秒）——每个 mutation 都要真等一遍。这是这张卡的代价：
结论建立在时间上，就没法只查代码。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import self_test  # noqa: E402

from verify_reference import build  # noqa: E402

GATHER = "        await asyncio.gather(*(fake_llm(client, i) for i in range(n)))"

MUTATIONS = [
    (
        "fake_llm 里改成 time.sleep（卡住事件循环）",
        "    await asyncio.sleep(0.8)",
        "    time.sleep(0.8)",
        "async 里没有 time.sleep",
    ),
    (
        "gather 改成顺序 await（并发变串行）",
        GATHER,
        "        for i in range(n):\n            await fake_llm(client, i)",
        "并发只等一次",
    ),
    (
        "超时阈值放到 10 秒（等于没有超时）",
        "        async with asyncio.timeout(0.3):",
        "        async with asyncio.timeout(10):",
        "超时被拦住",
    ),
    (
        "except 写错异常类型（TimeoutError 漏出去）",
        "    except TimeoutError:",
        "    except ZeroDivisionError:",
        "超时被拦住",
    ),
    (
        "并发时 idx 写死成 0",
        "        await asyncio.gather(*(fake_llm(client, i) for i in range(n)))",
        "        await asyncio.gather(*(fake_llm(client, 0) for _ in range(n)))",
        "并发保序",
    ),
    (
        "serial 每轮都新建 client（放弃连接复用）",
        "    async with httpx.AsyncClient() as client:\n        for i in range(n):\n            await fake_llm(client, i)",
        "    for i in range(n):\n        async with httpx.AsyncClient() as client:\n            await fake_llm(client, i)",
        "client 只建一个",
    ),
    (
        "并发时把异常吞掉",
        GATHER,
        "        try:\n            await asyncio.gather(*(fake_llm(client, i) for i in range(n)))\n        except Exception:\n            pass",
        "异常不被吞掉",
    ),
]


def main() -> int:
    return self_test(page="stage-p1.html", card="p1-3", lab=LAB, build=build, mutations=MUTATIONS)


if __name__ == "__main__":
    sys.exit(main())
