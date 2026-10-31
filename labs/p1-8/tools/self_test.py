"""判分器体检：把「只打三样」这条规则逐条改坏。

    python3 labs/p1-8/tools/self_test.py

基线有 6 条本来就红（手册那段 probe 把 messages 写死了，一次都没调到 SDK）。
所以这里只挑**本来绿的那 5 条**打——打一条已经红的判据证明不了任何事。
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
        "不打 type",
        '        print(f"  type     = {type(exc).__name__}")',
        "        pass",
        "三样各打五条",
    ),
    (
        "不打 label",
        '        print(f"\\n[{label}]")',
        "        pass",
        "五个 label 都在",
    ),
    (
        "label 写死成同一个",
        '        print(f"\\n[{label}]")',
        '        print("\\n[探测]")',
        "label 互不重复",
    ),
    (
        "把完整 traceback 打出来",
        "    except Exception as exc:",
        "    except Exception as exc:\n        import traceback\n        traceback.print_exc()",
        "没有 traceback",
    ),
    (
        "status 兜底写死成 -1",
        '        print(f"  status   = {getattr(exc, \'status_code\', None)}")',
        '        print(f"  status   = {getattr(exc, \'status_code\', -1)}")',
        "缺 status_code 时打印 None",
    ),
]


def main() -> int:
    return self_test(page="stage-p1.html", card="p1-8", lab=LAB, build=build, mutations=MUTATIONS)


if __name__ == "__main__":
    sys.exit(main())
