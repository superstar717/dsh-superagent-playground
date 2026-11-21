# DSH 0.2.2 升级调研报告（本机 superagent 栈）

- 调研对象：DeepSeek Harness（DSH）最新版本的功能变化与「是否值得更新」
- 本机现状：全局 `dsh 0.2.1-rc.5` + `superagent` profile（23 个插件：7 个本地自研、3 个源码 link、13 个 npm 第三方）
- 数据快照：2026-11-14 09:30 CST（版本、发布时间、本机配置均为该时点）
- 结论一句话：**值得升级到 `0.2.2-rc.3`，但不是一条命令直升**——需要一次约半天到一天的插件迁移和维护窗口重启，直接 `npm i -g` 会让本机自研栈面临运行时风险。

---

## 1. 结论

### 1.1 版本结论

| 项 | 当前 | 最新 |
|---|---|---|
| 全局 CLI | `0.2.1-rc.5`（2026-10-29 发布，0.2.1 线最后一个版本） | `0.2.2-rc.3`（2026-11-13 发布） |
| npm dist-tag | — | `latest = 0.2.2-rc.1`，`next = 0.2.2-rc.3` |
| 源码 checkout | `dsh-v0.2.1-rc.5-1-gab426e3d23`（2026-11-10） | `dsh-v0.2.2-rc.3` |
| 跨版本规模 | — | `0.2.1-rc.5..0.2.2-rc.3` 共 **4,197 个提交**、约 1.04 万个文件变更 |

注意：**不要用 `npm i -g @deepseek-ai/dsh`（`latest`）**，它现在指向 `0.2.2-rc.1`（11-04），比 `next`/最新 RC 少了 rc.2 的大量修复与 rc.3 的会话导入插件。请显式指定 `@0.2.2-rc.3`。

### 1.2 推荐动作

1. **值得升级，但按「计划升级」执行**：挑一个没有在跑工单的窗口，先备份，再迁移本机插件，最后重启。
2. **目标版本固定为 `0.2.2-rc.3`**（或等 0.2.2 正式版；本地迁移工作量不变）。
3. **不要现在直接升**：本机当前有多个活跃工单会话，且 `dsh-superagent` 等自研插件需要按新 API 复核后才安全。

### 1.3 「升级后需要重启吗」

**需要，而且必须重启。**

- DSH 的插件、`cordis.patch.yml`、`~/.dsh/hooks.json` 都在宿主启动时加载；本机 `superagent` profile 没有启用 HMR，改完只能重启生效（与既往结论一致：hooks 配置只在宿主启动时解析）。
- 重启会结束当前所有 DSH 会话（窗口断开），但会话文件在 `~/.dsh/sessions` 持久化，重开即可恢复；正在跑的 worker 回合会被中断，`dsh-superagent` 有中断恢复逻辑，会带着恢复说明继续/重跑工单。
- 本机已有现成脚本：`~/.dsh/bin/super-restart.sh superagent`，约 **10–20 秒** 就绪；同端口重启后浏览器 cookie（30 天）仍有效，刷新即可，不需要重新扫码/登录。
- Feishu 机器人在重启期间短暂离线；launchd 定时任务（dysub 等）是独立进程树，不受影响。

---

## 2. 0.2.2 更新了什么

### 2.1 发布说明的量化口径

中文发布说明（rc.1 + rc.2 + rc.3）合计约 **220 条**：

| 类别 | 条数 |
|---|---|
| 新增功能 | 17 |
| 体验优化 | 58 |
| 问题修复 | 80 |
| 其他变更（含开发/迁移项） | 65 |

### 2.2 新增功能（按对本机的价值排序）

**A. 对「工单/调研」工作流直接有用**

- **变更请求与工作树（实验）**：在独立 Git worktree 中跑会话，可搜索文件树、逐文件查看本地与 PR diff，把选中代码和评论交给 Agent，并跟踪检查和评审状态。
- **具名、多层 SubAgent + AgentTeam**（rc.2）：子代理可具名、多层协作，按会话开启团队模式，共用成员与任务面板。
- **会话复制为 Markdown**：完整历史会话可复制为 Markdown，并附原始日志路径。
- **插件管理升级**：插件详情富文本、在线更新第三方插件包、更新失败自动回滚旧版本。
- **MCP 动态注册**：插件可动态注册/移除 MCP 服务，并可查询状态、重启、探测连接，无需逐项维护配置。
- **`subagent_oar` 实验插件**：把独立任务交给本机 Codex 或 Claude CLI。

