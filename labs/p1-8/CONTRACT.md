# P1-8 接口约定：错误探测脚本

判分器只看这一页。

## §1 落点

```
scripts/error_probe.py     探测五种错误，统一只打三样
```

`openai` 与 `agentlab.config.PRIMARY` 由判分器提供替身（不联网、不花额度）。
替身会按参数抛不同的异常：有的带 `status_code`，有的不带，有的消息超长。

## §2 判什么（11 条）

| 组 | # | 断言 |
|---|---|---|
| 不崩 | 1 | 五次探测全部跑完，没有异常漏到顶层 |
| 三样 | 2–3 | 输出里五个 label 都在；每条都是 `type` / `status` / `message` 三行 |
| 兜底 | 4 | 异常没有 `status_code` 时打印 `None`（不是崩、也不是留空） |
| 截断 | 5 | 超长错误消息被截到 200 字以内 |
| 可区分 | 6 | 五个 label 互不重复（能一眼看出是哪次探测） |
| 干净 | 7 | 不打印完整 traceback（那是日志系统的事，不是探测脚本的事） |
| 透传 | 8–10 | 五次调用都真的传到了 `create`；每次都带 `messages`；至少一次改 `model` |
| 静默 | 11 | `create` 不抛异常时，`probe` 什么都不打印 |

**为什么判「不打印 traceback」**：探测脚本的目的是**看清错误的结构**，
不是记录事故。打出 30 行 traceback，反而把「type / status / message」三行淹掉。
这三样覆盖 90% 的线上定位——这句话反过来就是：**traceback 里的其余部分，你定位时不会看。**

**为什么判「透传」**：`probe(label, **kwargs)` 如果把 kwargs 吞掉不传，
五次探测就都变成了同一种错误（空消息），于是你「看全了五种」其实只看到一种。
这是最隐蔽的一种错——输出照样有五行，内容全一样。

## §3 不判什么

- **五种坑选得对不对**：`空消息` / `超长输入` / `错误模型名` / `坏图片 URL` / `max_tokens 负数`
  是手册选的，你换几种也行（只要覆盖「参数错误」「模型不存在」「输入超限」三类）。
- **真实的错误码表**：那要真调供应商，5 次调用花几毛钱，但结果不可复现
  （供应商改文案就漂）。这一步**必须人工做一次**，判分器替代不了。
- **HTTP 状态码映射**：401/429/500 各对应什么动作，是你写进 P4 容错表的结论。

## §3.5 边界：参考实现有 6 条红

`probe()` 里 `messages=[]` 写成了固定参数，而五次探测都传 `messages=...`，
于是五次全部变成 `TypeError: got multiple values for keyword argument`——
**一次都没真正调到 SDK**。第 1、5、8、9、10、11 条抓的就是这个，
修法见 `NOTES.md` §1（一处 `kwargs.setdefault("messages", [])`）。

有意思的是第 2、3、4、6、7 条仍然绿：**格式全对，内容全一样。**
这正是「只判格式的判据不够」的现场例子。

## §4 你的自由

- 打印格式（只要三样都在，是不是等号对齐无所谓）
- 加第四样（`request_id`、`retry_after` 都很有用）
- 把探测结果存成 JSON 而不是打印

## §5 怎么跑

```bash
python3 labs/p1-8/harness/run_checks.py --target ~/code/agentlab-project
python3 labs/p1-8/tools/verify_reference.py
python3 labs/p1-8/tools/self_test.py
```
