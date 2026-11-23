# zcode-tool 验证记录（2026-11-22）

工单：`3b6d806d01eaf1184ece5c3da470dd99`（实现 ZCode DSH 插件 / zcode_run）
宿主：DSH `0.2.2-rc.3`，ZCode CLI `0.17.1`（源码构建 v3.18.2，`~/.local/bin/zcode`）
插件：`@local/zcode-tool` v0.1.0，目录 `~/.dsh/plugins/zcode-tool/`

结论：**四层验证全部通过，插件已在 superagent profile 通过 HMR 热加载并注册 `zcode_run`（未重启宿主）。**
未验证项见文末，不当作已验证。

---

## ① 单元测试（无外部依赖）

```bash
cd ~/.dsh/plugins/zcode-tool && npm test
```

`node --test test/*.test.js` → **20/20 pass**（2026-11-22）。覆盖：

- `normalizeConfig` 默认值/坏类型回退；
- `normalizeToolArguments` 默认 guarded、白名单、task 非空/长度、timeout 正整数与上限、attach 单值/数组、resume、未知参数；
- `buildZcodeArgs` **永远显式带 `--mode`**、attach 重复、resume；
- `parseZcodeJson` / `extractSessionId`（干净 JSON、带噪声、pretty-print、截断 JSON 正则兜底、缺失 → null）；
- `approvalDecision` 默认 ask、可关闭、其他工具放行、长 task 摘要；
- `resolveCwd` / `resolveAttachments` 相对路径解析与存在性/类型校验；
- `runProcess` 成功、非零退出、**超时杀进程组**、调用方 abort、spawn ENOENT；
- `apply` 注册工具与 `tools/pre-execute`；fake ZCode 二进制的 `execute` 端到端（含 argv 断言与错误路径）。

已知测试环境噪声：首次执行新写入的可执行脚本可能被 macOS 首次执行校验拖慢 ~5 s（同一脚本第二次 <0.5 s），不影响超时/杀进程断言。

## ② 真实 ZCode CLI 集成（消耗 Z.ai 配额）

通过插件 `execute` 路径（临时 fake ctx，`requireApproval:false`，真实 `~/.local/bin/zcode`）：

- 任务：`只回复两个字：正常。不要调用任何工具。`
- 参数：`mode='guarded'`，`timeout_ms=180000`
- 结果（2026-11-22 21:10）：

```json
{
  "ok": true,
  "exitCode": 0,
  "sessionId": "sess_67c6b3a0-b475-48a9-8e3f-9a19c7353a00",
  "timedOut": false,
  "durationMs": 60537,
  "stdout": "{\"sessionId\":\"sess_67c6b3a0-...\",\"response\":\"正常\",\"usage\":{\"inputTokens\":66497,\"outputTokens\":39,\"totalTokens\":66536,...}}",
  "stderr": "ZCode Built-in skipped (not-due)\n"
}
```

说明：`stderr` 的 `ZCode Built-in skipped (not-due)` 是 CLI 自身诊断，`ok` 仍按进程退出码判定。

## ③ headless 宿主加载 + 端到端（真实 DSH 进程）

临时 profile `~/.dsh/profiles/zcode-smoke/`：bundles = `@deepseek-ai/dsh-base` + `@deepseek-ai/dsh-headless` + `@local/zcode-tool`；profile patch 把 `zcode-tool.config.requireApproval` 覆盖为 `false`。

```bash
source ~/.dsh/state/superagent.env
dsh --profile zcode-smoke "Use the zcode_run tool with task '只回复两个字：正常。不要调用任何工具。' and cwd '/tmp/zcode-smoke-work'. Then reply with exactly: sessionId=<the sessionId from the tool result>, ok=<the ok value>."
```

- 进程退出 0，最终答复 `sessionId=sess_a1731b1c-2bfb-46ce-8518-66893c5ba8a1, ok=true`。
- 会话事件（`~/.dsh/sessions/--private-tmp--/session-1eeb4f6a-.../session.v4.jsonl.zstd`）：
  - `tool/call`：`zcode_run`，arguments `{"task":"只回复两个字：正常。不要调用任何工具。","cwd":"/tmp/zcode-smoke-work"}`（mode 未传 → 默认 guarded）；
  - `tool/result`：`isError=false`，content `[zcode_run] ok · mode=guarded · exit=0 · 57.2s · sessionId=sess_a1731b1c-...`，stdout JSON `response=正常`、`totalTokens=66509`。

## ④ 审批默认值 fail-closed（真实 headless 宿主）

同一临时 profile 再叠加 `--patch /tmp/zcode-approval-patch.yml`（`requireApproval: true`），让模型调用 `zcode_run`：