**B. 交互与界面**

- 手机/平板适配（软键盘、导航、窄屏布局）。
- 聊天文本作为引用插入输入框，发送后紧凑预览。
- 统一右键与键盘菜单（会话、工作区、侧栏，支持开发者扩展）。
- 文件预览常驻目录树与文件定位。
- 工作步骤收起后保留全部助手文字回复，可切换「仅最终回答」。
- 新增日语、西班牙语、法语、德语、俄语、巴西葡萄牙语。
- 侧栏插件入口收进「更多」，可重新固定并保持原顺序。
- Agent 终端改到侧栏标签页，人可直接输入接管；`user_terminal_list/read` 可读回终端内容。
- 网页搜索单次默认支持最多 10 个查询、10 个来源。
- 模型请求失败后的重试设置（条件/次数/等待时间）可在模型设置里调。
- API Key 掩码管理（整体替换或清除，不显示完整旧密钥）。

**C. 开发与模型**

- 自定义模型提供方支持 Gemini 原生接口（可获取模型列表、设置推理等级）。
- 插件可为聊天代码块按语言扩展渲染。
- 插件索引可提供 GitHub Star 与 npm 周下载量。
- SDK 补齐文件交付、问答与回调、调度、技能、上下文、原生命令、插件管理、计划审阅、目标续跑、操作审批等能力。
- 新增默认关闭的 `apply_patch` 工具：一次完成多文件新增/编辑/删除/移动。
- Node PTC 新增 VM Script 模式（顶层 await、动态 import、表达式结果，可跨调用保留状态）。

**D. rc.2 / rc.3 增量**

- rc.2：Git Worktree 按分支/提交/文件类型审阅、直接处理 GitHub 评审与更新分支；桌面端正式版/开发版更新渠道切换；临时请求失败可直接「继续生成」；上翻自动加载更早消息并保持阅读位置；上下文提示明确「运行信息 vs 旧信息」的替换关系。
- rc.3：实验性「DeepSeek 会话导入」插件（把 DeepSeek App/网页历史会话导入工作区继续对话）；修复 Windows 桌面版应用内更新失败。

### 2.3 稳定性与性能修复（与本机长期会话/值守强相关）

- 修复会话恢复或压缩后上下文提示不清晰、历史加载/新消息持续卡住、同一消息重复提交、停止任务时资源提前释放。
- 后台任务完成通知直接携带小体积输出，减少重复通知；子代理等待改为「没结果就结束本轮等通知」，减少 sleep/轮询。
- 系统提示词未变化时复用上下文前缀缓存；长回复流式组装的运行时成本降低。
- 文件查找跳过无关目录、只读工具可并行、Web 静态资源 ETag、远程连接默认 WebSocket 压缩。
- 修复 macOS 窗口拖动/粘贴快捷键、Windows 暗色启动白闪；rc.3 修 Windows 应用内更新。
- 修复插件加载失败导致整页无法启动、插件显示「运行中」但实际未加载等问题。

### 2.4 破坏性/迁移项（与本机有关）

| 变更 | 影响 |
|---|---|
| Cordis Core 4.1.0 / Loader 1.1.0 / Include 1.1.0 | 插件 API 基线变化；本机 `dsh-superagent` peer 里仍钉 `cordis 4.0.5-alpha.1`，运行时需验证 |
| 最低 Node.js 24.9 | 本机 24.15.0，满足 |
| `agent/request` 不再允许改路由 | 本机 `dsh-superagent` 的角色模型初始化依赖它，需迁移到 `agent.model.select()` |
| Session Projection 注册改 async；旧 `stateOf(session,key)` 弃用但可用 | `dsh-superagent`、旧 hooks 桥接仍有旧式调用，会告警，需排期迁移 |
| 工具按步骤条件启用；`tools.resolve/executable`、提示词组装接口迁移 | 自定义插件需复核（`dsh-superagent` 大量使用 tools/prompt 接口） |
| PTC 控制通道改 birpc；SSH 协议 2→3 | 本机暂未用 PTC/SSH helper，影响小 |
| 官方组合包列表移到 `@deepseek-ai/dsh-official-bundles`；独立 worktree bundle 并入「变更请求与工作树」 | profile 的 bundles 需移除 `@deepseek-ai/dsh-experimental-tool-worktree` |
| 文件修改「先读后写」防护默认关闭（`fs-observation-policy` disabled） | 安全/行为变化；要保留需在 profile 显式开启 |
| 内置 preset 默认关闭 `interrupt_agent` | 本机 worker 工具白名单含 `interrupt_agent`，要保留需按 preset 覆盖 |
| 网页搜索默认改用 DeepSeek Search API，新增 `searchBilling`/`fetchBilling` | 旧提供方/自定义配置需按升级指南调整；本机还有 argo-dsh（Tavily/Firecrawl）另算 |
| 归档 Session 默认清理符合条件的 Git worktree | 使用 worktree 时需注意；本机暂未重度使用 |
| `dsh-doc` 取代 4 个创造模式 skill | 本机未发现引用旧 skill 名 |

