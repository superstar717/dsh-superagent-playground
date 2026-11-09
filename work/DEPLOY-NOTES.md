# 落地图谱调用与洞见闭环方案 — 部署与验证记录

工单：graph-gaps-plan-1b9537da52e5（2026-11-10）
方案来源：用户 2026-11-09 飞书方案（①飞书问答入口 ②洞见交互闭环 ③自动喂图+逐月回填），按"价值/成本"顺序全做。

## 交付物与部署位置（live 即生效）

| 文件（本 PR 归档） | 部署位置（live） | 作用 |
|---|---|---|
| work/scripts/kb-responder.py | ~/姜胡说/scripts/kb-responder.py | ① @机器人提问→GraphMind /search→线程内带引用回答；② 推送回复「采纳N/忽略N」→写回常青笔记+进创作待办 |
| work/scripts/kb-monthly-feedforward.py | ~/姜胡说/scripts/kb-monthly-feedforward.py | ② 月报一个数：本月创作实际引用旧知识次数（impact）+采纳/忽略数 |
| work/dysub/graph_feed.py + cli.py + registry.py + creators.json | ~/.local/douyin-subscription/（git 652aa68） | ③ 同步完成自动喂图（校验非空→分块上传→增量索引）+ `dysub feed-graph` 补喂命令 |
| work/scripts/dysub-backfill | ~/.local/douyin-subscription/bin/dysub-backfill | ③ 逐月回填驱动器（队列 2021-01→2026-10 共 70 月，单月隔离） |
| work/launchd/*.plist | ~/Library/LaunchAgents/ | 三个新任务：kb.responder（KeepAlive 常驻）、dysub.backfill（21:30）、dysub.graphfeed（21:40） |

**零改动承诺兑现**：未动任何既有 launchd 任务（com.dysub.sync 21:00、kb_para 全系、图谱服务照常）；
dysub 改动只影响之后的同步进程（当晚在跑的李公子逐月回填用的是旧代码，全程未受干扰）。

## ① 问答入口 — 设计与验证

- **轮询而非订阅事件**：DSH superagent 已持有 im.message.receive_v1 事件总线消费者；
  多挂消费者在队列模式下会抢走 DSH 工单事件。kb-responder 用 `+chat-messages-list`
  轮询（20s 间隔），与 DSH 完全旁挂零竞争。
- **确定性匹配**：只接「人类发送 + @机器人 + 问句形态（问号或疑问词开头）」；
  祈使句/工单请求（含 工单/剔除/执行/回填 等动词）不接、两可不接，留给 DSH 工单流；
  线程内机器人已回复过的讨论不插话（DSH 进行中任务）；首次启动只注册推送不回答历史问题。
- **带引用回答**：GraphMind /search（dataset jianghushu-methodology_b0607c, mode mix）
  返回的 answer 自带 References 源文档列表，原样回帖，超 2800 字截断说明。

**After 证据（真实 /search 返回，2026-11-10 01:05 实测）**：
问「姜胡说 认知」→ 1346 字结构化回答，末尾 References 列出 [1] 01-个人成长.md
[2] 20261028_让认知追着行动跑….txt [3] 6854877843646663944.txt 等 5 个源文档。
耗时 ~11s/问。「李公子和姜胡说是什么关系」→ 正确答出"推荐关系：姜胡子向粉丝推荐了李公子的社群"。

**限制（如实）**：群内真实 @机器人 提问的端到端回帖尚未发生（部署后首次真实提问即验证，
日志写 ~/姜胡说/logs/kb-responder.log）；回复发送复用 daily-three 已在生产验证的
lark-cli 通道；CLI 无法截图飞书客户端，无聊天界面截图。

## ② 洞见闭环 — 设计与验证

- 推送注册：识别机器人发的「每日三洞见」顶层消息，记录 message_id→日期（回看 7 天）。
- 回复「采纳N / 忽略N」（N=1-3，对应当日三条）：采纳 = `kb validate --accept` →
  `kb writeback`（写回常青笔记节点）→ 追加 dtodo work 轨创作待办（cat: 创作，q2）→
  线程回执；忽略 = 台账记录 + 回执。不指序号的「采纳」回 1-3 条清单让用户选。
- 台账：~/姜胡说/.kb_responder/adoption.jsonl（月报数据源之一）。
- 月报：`python3 kb-monthly-feedforward.py [--month YYYY-MM] [--list]`
  输出 impact 次数 / writeback 新增节点 / 采纳-忽略数。

**After 证据（一次性库副本 e2e，真实执行 kb 变更、不发群消息 --no-send）**：
对 2026-11-06 推送回复「采纳1」→ INS-0001 candidate→validated ✓ → 写回节点 KB-4477
（type derived-insight, source_ref INS-0001）✓ → dtodo 条目 `[q2] [cat: 创作] 创作选题
（源自洞见 INS-0001…）` ✓ → adoption.jsonl 记录 ✓，五步全绿。
测试数据已从正式台账清除，正式库零污染（writeback 0 节点、采纳 0 条已复核）。

## ③ 喂图自动化 + 逐月回填 — 设计与验证

- **复用既有管线语义**（2026-11-08 feed-graph.sh 已验证）：上传 documents（20/请求）→
  空 body 触发增量索引 → LightRAG 内容哈希幂等去重；新增：喂图前本地校验非空
  （空/过短/不可解码/超 1MB → 隔离记录，防上轮 Parsing failed 整轮报废）、
  同视频「数字名+可读名」双文件按 sha1 去重（优先可读名）、索引短轮询 90s 即返回
  （索引可跑数小时，绝不阻塞 sync）、单文件失败隔离。
- **sync hook**：同步收尾（入库后、清媒体前）自动喂本轮 txt；`--no-graph` 可关；
  任何喂图异常只记 [GRAPH-ERR]，不影响同步结果与退出码。
- **补喂命令**：`dysub feed-graph <博主> [--max N] [--dry-run]`——扫 asr_dir 未喂 txt
  （sha1 台账幂等），每晚 launchd 21:40 排队消化（李公子 20/晚、姜胡说 10/晚）。
- **逐月回填**：`dysub-backfill` 队列 2021-01→2026-10（70 月），每晚 21:30 一月；
  锁被占（21:00 定时同步或手动回填在跑）即让路退出；单月失败重试 3 次后标记
  blocked（飞书提醒）跳下月。进度：`dysub-backfill --status`。

**After 证据（真实 e2e，2026-11-10 01:28）**：
`dysub feed-graph ms4wljabaaaaazb6 --max 2` → 数据集 ligongzi_9c54ca 自动创建 →
2 篇上传（GET /documents 复核 2 个文档在列）→ 触发增量索引 →
`{"status":"completed","step":"done","progress":100,"message":"索引完成！"}`。
第二轮 dry-run 确认：已喂 sha1 不再重复、数字名重复文件被去重。
驱动器 dry-run 确认锁让路：当晚李公子手动回填在跑，本轮自动退出（日志在案）。

## 回滚

- 停问答/闭环：`launchctl bootout gui/$(id -u)/com.user.kb.responder`
- 停回填/补喂：`launchctl bootout gui/$(id -u)/com.dysub.backfill`（及 .graphfeed）
- 喂图 hook：`dysub sync ... --no-graph` 即跳过；creators.json 删 graph_dataset 字段即全局关闭。
- dysub 代码回滚：git revert 652aa68。

## 已知限制与后续

- 群内首次真实 @机器人 提问、首次真实「采纳N」回复 = 最终端到端验证点（部署后自然发生）。
- 姜胡说 asr_dir 存量 642 txt 中未喂部分按 10/晚 滴灌喂入（LightRAG 幂等跳过已喂的）；
  若不想喂存量，从 com.dysub.graphfeed.plist 去掉 jianghushuo 一段即可。
- 双回答风险：@机器人问句现在有两条应答路径（本 responder 快速图谱回答 + DSH 工单流的
  慢速回答）。已用问句形态+工单动词排除+线程内已回复检测收敛；实测若仍有噪音，
  可在 kb-responder.py 的 WORK_RE/QUESTION_START_RE 调词，或加显式触发词（如"问图谱"）。
- 当前洞见推送（11-07 起）疑似因 MiniMax 余额问题未发出（群内只见 11-06 一条），
  洞见闭环依赖推送恢复，属另一问题未在本工单处理。
