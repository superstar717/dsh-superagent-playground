# DEPLOY-NOTES — 图谱问答改由 superagent 主导（工单 c568a58a9d7e）

日期：2026-11-13（Asia/Shanghai）
结论：**已落地**。群里 @机器人 的消息统一由 superagent 工单先处理；旁挂的「图谱问答」改为
superagent 优先窗口内的兜底，并修复了这次误答的两个直接缺陷。图谱能力通过工单内 skill
`jianghushu-graph-qa` 继续可用。

---

## 1. 用户问题与事实时间线

2026-11-13 傍晚，飞书群同一条话题线程上，同一条消息出现了两条答复，用户随即质疑「为什么图谱问答」。

| 时间 | 事件 |
| --- | --- |
| 17:47 | 人 @机器人 发来一条带知乎链接的调研请求 |
| 17:48:00 | superagent 建工单并回接单回执 |
| 17:48:18 | 旁挂 kb-responder 把同一消息判为问句，调 GraphMind `/search`（日志 `Q&A 处理 …`） |
| 17:48:32 | 群里出现「图谱问答」答复（GraphMind 无联网能力，答不了调研任务） |
| 17:49 | 人质疑：这应该交给 superagent 处理 → 本工单 |
| 18:00 | superagent 工单完成并回调研结果 + 飞书文档 |

两个进程用的是**同一个飞书 app**（显示名相同），所以群里看不出答复归属。

## 2. 现状（核实）

| 组件 | 位置 | 职责 | 触发方式 |
| --- | --- | --- | --- |
| DSH superagent | `dsh --profile superagent`（web 3082，stateDir `~/.dsh/state/superagent-fresh`） | 消费 `im.message.receive_v1` → 工单 → worker → 线程回复 | 飞书事件（长连接） |
| kb-responder | `~/姜胡说/scripts/kb-responder.py`，launchd `com.user.kb.responder` | ① 图谱问答 ② 洞见「采纳N/忽略N」闭环 | 每 20s 轮询 chat 消息 |
| GraphMind | `~/graphmind-replica`（127.0.0.1:8777，launchd `com.huweixing.graphmind`） | LightRAG 图谱检索（无联网），数据集 `jianghushu-methodology_b0607c` / `ligongzi_9c54ca` 等 | REST `/api/datasets/<id>/search` |

差异点：superagent 与 kb-responder 都自认为有资格回同一条消息，且没有「谁先接管」的约定。

## 3. 根因（旧版代码实测复现）

旧版脚本（PR #10 原样，备份 `~/姜胡说/scripts/kb-responder.py.bak-20261113-superagent-first`）：

```
[旧版] is_question(带查询串的链接 + 调研类请求) = True
[旧版] thread_has_prior_bot_reply(真实消息) = False
[旧版] WORK_RE 是否覆盖『调研』 = False
```

1. **URL 查询串被当成问号**：`is_question` 用 `"?" in text` 判定；知乎链接的 `?utm_psn=` 让
   该调研类请求通过了问句判定（正文里根本没有问号）。
2. **线程守卫对根消息失效**：`thread_has_prior_bot_reply` 只扫「当前消息之前」的回复，且遇到
   根消息（thread_position=-1）第一条就 `break`。superagent 的回执在**根消息之后**，永远检测不到
   ——这是重复答复的直接原因。
3. **工单词表缺口**：`WORK_RE` 不含调研/研究/评估/核实/整理…，即使修好第 1 条，调研类请求
   也没有「留给工单」的保护。

## 4. 方案比选（选 C）

| 方案 | 做法 | 评价 |
| --- | --- | --- |
| A 彻底删除图谱问答 | kb-responder 只留洞见闭环 | 简单，但普通知识问题也要等分钟级工单，丢掉已建能力 |
| B 只修 URL 判定 | 仍保持「图谱先答、工单再答」 | 重复答复不解决，归属仍不清 |
| **C superagent 优先 + 图谱兜底（已落地）** | 60s 优先窗口；线程已有任何机器人消息就不插话；调研/工单动词永不接；兜底带专属标记 | 主路径唯一、可追溯；图谱能力保留为兜底，并在工单侧继续可用 |

配套（「交给 superagent」不只停掉旁挂，还要让工单答得出图谱内容）：
- 新增 skill `jianghushu-graph-qa`：worker 查 GraphMind（`kg_*` 工具或 `bash`+curl）后带 `[图谱检索]` 依据作答；
- `~/.dsh/AGENTS.md` §十三：全局常驻规则，说明归属、数据集与接口。

## 5. 变更清单

| 文件 | 变更 |
| --- | --- |
| `~/姜胡说/scripts/kb-responder.py`（本仓 `work/scripts/kb-responder.py`） | 问句判定剥离 URL 后再判 `?`；`WORK_RE` 补入调研/研究/评估/核实/整理等；线程守卫扫整条线程；新增 60s superagent 优先窗口（`should_defer`/`deferred` 状态）；兜底回复标记 `**【图谱问答·兜底】**` 并注明「superagent 未接管」；GraphMind 返回字符串 `"None"`/空时按失败处理，不再把 `None` 发群里 |
| `~/.dsh/skills/jianghushu-graph-qa/SKILL.md`（本仓 `work/skills/jianghushu-graph-qa/SKILL.md`） | 新增工单内图谱问答 skill（数据集、两条查询路径、超时/降级处理、标注规范） |
| `~/.dsh/AGENTS.md` §十三 | 新增归属规则与图谱接口速查 |
| launchd `com.user.kb.responder` | `launchctl kickstart -k` 重启，PID 91116 → 34572（新代码） |