---

## 3. 本机兼容性盘点

### 3.1 版本门禁：能过

DSH 的插件兼容性判定（tag `dsh-v0.2.2-rc.3`，`packages/boot/app-boot/src/plugin-compatibility.ts:52`）：

```ts
return range.trim() !== '' && semver.satisfies(runtimeVersion, range, { includePrerelease: true })
```

即：先看 `engines.dsh`，没有才看 `@deepseek-ai/dsh*` peer；**预发布版本参与匹配**。据此复核：

| 范围 | 运行时 0.2.2-rc.3 | 组件 |
|---|---|---|
| `^0.2.1-alpha.2` | ✅（includePrerelease） | dsh-superagent 的 `engines.dsh` |
| `>=0.2.1-rc.5 <0.3.0` | ✅ | agentero-dsh、dsh-media-desk |
| `>=0.1.0-rc.6 <0.3.0-0` | ✅ | dsh-bilibili |
| `>=0.2.0-rc.2` / `>=0.2.1-rc.2` / `>=0.2.2-rc.1`（任一分支） | ✅ | dsh-context |

7 个本地自研插件（`stat-research-gate`、`douyin-subscription`、`answer-consistency-gate`、`sr-workbench`、`dsh-memory-evolve`、`dsh-superagent`、`graphmind-bridge`）多数没有 `engines.dsh`/peer，**版本门禁不会拦截**——风险全在运行时 API。

### 3.2 组件逐项

| 类别 | 组件 | 现状 | 0.2.2 影响 | 处理 |
|---|---|---|---|---|
| 运行时 | Node | v24.15.0 | 要求 ≥24.9 | ✅ 不动 |
| 核心 | 全局 CLI | 0.2.1-rc.5 | 目标 0.2.2-rc.3 | npm 全局升级，显式 pin |
| 源码 | `~/deepseek-harness` | rc.5+1，仅 `chmod +x apps/desktop/cli/dsh` 本地改动 | 升级指南与插件源码都以 rc.3 为准 | checkout 到 `dsh-v0.2.2-rc.3`，`pnpm install && pnpm build` |
| 链接包 | `@deepseek-ai/dsh-hooks-claude-code` | 0.2.1-rc.5（link 到源码） | 新版改用 `ctx.agents.turnBoundaryOf`；旧版走已弃用的 `sessionProjections.stateOf`（仍可用） | 随 checkout 升 rc.3 重建 |
| 链接包 | `@deepseek-ai/dsh-subagent-claude-code` / `-codex` | 0.2.1-rc.5（link） | 差异以 locale/peer 为主 | 随 checkout 升 rc.3 重建 |
| 自研 | `dsh-superagent` 0.1.0 | `engines.dsh ^0.2.1-alpha.2`；peer 钉 cordis 4.0.5-alpha.1 | `agent/request` 不许改路由（不一致会 throw）；projection 注册异步；客户端 UI API 有变 | **重点适配 + typecheck/test + UI 冒烟** |
| 自研 | `dsh-memory-evolve` 0.1.0 | 无版本声明；记忆/待办/技能/COI/大量 UI | 无门禁；运行时行为需冒烟 | 记忆读写、任务、技能、注入逐项测 |
| 自研 | `stat-research-gate` 2.10.1、`douyin-subscription` 1.0.0、`answer-consistency-gate` 0.1.0、`sr-workbench` 0.1.0、`graphmind-bridge` 0.2.0 | 无版本声明 | 工具/UI 插件，无门禁 | 冒烟 |
| 第三方 | 13 个 npm 插件（kanban、better-sidebar、bilibili、builtin-browser、context、media-desk、routing-suite、replay、modlens、argo-dsh、agentero-dsh、guizang-design、reverse-skill） | 见附录 | engines 范围多数含 0.2.2；客户端 UI 定位/侧栏/设置 API 有变更 | 升级后 UI 全量冒烟 |
| Hooks | `~/.dsh/hooks.json` 5 条（PreToolUse ×4、PostToolUse ×1） | Claude Code 格式，启动时加载 | 格式未变，桥接插件适配层小改 | 重启后 e2e 验证拦截/放行 |
| 配置 | `fs-observation-policy` | 0.2.1 默认启用 | 0.2.2 默认 disabled | 要保留则 profile 显式 `disabled: false` |
| 配置 | `interrupt_agent` | 当前可用 | 内置 preset 默认关闭 | 要保留则按 preset 覆盖 `interrupt: true` |
| 配置 | worktree bundle | bundles 含 `@deepseek-ai/dsh-experimental-tool-worktree` | 已并入新工作树/变更请求入口 | 从 `dsh.profile.bundles` 移除 |
| 配置 | 网页搜索 | 内置 DeepSeek 搜索 + argo-dsh（Tavily/Firecrawl） | 默认改 DeepSeek Search API 计费（auto/account/api-key） | 验证搜索与计费；必要时配 `searchBilling` |
| 配置 | 终端 bundle | 无本地 patch | 改为侧栏终端面板，需终端控制器（Web 已有） | 重启后验证 |
| 数据 | 78 个 session 目录、39 张工单、`orchestrator.sqlite`（约 2.2MB + WAL） | — | 存储支持读取旧版本 | 升级前备份 |

