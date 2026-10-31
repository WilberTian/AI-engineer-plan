"""判分器体检：往 cost.py 里塞已知算术错。

    python3 labs/p4-8/tools/self_test.py

6 个 mutation 全是「数字会静默变错」的那类——不报错，只是成本不对。
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from refkit import self_test  # noqa: E402

from verify_reference import build  # noqa: E402

MUTATIONS = [
    (
        "除数写成 1000（成本虚高 1000 倍）",
        "        ) / 1_000_000",
        "        ) / 1_000",
        "单位是百万 token（不是每千）",
    ),
    (
        "缓存部分不从 input 里扣",
        "        fresh = max(0, self.input_tokens - self.cached_tokens)",
        "        fresh = self.input_tokens",
        "缓存部分从 input 里扣掉再按缓存价算",
    ),
    (
        "缓存部分不单独计价（按全价算）",
        '        return (\n            fresh * p["in"] + self.cached_tokens * p["cached_in"] + self.output_tokens * p["out"]\n        ) / 1_000_000',
        '        return (\n            fresh * p["in"] + self.cached_tokens * p["in"] + self.output_tokens * p["out"]\n        ) / 1_000_000',
        "全部命中缓存时只算缓存价",
    ),
    (
        "不夹住负数（cached > input 出负成本）",
        "        fresh = max(0, self.input_tokens - self.cached_tokens)",
        "        fresh = self.input_tokens - self.cached_tokens",
        "cached > input 时不出负成本",
    ),
    (
        "未知模型猜一个默认价",
        '        if not p:\n            return 0.0',
        '        if not p:\n            p = {"in": 1.0, "out": 3.0, "cached_in": 0.3}',
        "未知模型返回 0 而不是猜价",
    ),
    (
        "命中率分母不用 max(1, …)",
        "            / max(1, sum(u.input_tokens for u in usages)), 3),",
        "            / sum(u.input_tokens for u in usages), 3),",
        "空列表不除零",
    ),
    (
        "n_calls 数 token 而不是调用",
        '        "n_calls": len(usages),',
        '        "n_calls": sum(u.output_tokens for u in usages),',
        "n_calls 数的是调用次数",
    ),
]


def main() -> int:
    return self_test(
        page="stage-p4.html", card="p4-8", lab=LAB, build=build, mutations=MUTATIONS,
    )


if __name__ == "__main__":
    sys.exit(main())
