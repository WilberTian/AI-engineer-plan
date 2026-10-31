"""判分器体检：把开关和消融各改坏一处，对应的检查必须变红。

    python3 labs/p5-14/tools/self_test.py

两段分开跑：前五个 mutation 打在 flags.py 上，后两个打在 ablate.py 上。
用 refkit 的 self_test 只覆盖单文件，所以这里对 ablate 直接用 mutate.run_mutations。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
sys.path.insert(0, str(LAB.parent / "_shared"))
from htmlcode import block  # noqa: E402
from mutate import run_mutations  # noqa: E402
from refkit import self_test  # noqa: E402

from verify_reference import PAGE, CARD, build_ablate_only, build_flags_only  # noqa: E402

FLAGS_MUTATIONS = [
    (
        "self_check 默认改成开",
        "    self_check: bool = False",
        "    self_check: bool = True",
        "Flags 四个字段与默认值",
    ),
    (
        "去掉 frozen（开关可被原地改）",
        "@dataclass(frozen=True)",
        "@dataclass",
        "Flags 不可变",
    ),
    (
        "环境变量判据改成非空即开",
        'kwargs[f] = os.getenv(f"AIP_{f.upper()}") == "1"',
        'kwargs[f] = bool(os.getenv(f"AIP_{f.upper()}"))',
        "环境变量只认 '1'",
    ),
    (
        "remote 那层失效（环境变量盖上来）",
        "        if f in remote:",
        "        if False and f in remote:",
        "remote 优先于环境变量",
    ),
    (
        "load() 不再合并环境变量",
        "    return replace(Flags(), **kwargs)",
        "    return Flags()",
        "环境变量优先于默认",
    ),
]

ABLATE_MUTATIONS = [
    (
        "一次关两个特性",
        '    off = run_eval(flags=replace(BASE, **{f: False}))',
        '    off = run_eval(flags=replace(BASE, **{f: False, "rerank": False}))',
        "每次只关一个",
    ),
    (
        "输出里不报成本",
        '    print(f"{f:14s} Pass@5 {d_pass5:+.3f}  成本 {d_cost:+.4f}  延迟 {on.p95 - off.p95:+.0f}ms")',
        '    print(f"{f:14s} Pass@5 {d_pass5:+.3f}  延迟 {on.p95 - off.p95:+.0f}ms")',
        "报了 Pass@5 与成本",
    ),
]


def run_checks(target: Path) -> tuple[int, str]:
    r = subprocess.run(
        [sys.executable, str(LAB / "harness" / "run_checks.py"), "--target", str(target)],
        capture_output=True, text=True, cwd=str(target),
    )
    return r.returncode, r.stdout + r.stderr


def main() -> int:
    rc1 = self_test(
        page=PAGE, card=CARD, lab=LAB, build=build_flags_only, mutations=FLAGS_MUTATIONS,
    )
    print()
    rc2 = run_mutations(
        "P5-14 判分器体检（二）：ablate.py",
        baseline=block(PAGE, CARD, 1),
        mutations=ABLATE_MUTATIONS,
        build=build_ablate_only,
        run_checks=run_checks,
    )
    return 0 if rc1 == 0 and rc2 == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