- 会话事件 `tool/result`：`isError=true`，`error.name=ApprovalError`，`error.code=APPROVAL_UNAVAILABLE`，正文：
  `Error: tool "zcode_run" requires approval, but no approval channel is available`
- 拒绝发生在 `tools/pre-execute` 阶段，ZCode 进程未启动（模型随后的 `ls /tmp/zcode-smoke-work` 仅看到空目录）。

## ⑤ 线上 superagent profile 安装 + HMR 生效（未重启）

变更（`~/.dsh/profiles/superagent/`）：

- `package.json`：dependencies 增加 `"@local/zcode-tool": "link:/Users/huweixing/.dsh/plugins/zcode-tool"`；`dsh.profile.bundles` 末尾增加 `"@local/zcode-tool"`。
- `node_modules/@local/zcode-tool` → 插件目录软链。
- 备份：`package.json.bak-zcode-20261122-211525`、`cordis.patch.yml.bak-zcode-20261122-*`（profile patch 仅短暂加过注释用于触发 reconcile，已还原，最终与备份逐字节一致）。
- 锁文件：`pnpm-lock.yaml` 增加对应 link importer 条目（`specifier: link:/Users/huweixing/.dsh/plugins/zcode-tool`、`version: link:../../plugins/zcode-tool`；备份 `pnpm-lock.yaml.bak-zcode-*`），避免后续 pnpm frozen-lockfile 操作因清单/锁不一致失败。

组合验证：

```bash
dsh --profile superagent --dump-config | grep -A5 zcode-tool
# == @local/zcode-tool
# - id: zcode-tool
#   name: '@local/zcode-tool'
#   config:
#     requireApproval: true
#     defaultTimeoutMs: 600000
#     maxTimeoutMs: 1800000
```

**HMR 实际生效**（无需重启）：宿主 inspector（`http://127.0.0.1:9230/json`）暴露当前 Host 的 CDP target；用 WebSocket 连上后在 Host realm 执行 `Runtime.evaluate`，从 Cordis 根 Context 读 `tools.schemas()`：

```js
// 关键片段：inspector 的 Host realm 保留 Cordis 对象
const table = globalThis[Symbol.for('dsh.inspector.realm-object-registries')]
let root
for (const registry of table.values()) root = registry.retained.get('object-1')
const names = root.get('tools').schemas().map(schema => schema.name)
// 126 个工具，最后一项为 "zcode_run"
```

进一步读 schema：

```json
{
  "found": true,
  "description": "Run one non-interactive ZCode CLI prompt (Z.ai GLM coding agent) against a working directory. Use this when a task needs",
  "properties": ["task", "cwd", "mode", "timeout_ms", "attach", "resume"],
  "required": ["task"],
  "modeEnum": ["guarded", "plan", "build", "edit", "yolo"],
  "modeDefault": "guarded"
}
```

恢复 profile patch 精确内容后再次探测，`zcode_run` 仍在（HMR 产物稳定）。

复测入口：`node scripts/verify-live.mjs`（零成本，含上述 inspector 探针；2026-11-22 实测输出 `126 tools, zcode_run found`、退出码 0）；`--real` 追加一次真实 ZCode 调用（已用 fake 二进制验证脚本路径，真实路径与 ② 相同）。

注意：`ctx.logger.info` 的插件自报行没有出现在 `~/.dsh/state/dsh-superagent-restart.log`，**不能以日志缺席判断插件未加载**；本次以运行期注册表为准。

---

## ⑥ 线上 GUI 真实调用 + 审批放行（2026-11-22 22:04 追加）

在**真实 superagent 宿主**（非临时 headless profile）的 GUI 会话 `session-5a27dc07-6031-4453-9928-4655d7ef74d6` 中由模型调用 `zcode_run`：

- 参数：`task=只回复两个字：正常，不要调用任何工具`、`cwd=/tmp`、`mode=guarded`、`timeout_ms=180000`；
- 审批链（该会话 `session.v4.jsonl.zstd` 事件）：`approval/policy=ask`（seq 2）→ `approval/asked`（seq 22，toolName=`zcode_run`，reason 含 mode/cwd/task 摘要）→ `approval/decided`（seq 23，outcome=`allowed-once`，距 asked 4.58 s）；
- 执行结果：`ok`、exit=0、71.0 s、`response=正常`、`sessionId=sess_3e379a15-d56c-405b-9862-35ced9fb53d8`、usage input 91,122 / output 3；
- 意义：**线上 GUI 首次走通「ask → 放行 → 真实执行」全链路**（此前审批证据只有单测 + headless fail-closed 拒绝）；同时证明 HMR 加载后的 live 宿主可直接执行，且 `cwd` 指向工作区外（`/tmp`）可行。
- 未证实边界：事件只能证明「存在审批决定且 outcome=allowed-once」，**无法区分是人工点击还是配置的自动应答器**；要 100% 确认点击路径，需人工在弹窗里点一次并当场观察。

