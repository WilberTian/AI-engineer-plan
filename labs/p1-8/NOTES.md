# P1-8 要点核对表：错误探测脚本

判分：`python3 labs/p1-8/harness/run_checks.py --target <你的项目>`（11 条，参考实现 5 绿 6 红）
自查判据本身：`tools/verify_reference.py` + `tools/self_test.py`（5 个 mutation 全抓住）

---

## §1 先说结论：手册这段代码跑不起来

```python
def probe(label: str, **kwargs):
    try:
        client.chat.completions.create(model=PRIMARY.model, messages=[], **kwargs)
```

`messages=[]` 写成了**固定参数**，而五次探测又都传了 `messages=...`：

```python
probe("空消息", messages=[])
```

于是 Python 报 `TypeError: create() got multiple values for keyword argument 'messages'`，
**一次都没真正调到 SDK**。五次探测打出来的是同一个错误：

```
[空消息]
  type     = TypeError
  status   = None
  message  = openai._Completions.create() got multiple values for keyword argument 'messages'
```

`[超长输入]`、`[错误模型名]`、`[不存在的图片URL]`、`[max_tokens 负数]` —— 五段输出**一模一样**。

**修法**（一处）：

```python
kwargs.setdefault("messages", [])
client.chat.completions.create(model=PRIMARY.model, **kwargs)
```

或者把默认值放到签名里：`def probe(label, messages=(), **kwargs)`。

判分器第 1、5、8、9、10、11 条抓的就是这个——它们看的是「有没有真的调到 SDK」，
而 2、3、4、6、7 条仍然绿，这恰好说明**格式对了不代表内容对**。

## §2 决策点表

| # | 位置 | 手册做法 | 另一种合理做法 | 什么时候该换 | 怎么核你那份 |
|---|---|---|---|---|---|
| 1 | 打印什么 | type / status / message | 加 `request_id`、`retry_after` | 要拿 request_id 找供应商支持时 | 429 的时候有 `retry_after` 吗 |
| 2 | 消息截断 | 前 200 字 | 前 200 + 末 100 字 | 错误体前面是堆栈、关键信息在末尾时 | 看一条 502 的错误体结构 |
| 3 | 捕获范围 | `except Exception` | 分类捕获（`RateLimitError` 等） | 要按类型给不同动作时 | 5 种坑各落在哪个 except 上 |
| 4 | 输出去向 | stdout | JSONL 落盘 | 要进 P4 的审计日志时 | 有没有 `print` 和写文件两条路 |
| 5 | 五次坑 | 5 类 | 加「并发打满」「超时」 | 要覆盖容器/网络层失败时 | 线上真实错误类型的 top5 是什么 |
| 6 | 是否保留 | 一次性脚本 | 改成 `debug_probe` 命令 | 线上要能随时探一次时 | 出问题时你手上有没有这个工具 |

第 6 条值得单独说：**这个脚本是一次性的，但它的输出格式应该活着。**
P4 做容错时，「type / status / message」这三样就是你的审计日志字段。
一次性脚本丢掉以后，你在线上遇到 429 时只能靠猜。

## §3 静默错误清单

| 静默错误 | 现象 | 什么时候暴露 |
|---|---|---|
| `probe` 把参数吞了 | 五次探测内容全一样，但「看起来都跑了」 | 以为看全了五类错误，其实一类没看到 |
| 用 `exc.status_code` 直接取 | 参数校验类错误（无 status_code）直接崩 | 第一次遇到 400 参数错误就报 AttributeError |
| 消息不截断 | 一行 5000 字，把另两样挤出屏幕 | 真遇到 502 整页 HTML 时 |
| 打完整 traceback | 三行有用信息被 30 行堆栈埋掉 | 定位时反而更慢 |
| 每个坑都用同一个模型 | 「模型不存在」这一类的形状没见过 | 把 404 误判成参数错，重试三次才放弃 |
| 只在 except 里打印 | 成功路径也在打印 = 日志噪音 | 真实运行时 90% 的行是噪音 |

## §4 一个判断：错误码表该怎么定

这张卡的验收是「一张**每类对应一个动作**的表」。判断标准不是「记得全」，而是：

**看到这个错误，你的代码会做什么？**

| 动作 | 触发条件 | 例子 |
|---|---|---|
| 重试（带退避） | 瞬时故障，重试有意义 | 429、500、502、连接超时 |
| 改参数后重试 | 请求本身有问题 | 400 参数错、上下文超限（先压缩） |
| 换模型/降级 | 指定模型不可用 | 404 模型不存在、403 无权限 |
| 上报并停止 | 重试只会更糟 | 401 密钥错、402 余额不足 |
| 交给用户 | 不是你的错 | 内容审核拦截 |

判这张表的方法很简单：**拿 5 个真实错误，问「它会走哪一行」**。
有一行走不到 → 那行是摆设；有一个错误落不到任何一行 → 你在 P4 会写一个兜底的
`except Exception: 重试三次`，而那是最贵的错法（用三次调用掩盖一个不该重试的错误）。

顺带一句：这张表**必须你自己调一次供应商**才有。判分器判不了错误码——
它只能判「你打出来的三样够不够定位」，而三样对不对，只有真错误说了算。
