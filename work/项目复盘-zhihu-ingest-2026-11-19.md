# 项目复盘 — 知乎回答提取入库并落地机制（zhihu-mechanism-ingest-75777e92e8dd）

> 完成时间：2026-11-19 23:2x ｜ 来源：飞书群消息「知乎回答 URL + 提取入库 并进行机制落地」
> 路由注记：知乎需登录态（zhihu_reader）；机制先评估再落地。
> 注：work/项目复盘.md 已被工单 c568a58a9d7e 占用，本复盘按日期独立命名，不覆盖他人归档。

## 一、最终事实

**入库（全链 e2e 完成，kb-commit 门禁通过并推送私有远端 ddd344f）**

- 原文：`03-Resources/耐心等待-高手是怎么使用AI的-知乎回答-2106144959288158181.md`（source=知乎回答 URL；网页原文照录；标注了噪声处理与提取方式）
- 候选知识卡（02-Areas，全部 candidate:true 待用户确认）：
  1. AI是失忆新人——背景资料和说明书一次给全（心法②③）
  2. 能动手别动嘴——让AI直接执行而非只要口头答案（④）
  3. 错一次固化一次规则——AI协作的规则库飞轮（⑤⑥）
  4. 与其反复叮嘱不如直接给模板（⑦）
  5. 多AI分工——调研输出裁判循环迭代（⑧）
- 印证追加：心法①命中既有卡《会指挥AI的前提》，按 SOP 追加印证来源（para_save supersede，旧版迁 04-Archive，原卡 kind/created frontmatter 完整保留）
- 逐条查重（SOP 硬步骤）：8 条心法逐条对 02-Areas 检索比对，仅①命中，其余未命中新建

**机制（先评估后落地）**

- 评估结论：
  - 提取能力已存在且成熟（`~/bin/zhihu_reader.py`，登录态 `~/.zhihu_reader_dp` 有 `z_c0`，2026-11-19 实测有效）→ 不重写；
  - 缺口是「发现性 + 回答噪声 + 版本管理」：无任何 skill 指向该工具链（本次开工靠多轮搜索才发现）、trafilatura 整页提取混入「更多回答」与登录角标、工具无版本管理；
  - **不做全自动「URL→库」CLI**：查重与提炼判断必须由 agent 按 SOP 做（para_save 是 agent 工具），全自动会绕过查重硬步骤——评估为不落地，理由记录在案。
- 落地四件：
  1. skill `zhihu-ingest`（`~/.dsh/skills/zhihu-ingest/`）：工具链入口/登录态检查/标准链路/已知坑；**已实测进入会话技能目录**（创建后 available_skills 立即可见）；
  2. 新工具 `~/bin/zhihu_answer_extract.py`：js-initialData 按 answer id 身份核验式精确提取（免疫噪声），真实 URL e2e 通过（作者 耐心等待 / 624 字符 / 无噪声）；
  3. `~/bin` 纳入 git 版本管理（白名单 .gitignore，首提交 8c1cff6，含 reader/discover/answer_extract 三件）；
  4. LESSONS **E183**：`set_local_port(0)` 残留 Chrome 占登录态目录（本次实测踩坑，已查重无既有条目）。

**验证状态**

- 提取→核验→入库→提炼→提交→推送全链实跑通过；
- 双路比对：trafilatura 主块与 js-initialData 逐行一致，目标答案 23 行（作者 耐心等待，非文末署名的龙之语007——那是「更多回答」混入内容）；
- 登录态：sqlite 查 `z_c0` 确认存在后才跑（E86 预防）。

## 二、做得对的

1. 开工检索三处命中既往资产（zhihu_reader.py + 登录态 + 三个既往工单复盘），未重造轮子。
2. 不信单路提取结果：用页面 js-initialData 按 answer id 核验身份与正文，发现并剔除了「更多回答」噪声与署名误导。
3. supersede 前先读 para-knowledge 插件源码，确认 content 自带 frontmatter 时原样保留（只补缺失字段），避免了原卡 kind/created 丢失。
4. 失败快速归因：BrowserConnectError → pgrep 发现残留 Chrome → 按主进程 PID 清理 → 新教训入 LESSONS。

## 三、犯过的错

1. `set_local_port(0)` 想当然当"自动选端口"→ 残留 Chrome 占登录态目录连环失败；且第一次 pkill 模式没考虑参数顺序（`--remote-debugging-port` 在 `--user-data-dir` 之前），盲试一轮后才按 PID 杀（E183）。
2. 复核脚本先写后跑发现借 `make_page` 的正确姿势，第一版手写 ChromiumOptions 走了弯路。

## 四、如果重来会怎么做

1. 开工直接按 skill（现在已存在）走标准链路，省掉探索轮次。
2. 任何 DrissionPage 建页一律复用 `zhihu_reader.make_page`，不手写 ChromiumOptions。

## 五、仍未解决 / 边界（如实）

1. 登录态时效：`z_c0` 过期后需要人工扫码登录一次（工具已内置首次登录流程，非本单问题）。
2. kb-commit 是 `git add -A`：本单提交裹入了另一并行会话同期的 4 个 superseded 归档（共享库正常行为，提交信息只覆盖本单部分）；脚本行为未改。
3. 专栏文章（zhuanlan）走 zhihu_reader 的路线既往工单已验证，本单未重复实测。
4. 5 张候选卡与印证追加均为 candidate 状态，**晋升需用户确认**（SOP 第三阶段，AI 不得自行转正）。
5. 本会话无 memory/dtodo 原生工具，工具链事实改由 skill + LESSONS 承载（等效归位）。

## 六、经验归位情况（ready 前完成，不留「待新工单」项）

| 经验 | 落点 | 状态 |
|---|---|---|
| set_local_port(0) 残留 Chrome | `~/.dsh/LESSONS.md` **E183** | 本单新增（已查重） |
| 知乎提取工具链入口/坑 | `~/.dsh/skills/zhihu-ingest/SKILL.md` | 本单新增，已进会话技能目录 |
| 新工具 zhihu_answer_extract.py | `~/bin/`（git 8c1cff6）+ 仓库副本 `work/scripts/` | 已落常驻路径 |
| 答案内容入库 | `~/我的知识库`（kb-commit ddd344f，已推私有远端） | 完成 |
| 过程与评估 | 本复盘 + `work/skills/` `work/scripts/` 副本随 PR 归档 | 完成 |

## 七、后续追问与「落1」执行（2026-11-19 23:2x）

- 用户问「这个内容不值得进行机制落地吗」→ 按「是否已有机制载体 + 信息增量」框架逐条评估：8 条心法中
  6 条已有载体（AGENTS 注入/skill/agent 工具执行/LESSONS 错误录/模板链），未发现常设载体的仅 2 条
  （①通用任务开工验收标准、⑧内容任务裁判；检索范围：AGENTS 十八节+技能目录+本单候选卡）。
  结论已答复：不值得为这条内容新立机制，但①可按最小约定通用化。
- 用户拍板「落1」→ **`~/.dsh/AGENTS.md` 新增 §十九「开工先定验收标准」**：开工 todo 首行写清"做完"
  长什么样，交付前逐项自检；不加 hook/门禁（E127 同款取舍）。
- 验证：AGENTS.md 修改后本会话指令注入已回读包含 §十九（下个会话必可见，满足第十节自查）；⑧维持
  §十七「不做更强机制」的既有拍板，未动。