---

## ⑦ 审批策略 = `never` 时的线上 fail-closed（2026-11-22 22:09 追加）

把会话审批策略从 `ask` 切成 `never`（`approval/policy` seq 157）后，在同一 live 会话、同参数再调一次 `zcode_run`：

- 事件链：`approval/asked`（seq 191）→ `approval/decided`（seq 192，`outcome=rejected`）；
- 工具结果：`isError=true`、`error.name=ApprovalError`、`error.code=APPROVAL_REJECTED`，正文 `Error: the user rejected tool "zcode_run"`；
- 副作用核查：`pgrep -fl "zcode.cjs"` 无进程 → **ZCode 未启动、零配额消耗**；
- 结论：**「never ask」≠ 自动放行，等价于自动拒绝**。与 ④ 的 headless 拒绝是两条不同错误码：

| 场景 | error.code |
|---|---|
| 无审批通道（headless，`requireApproval: true`） | `APPROVAL_UNAVAILABLE` |
| 通道存在但策略=`never`（自动拒绝） | `APPROVAL_REJECTED` |

- 运维含义：superagent profile 默认 `requireApproval: true`，故会话策略为 `never` 时 `zcode_run` 永久不可用。要用需二选一：①策略回 `ask` 并人工点允许一次；②在 profile patch 把 `zcode-tool.config.requireApproval` 置 `false`（等于放弃逐次审批，只适合受信部署/headless，如 ③ 的冒烟 profile）。→ **已按 ② 落地，实际生效验证见 ⑧（2026-11-22 22:11）。**

---

## ⑧ 关闭逐次审批（`requireApproval: false`）线上生效（2026-11-22 22:11 追加）

背景：会话审批策略为 `never` 时 `zcode_run` 被自动拒绝（⑦）。用户选择方案②，在 live profile patch 显式关掉逐次审批：

- 变更：`~/.dsh/profiles/superagent/cordis.patch.yml` 追加
  ```yaml
  - id: zcode-tool
    config:
      requireApproval: false
  ```
  备份 `cordis.patch.yml.bak-zcode-approvaloff-20261122-221030`；写入前用 pyyaml 解析校验（12 条 entry、该 entry 可解析），再以 `mv` 原子替换（权限 0600）。
- 组合确认：`dsh --profile superagent --dump-config` 输出
  `# == @local/zcode-tool, patched by .../cordis.patch.yml` + `config: {requireApproval: false}`。
- 线上生效（**未重启宿主**）：22:11 再调 `zcode_run`（同参数）→ `ok`、exit=0、**35.6 s**、`response=正常`；该会话事件中**没有新增 `approval/asked`**（最后一条审批事件仍是 seq 192 的拒绝），证明 `tools/pre-execute` 不再返回 `{kind:'ask'}`，patch 被 live reconcile 立即采纳。
- 代价（用户已知情接受）：该 profile 内所有 `zcode_run` 调用不再经人工确认；`mode=guarded` 仍约束 ZCode 自身权限提示，但已无 DSH 层逐次审批。
- 回滚：还原上述备份，或删除该 entry（`mv` 原子替换后无需重启）。

---

## ⑨ 冷启动验证（意外完成）与验证方式的事故（2026-11-22 22:14–23:08）

- 事实：22:14–23:00 有 **33 轮**「延迟重启 → 探针 → 写日志」脚本被执行（`~/.dsh/state/coldstart-zcode.log`），其中 **30 轮** `verify-live.mjs` 输出 PASS：`126 tools, zcode_run found`，且每轮 `dump-config` 均为 `requireApproval: false`。
- 结论：**superagent 冷启动后插件仍加载、profile patch 仍生效**（30 次独立重启的证据）——原「未验证 #2 冷启动」关闭。
- 代价（必须一起记）：该脚本是用 `launchctl submit` 挂的，submit 作业**无条件保活**（2026-11-22 23:41 独立复现：`exit 0` 的 3 秒脚本 46 s 内被重拉 5 次，`launchctl print` 显示 `properties = keepalive`；`man launchctl` 的 "in the event of failure" 措辞有误导性），导致宿主在 **45.7 分钟内被 SIGKILL 重启 32 次**；作业在会话结束后仍跑了 45 分钟（详见 `work/项目复盘-zcode-plugin-2026-11-22.md` 第八节、LESSONS E212）。
- 现行状态：作业 `com.zcode.coldstart-verify` 已 `bootout`；脚本已替换为空转版（`exit 1`，**勿 `bootstrap` 回去**）；原脚本忠实备份 `~/.dsh/state/coldstart-verify-zcode.sh.bak-loop-20261122`（sha256 `f746fde2…`，从会话 `tool/call` seq 562 原始 heredoc 重建）。
- 复跑规则：**再验冷启动一律前台跑**，不要 `launchctl submit`；跑完确认 `launchctl list | grep coldstart` 为空。