### 3.3 关键运行时风险（必须人工确认）

1. **`dsh-superagent` 的角色模型逻辑**：`src/app/role-models.ts` 通过 `agent/request` 改写 provider/model。0.2.2 的 `agent-loop` 会在「提出的路由 ≠ step 准备时固定的 selection」时直接 `throw`（`packages/core/agent-loop/src/agent.ts:642`）。该插件同时先写了 `model/selection` 事件，因此多数路径可能刚好一致，但这是**边界行为**，必须实测/适配为 `agent.model.select()`，不能赌。
2. **客户端 UI**：本机有 10+ 个客户端扩展（superagent 面板、memory-evolve、better-sidebar、kanban、媒体台等）。0.2.2 改了菜单定位/侧栏/设置等客户端接口（rc.2 明确「自定义浮层需适配新定位接口」），需要逐页冒烟。
3. **旧 hooks 桥接**：旧版 `dsh-hooks-claude-code` 注入 `sessionProjections`（0.2.2 中已弃用但保留），功能大概率仍可用，但会有弃用告警；应随 checkout 升级到 rc.3 版本。
4. **`dsh-memory-evolve`**：体量大、接口多，且依赖 DSH 的 runtime-context 物化行为（0.2.2 对 `<system-reminder>` 包装/清空标记有变化），需重点回归记忆与注入链路。

---

## 4. 升级执行清单（建议维护窗口）

### Phase 0：预检与备份（10 分钟）

```bash
# 版本与状态
dsh --version                                   # 期望 0.2.1-rc.5
ls ~/.dsh/profiles/superagent/{package.json,cordis.patch.yml}

# 备份（不可省）
mkdir -p ~/.dsh/backup/0.2.2-upgrade-$(date +%F)
cp ~/.dsh/hooks.json ~/.dsh/backup/0.2.2-upgrade-$(date +%F)/
cp ~/.dsh/profiles/superagent/{package.json,cordis.patch.yml} ~/.dsh/backup/0.2.2-upgrade-$(date +%F)/
sqlite3 ~/.dsh/state/superagent-fresh/orchestrator.sqlite \
  ".backup '$HOME/.dsh/backup/0.2.2-upgrade-$(date +%F)/orchestrator.sqlite'"

# 确认没有在跑工单（看 ~/.dsh/sessions 最近修改与 ticket 表）
```

### Phase 1：源码与链接包（30–60 分钟）

```bash
cd ~/deepseek-harness
# 唯一本地改动是 chmod +x apps/desktop/cli/dsh，先记下来
git diff --stat
git fetch --tags origin
git checkout dsh-v0.2.2-rc.3
pnpm install
pnpm build          # 或至少构建 hooks-claude-code / subagent-codex / subagent-claude-code
chmod +x apps/desktop/cli/dsh
```

### Phase 2：本地插件适配（2–4 小时，估计）

