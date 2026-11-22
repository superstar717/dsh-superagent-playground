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

## 未验证 / 已知限制（不当作已验证）

1. **线上 GUI 的审批点击路径**未实际点过：审批 ask 的注册由单元测试 + headless fail-closed 证明；线上有 approval 服务，预期弹窗。
2. **superagent profile 冷启动**未重启验证：headless 临时 profile 是真实冷启动加载测，但 superagent 的完整组合未重启；`--dump-config` 已证明组合，下一次正常重启会加载它。
3. `mode` 的 `plan/build/edit/yolo` 未逐个跑真实任务；仅验证 `guarded` 与参数构造/白名单。
4. `attach` / `resume` 未对真实 ZCode 跑通（仅 argv 构造与单测；ZCode 文档确认参数面）。
5. 超时/取消的真实 ZCode 长任务未构造（`runProcess` 层已用 fake 长任务验证杀进程组）。