---

## ⑩–⑫ 真实任务矩阵（2026-11-24 追加，`scripts/verify-real-matrix.mjs`）

复用 ② 的模式（fake ctx 直调插件 `execute`，真实 `~/.local/bin/zcode`，`requireApproval:false`），每场景独立 mkdtemp 沙盒，逐场景前台跑。**7/7 PASS**（2026-11-24 实测）：

| # | 场景 | 结果 | 关键证据 |
|---|---|---|---|
| ⑩a | `plan` | PASS 56s | 读 note.txt 并原样复述 marker；沙盒无模型写入（模型自述「未创建/修改/删除、未执行命令」）——plan 的写入/命令限制生效 |
| ⑩b | `build` | PASS 179s | Write/Bash 均被拒：`No permission client configured for Write` / `...for Bash`；**CLI 仍 exit 0**（与权限文档「工具拒绝后进程也可能返回 0」逐字吻合）；模型如实报告并未绕过 |
| ⑩c | `edit` | PASS 94s | `edit.txt` 创建成功（content=`ok`）——工作区编辑免审批生效 |
| ⑩d | `yolo` | PASS 90s | bash `printf 'ok\n' > yolo.txt` 执行成功并被模型自校验（cat/od）——命令放行生效 |
| ⑪a | `attach` | PASS 59s | 相对路径附件 `brief.md` → 口令 `ZCODE-ATTACH-PASS-9K4` 原文回传（`resolveAttachments` 相对解析顺带验证） |
| ⑪b | `resume` | PASS 85s | 第一跳存暗号得 `sess_3441cf04-5ace-4e73-9276-259200788ddb`；`--resume` 第二跳答出暗号「蓝鲸42」——会话连续性生效 |
| ⑫ | `timeout` | PASS 20s | `timeout_ms=15000` + yolo `sleep 300`：`timedOut=true`、`ok=false`、durationMs=17117（15s+SIGTERM 宽限）、stderr 含 `[zcode-tool] timed out after 15000 ms; process group killed`、pgrep 基线对比**无孤儿进程** |

**实测发现（非缺陷，记录在案）**：

- ZCode CLI 会在 cwd 自建脚手架点目录（`.mimosa`、`.video_agent`）——「无模型写入」断言必须过滤点文件（首跑 plan 因断言过严误 FAIL，多耗 1 次配额后修正）。
- `build` 场景 179s 明显长于其他场景：模型在写入被拒后自行排查并如实汇报（未绕过），属 plan/build 模式下模型行为的正常开销。
- 超时场景中 CLI 被杀在 JSON 输出之前 → `sessionId=null`（该路径未断言 sessionId）。

**复跑入口**：`node scripts/verify-real-matrix.mjs`（全量 7 场景）或 `--only <name>`（单场景重试，不重复烧配额）；`ZCODE_TOOL_ZCODE=<fake>` 可干跑脚本通路；`--json` 机器可读输出。

**仍不当作已验证**：调用方 abort（`AbortSignal` 取消）真实路径未构造（仅单测 fake 覆盖）；`guarded` 模式的真实长任务未单独重跑（② 的基础任务已覆盖该模式）。

---

## 未验证 / 已知限制（不当作已验证）

1. ~~**线上 GUI 的审批点击路径**未实际点过~~ → **已由 ⑥ 补上「ask→allowed-once→真实执行」证据**；残留不确定性仅为「人工点击 vs 自动应答器」不可从事件区分。
2. ~~**superagent profile 冷启动**未重启验证~~ → **已由 ⑨ 关闭**：33 轮重启中 30 轮探针 PASS（`126 tools, zcode_run found`），patch 亦在每轮 `dump-config` 中保持 `requireApproval: false`。
3. ~~`mode` 的 `plan/build/edit/yolo` 未逐个跑真实任务~~ → **已由 ⑩ 关闭**（7/7 PASS，语义与权限文档吻合）。
4. ~~`attach` / `resume` 未对真实 ZCode 跑通~~ → **已由 ⑪ 关闭**（附件内容回传 + 跨调用会话续接均实证）。
5. ~~超时/取消的真实 ZCode 长任务未构造~~ → **超时已由 ⑫ 关闭**（进程组整体被杀、无孤儿）；**取消（caller abort）真实路径仍未构造**，仅单测 fake 覆盖。
6. `verify-live.mjs` 曾把本地契约的 `approval=ask` 写死输出、易误读为线上值 → 已修正（本地行改标 `approval(default config)=ask`，新增 `live-config` 探针从 `dsh --dump-config` 读实际 `requireApproval`；2026-11-24 实测输出 `requireApproval=false (approval off)`）。