- `~/dsh-superagent-prototype`：
  - 把 `engines.dsh` / `@deepseek-ai/*` peer 范围更新到 `^0.2.2-rc.3`（或 `>=0.2.1-alpha.2 <0.3.0`）；
  - 复核 `role-models.ts` 的 `agent/request` 覆盖 → 改用 `agent.model.select()`；
  - `sessionProjections.stateOf(session,key)` → 新的 handle/`turnBoundaryOf` 读法；
  - `pnpm typecheck && pnpm test && pnpm build`，再手工点一遍工单面板/设置页。
- `dsh-memory-evolve` 与其他本地插件：跑一遍核心功能（记忆、待办、技能、统计、抖音、图谱桥），有报错按新 API 修。

### Phase 3：全局安装与 profile 配置（20 分钟）

```bash
# 先停宿主，避免运行中进程与新包混用
PID=$(lsof -tiTCP:3082 -sTCP:LISTEN | head -1); [ -n "$PID" ] && kill "$PID"

npm i -g @deepseek-ai/dsh@0.2.2-rc.3
dsh --version          # 期望 0.2.2-rc.3
```

在 `~/.dsh/profiles/superagent/cordis.patch.yml` 里按需增加/修改：

```yaml
# 保留「先读后写」防护（0.2.2 默认关闭）
- id: fs-observation-policy
  disabled: false
```

```yaml
# 如果 superagent 的 worker preset 需要 interrupt_agent：
# 按升级指南，在对应 preset 行（preset-standard / preset-cordis / preset-ptc）
# 的 tool-subagent-control 配置里设 interrupt: true；顶层 tool-subagent-control 行无效。
```

同时从 `package.json` 的 `dsh.profile.bundles` 移除：

```text
@deepseek-ai/dsh-experimental-tool-worktree
```

检查组合：

```bash
dsh --profile superagent --dump-config | less
# 关注：是否有 denied / skippedBundles / 配置缺失
```

### Phase 4：重启与冒烟（30–60 分钟）

```bash
~/.dsh/bin/super-restart.sh superagent
# 约 10–20 秒就绪，脚本会打印本次登录链接
```

冒烟清单（按顺序）：

1. 启动日志无 `denied` / `skippedBundles`，Web 页面能开。
2. Feishu 里 @机器人 一句话，确认收/发正常。
3. Hooks e2e：跑一个应被拦的命令（如 `gh auth login` 走 gate_pretool）确认被拒；写一个未读文件确认 docs_gate 行为；确认 PostToolUse 的 lessons 记录仍在。
4. 会话恢复：打开一个旧会话，确认历史可读；新建会话发一条消息。
5. 记忆：读一条 memory、写一条 daily、跑一次 `dtodo list`。
6. 模型：orchestrator/router/worker 角色模型、reasoning effort 是否符合预期（重点看 `dsh-superagent`）。
7. UI：侧栏、会话列表、工单面板、设置页、插件页、kanban、媒体台。
8. 真跑一个低风险工单（例如问一个只读问题），确认派单/回收正常。

### 回滚方案

```bash
PID=$(lsof -tiTCP:3082 -sTCP:LISTEN | head -1); [ -n "$PID" ] && kill "$PID"
npm i -g @deepseek-ai/dsh@0.2.1-rc.5
cd ~/deepseek-harness && git checkout dsh-v0.2.1-rc.5 && pnpm install && pnpm build
cp ~/.dsh/backup/0.2.2-upgrade-<date>/{hooks.json,package.json,cordis.patch.yml} ...  # 放回原位
~/.dsh/bin/super-restart.sh superagent
```

注意：回滚后，**升级期间新建的会话/工单数据可能无法被旧版本读取**（存储承诺的是「新版本读旧数据」，不是反向兼容）。所以先在低风险会话验证，再切生产工单。

---

## 5. 是否值得更新（判断）

### 5.1 值得的点

- **功能增量大且对路**：worktree/PR 审阅、具名多层子代理、插件在线更新、会话 Markdown 复制、MCP 动态注册、终端接管、搜索 10 来源、模型重试设置，都是本机值守/调研/工单流的直接能力。
- **修复密度高**：80 条修复里大量是长会话、子代理轮询、后台任务通知、上下文压缩/恢复、重复提交这类「值守场景痛点」。
- **不升级的机会成本**：0.2.1 线已停在 rc.5，后续第三方插件与文档会逐步只对 0.2.2 验证；继续留在旧 RC 不是「更稳」，只是「更旧」。
- 本机 Node 24.15 已满足新要求，硬件/运行时无需额外准备。

