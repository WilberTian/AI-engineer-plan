"""P3-13 的日志夹具：9 条 run，其中 5 条该被挖出来。

判分器和 tools/ 都从这里取，只有一份——两份就会漂，
而漂了以后「挖出 5 条」这条判据会变成假绿或假红。

设计意图：
- 0002 / 0003 同属 timeout → 测「按失败类型去重」
- 0004 靠 retries、0005 靠 tool_calls、0006 靠 user_score → 三种信号各一次
- 0009 没有 error_type → 测「未知类型也要收」
- 0001 / 0007 / 0008 是正常样本 → 测「不误报」；0008 特意缺 retries 字段 → 测默认值
"""
from __future__ import annotations

LOG_ROWS = [
    {"run_id": "1f2a3b4c-9d01", "input": "默认端口是多少", "final_answer": "8080",
     "tool_calls": 2, "retries": 0, "user_score": 1.0},
    {"run_id": "2b3c4d5e-9d02", "input": "读一下 notes/plan.md", "final_answer": "",
     "error": "TimeoutError: read timed out", "error_type": "timeout",
     "tool_calls": 1, "retries": 0},
    {"run_id": "3c4d5e6f-9d03", "input": "读一下 notes/todo.md", "final_answer": "",
     "error": "TimeoutError: read timed out", "error_type": "timeout",
     "tool_calls": 1, "retries": 0},
    {"run_id": "4d5e6f70-9d04", "input": "抓一下这个网页的标题", "final_answer": "失败了",
     "error_type": "retry_storm", "retries": 3, "tool_calls": 4},
    {"run_id": "5e6f7081-9d05", "input": "总结一下这个项目的结构", "final_answer": "我正在查…",
     "error_type": "loop", "tool_calls": 20, "retries": 0},
    {"run_id": "6f708192-9d06", "input": "报销流程是什么", "final_answer": "应该是先填单子吧",
     "error_type": "bad_answer", "tool_calls": 1, "retries": 0, "user_score": 0.2},
    {"run_id": "708192a3-9d07", "input": "明天上海天气", "final_answer": "我没有实时天气数据",
     "tool_calls": 0, "retries": 0, "user_score": 1.0},
    {"run_id": "8192a3b4-9d08", "input": "asyncio 的事件循环是什么", "final_answer": "它是调度器…",
     "tool_calls": 5, "user_score": 1.0},
    {"run_id": "92a3b4c5-9d09", "input": "读一下 config.toml", "final_answer": "",
     "error": "KeyError: 'db'", "tool_calls": 2, "retries": 0},
]

# 该被挖出来的失败类型（按 error_type 去重后）
EXPECT_KINDS = {"timeout", "retry_storm", "loop", "bad_answer", "unknown"}

# 明确不该被挖的 input（正常样本）
HEALTHY = {"默认端口是多少", "明天上海天气", "asyncio 的事件循环是什么"}