未改动：superagent 宿主代码、飞书 app/事件订阅、GraphMind 服务与数据、洞见采纳闭环逻辑。

## 6. 验证记录（实际执行）

1. 语法：`python3 -m py_compile` OK（新旧两处：工单副本与线上文件）。
2. 问句分类 9 例：知乎链接+调研 → 不接；`帮我写/评估/总结` → 不接；`…是怎么说的？`/`为什么…` → 问句。
3. **原消息注入**（`--dry-run --inject-top`，用真实 message JSON 复放）：
   ```
   [18:09:23] 忽略（非问句/工单请求，留给 superagent）
   ```
4. **线程守卫**（真实问题 + 出事线程复放）：
   ```
   [18:09:28] 忽略（线程内已有机器人回复，superagent 已接管）
   ```
5. 优先窗口：fresh question `defer=True`；fresh work `False`；旧消息 `False`；机器人消息 `False`。
6. 线上重启日志：
   ```
   [18:11:30] kb-responder 启动 poll=20s chat=<chat> dataset=jianghushu-methodology_b0607c mode=superagent-first grace=60s
   ```
7. 洞见闭环代码路径未改（`process_reply`/`adopt_insight`/`append_todo` 与旧版同段 diff 为空）。
8. **兜底失败路径**（`--dry-run --inject-top`，GraphMind 当前降级）：
   ```
   [18:13:20] Q&A 兜底处理 <合成消息>
   [18:13:24] Q&A 查询失败 <合成消息>: empty answer（GraphMind 可能正在建索引或后端降级）
   [no-send] would reply <合成消息>: 【图谱问答·兜底】图谱查询失败（服务超时或暂不可用），请稍后再试。
   ```
9. **真实新消息**：18:11 群里一条工单型请求被本进程判为工单请求并忽略
   （`忽略（非问句/工单请求，留给 superagent）`），superagent 同时已接单
   （decision `explicitRouted`），未产生重复答复。
10. **图谱检索链路**（skill 的 curl 路径，实跑）：`POST /api/datasets/ligongzi_9c54ca/search`
    （`local` 模式，query 为主题问题）→ HTTP 200，24.2s，返回 899 字答案（列出 6+ 个框架/方法论）。
    证明 worker 侧的图谱查询方式可用。

## 7. 限制与风险（如实）

- **GraphMind 的 jianghushu 数据集当前临时不可查**：18:10 实测
  `POST /api/datasets/jianghushu-methodology_b0607c/search` 返回 `{"answer":"None","context":null}`，
  后端日志 `ERROR: Query failed: <asyncio.locks.Lock …> is bound to a different event loop`；
  此时后台正在增量建索引（progress 38%）。**同一时刻 `ligongzi_9c54ca` 的 `local` 检索
  24.2s 返回 899 字真实答案**（见 §6.10），说明 REST 链路与 skill 的查询方式本身可用，
  问题只在该数据集的 LightRAG 存储锁被索引任务绑到了另一个事件循环。
  这是 GraphMind 侧既有缺陷，与本次改动无关；兜底已把 `"None"` 判为失败（回「图谱查询失败」
  而不是把 None 发群），skill 也要求查不到就明说并退回 kb_para/网络。
  建议：索引跑完后重启 `com.huweixing.graphmind`（`launchctl kickstart -k`）恢复该数据集查询；
  根治需修 graphmind-replica 的事件循环/存储锁用法（另立工单）。
- 兜底延迟：20s 轮询 + 60s 优先窗口 + `create_time` 分钟精度 → 兜底答复可能延迟 1–2 分钟；
  若 superagent 在窗口之后才回，仍可能双答（概率低，窗口外不保证互斥）。
- 图谱兜底只在本机 GraphMind 可用时有效；建索引期检索 60–90s，超时回「暂不可用」。
- worker 目前没有 `kg_*` 原生工具（superagent `WORK_TOOLS` 白名单未含），skill 里走 `bash`+curl
  的同一条 REST 接口；后续可把 `kg_*` 加进白名单（需宿主重启，另立工单）。
- 本次是路由/行为变更，**无 UI 改动**；before/after 证据是飞书消息原文与进程日志（见 §1/§6），
  不是界面截图。

## 8. 回滚

```bash
cp ~/姜胡说/scripts/kb-responder.py.bak-20261113-superagent-first ~/姜胡说/scripts/kb-responder.py
launchctl kickstart -k gui/$(id -u)/com.user.kb.responder
rm ~/.dsh/skills/jianghushu-graph-qa/SKILL.md   # 可选
# ~/.dsh/AGENTS.md §十三 可整节删除
```