### 5.2 成本与风险

- **一次迁移不可避免**：3 个源码 link 包 + 7 个自研插件 + 13 个第三方插件 + 5 条 hooks + profile 配置，需要逐项冒烟；估计 0.5–1 天（含验证），失败要回滚。
- **`dsh-superagent` 是最大风险点**：它同时用到被 0.2.2 改动的 model/projection/tools/prompt/客户端接口。版本门禁能过，但运行时行为必须实测。
- **pre-release 风险**：0.2.2-rc.3 发布仅 1 天，虽已累积 rc.2 的修复，但仍可能有新回归。
- **重启有中断成本**：当前多个活跃工单会话会被打断；虽然可恢复，但别在交付窗口做。

### 5.3 建议

| 场景 | 建议 |
|---|---|
| 想要 worktree/PR 审阅、新子代理、稳定性修复，且能安排半天窗口 | **升级到 0.2.2-rc.3**（推荐） |
| 近期工单密集、不能中断 | 先不动，排到空窗；不要用 `latest`（rc.1） |
| 追求最低风险 | 等 0.2.2 正式版，但本地迁移工作照做 |

---

## 6. 未验证与限制

- **未做真实 0.2.2 启动验证**：避免与线上 Feishu/GitHub 值守实例冲突（会重复接消息/重复派单），因此「可启动、可跑工单」是基于源码、清单与发布说明的静态判断，不是实测结论。
- 13 个第三方插件的客户端 UI 未逐个源码审计；UI 风险按「升级后冒烟」处理。
- `dsh-superagent` 的迁移工时是估计值，未实际改代码验证。
- 版本/发布时间/插件清单为 2026-11-14 09:30 CST 快照；之后发布的新版本未覆盖。
- 回滚只保证配置/版本可回退，不保证升级后新建数据的向下兼容。

## 7. 证据与来源

- npm registry：`@deepseek-ai/dsh` 的 `dist-tags` 与 `time`（见 `work/dsh-upgrade-evidence/versions.txt`）
- GitHub Releases / tags：`dsh-v0.2.2-rc.1/2/3` 发布说明（中文新增/优化/修复/其他变更条目）
- 本地源码（tag `dsh-v0.2.2-rc.3`）：
  - `packages/boot/app-boot/src/plugin-compatibility.ts:52`（engines.dsh + includePrerelease）
  - `packages/core/agent-loop/src/agent.ts:642`（agent/request 路由一致性检查）
  - `packages/session/session-projection/README.zh.md:90`（旧 stateOf 弃用）
  - `packages/experimental/hooks-claude-code/src/index.ts`（inject 改 agents）
- 官方升级指南：`docs/upgrade-guide/v0.2.2-rc.1/*`、`v0.2.2-alpha.2/*`
- 本机：`~/.dsh/profiles/superagent/{package.json,cordis.patch.yml}`、`~/.dsh/hooks.json`、`~/.dsh/state/superagent-fresh/orchestrator.sqlite`、`ps` 进程信息

## 附录：本机插件清单（23 个）

- 源码 link（3）：`@deepseek-ai/dsh-hooks-claude-code`、`@deepseek-ai/dsh-subagent-claude-code`、`@deepseek-ai/dsh-subagent-codex`（0.2.1-rc.5）
- 本地自研（7）：`@local/answer-consistency-gate` 0.1.0、`@local/douyin-subscription` 1.0.0、`@local/sr-workbench` 0.1.0、`@local/stat-research-gate` 2.10.1、`dsh-memory-evolve` 0.1.0、`dsh-superagent` 0.1.0、`graphmind-bridge` 0.2.0
- npm/第三方（13）：`@alpacachen/dsh-kanban` 1.11.1、`@dhicoc/dsh-reverse-skill`、`@liustack/modlens` 3.27.2、`@mingozhou/dsh-replay` 1.0.0、`@taxueseek/argo-dsh` 2.9.8、`agentero-dsh` 0.1.8、`dsh-better-sidebar` 0.28.0、`dsh-bilibili` 0.8.0、`dsh-builtin-browser` 0.4.15、`dsh-context` 0.83.1、`dsh-guizang-design` 0.1.4、`dsh-media-desk` 2.7.0、`dsh-routing-suite` 0.1.2
