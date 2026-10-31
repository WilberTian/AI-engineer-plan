"""判分器体检：往 guards.py 里塞已知 bug。

    python3 labs/p4-2/tools/self_test.py

7 个 mutation，每个都是「写了但不会报错」的那类缺陷。
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
        "去重 key 不含参数（只按工具名）",
        '        key = name + ":" + hashlib.md5(\n            json.dumps(args, sort_keys=True, ensure_ascii=False).encode()\n        ).hexdigest()[:8]',
        '        key = name',
        "换参数不误杀",
    ),
    (
        "去重 key 不含工具名",
        '        key = name + ":" + hashlib.md5(',
        '        key = "" + hashlib.md5(',
        "不同工具不共用一个计数器",
    ),
    (
        "哈希前不排序（键顺序影响判定）",
        "json.dumps(args, sort_keys=True, ensure_ascii=False)",
        "json.dumps(args, ensure_ascii=False)",
        "参数键顺序不同仍算同一调用",
    ),
    (
        "边界写成 >=",
        "        if self.total_tokens > MAX_TOTAL_TOKENS:",
        "        if self.total_tokens >= MAX_TOTAL_TOKENS:",
        "恰好用满预算不拦",
    ),
    (
        "预算只看单次不看累计",
        "        self.total_tokens += add_tokens",
        "        self.total_tokens = add_tokens",
        "预算按累计算而不是单次",
    ),
    (
        "脏数据不判 null 值",
        '    missing = [k for k in required_keys if k not in obj or obj[k] is None]',
        '    missing = [k for k in required_keys if k not in obj]',
        "字段值为 null 被拦",
    ),
    (
        "非 JSON 当成不合格",
        '    except json.JSONDecodeError:\n        return True, ""          # 非 JSON 不校验，交给模型读',
        '    except json.JSONDecodeError:\n        return False, "不是 JSON"',
        "纯文本结果不按 schema 拦",
    ),
]


def main() -> int:
    return self_test(
        page="stage-p4.html", card="p4-2", lab=LAB, build=build, mutations=MUTATIONS,
    )


if __name__ == "__main__":
    sys.exit(main())
