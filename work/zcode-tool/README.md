# @local/zcode-tool

把 ZCode CLI（Z.ai GLM coding agent）注册为 DSH 工具 `zcode_run`。本地插件，唯一事实源是本目录（git 管理），安装方式为链接进 DSH profile。

- 插件目录：`~/.dsh/plugins/zcode-tool/`
- 包名：`@local/zcode-tool`（`package.json` 的 `dsh.bundle.patch` → `cordis.patch.yml`）
- 宿主契约：DSH `0.2.2-rc.3`（`ctx.tools.register` 原生 JSON Schema 工具 + `tools/pre-execute` 审批）
- ZCode 契约：本机 `zcode` 0.17.1（源码构建 v3.18.2，`--prompt` / `--mode` / `--output-format json` / `--attach` / `--resume`）

## 1. 工具契约

`zcode_run` 一次调用 = 一个 `zcode --prompt ...` 无头进程，同步等待结束或超时。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|---|---|---|---|---|
| `task` | string | 是 | — | 交给 ZCode 的 prompt；非空，≤ 100,000 字符 |
| `cwd` | string | 否 | 当前 Session 工作目录 | 相对路径按 Session 工作目录解析；必须存在且是目录 |
| `mode` | enum | 否 | `guarded` | `guarded` / `plan` / `build` / `edit` / `yolo` |
| `timeout_ms` | integer | 否 | 600000 | 实际墙钟上限；部署可配上限（默认 1800000） |
| `attach` | string[] | 否 | `[]` | 重复传 `--attach`；相对路径按 cwd 解析，必须是文件 |
| `resume` | string | 否 | — | 以 `--resume <sessionId>` 续跑已有 ZCode 会话 |

返回规范值（模型看到的是渲染后的文本，含同样字段）：

```json
{
  "ok": true,
  "exitCode": 0,
  "sessionId": "sess_...",
  "stdout": "...",
  "stderr": "...",
  "timedOut": false,
  "durationMs": 60537
}
```

- `ok` **只表示 ZCode 进程退出码为 0**，不代表任务成功。任务是否成功要看 `stdout` 里的 JSON（`response`、`usage`、`projection`）或产物；`stderr` 里可能有 CLI 诊断（例如 `ZCode Built-in skipped (not-due)`）。
- `sessionId` 从 stdout JSON 提取；stdout 被截断时用正则兜底；没有则 `null`。
- `exitCode` 在超时/被信号杀死时为 `null`；`timedOut=true` 单独标记超时。
- stdout/stderr 各最多收集 2,000,000 字符，模型可见输出各截断到 200,000 字符并附截断说明。

## 2. 安全模型（插件版相对 skill 版的硬保障）

1. **显式权限模式**：`zcode --prompt` 的默认模式是 `yolo`（跳过权限提示）。本插件**永远显式传 `--mode`**，参数缺省时固定 `guarded`，从不依赖 ZCode 默认值。
2. **进程组终止**：子进程以独立进程组启动（POSIX `detached:true`），超时或调用方取消时 `SIGTERM` 整个进程组，5 秒后 `SIGKILL`；另有 3 秒硬结算兜底，保证工具不会挂死。Windows 走 `taskkill /T /F`。
3. **DSH 审批**：注册 `tools/pre-execute`，默认对每次 `zcode_run` 返回 `{kind:'ask'}`，由 DSH 审批服务弹窗；批准理由包含 mode/cwd/task 摘要并留痕。无审批通道（headless）时安全拒绝。部署可显式 `requireApproval: false` 关闭（仅建议隔离的无人值守 profile）。
4. **输入校验**：`task` 非空、`mode` 白名单、`timeout_ms` 正整数且不超上限、`cwd`/`attach` 存在性与类型、未知参数拒绝；相对路径按 Session 工作目录解析，避免继承宿主启动目录。
5. **无 shell 拼接**：`spawn(command, argvArray)`，`shell:false`，任务文本不会进入 shell。
6. **输出有界**：stdout/stderr 双上限，避免长会话撑爆上下文。

未覆盖的边界：ZCode 自身仍是完整 coding agent，`guarded` 之外的 `edit`/`yolo` 等能力由调用方显式选择并受审批约束；本插件不提供 OS 级沙箱，ZCode 能访问的文件/网络权限取决于宿主进程权限。

## 3. 部署配置

`cordis.patch.yml` 默认值：

```yaml
- insert:
    - id: zcode-tool
      name: '@local/zcode-tool'
      config:
        requireApproval: true
        defaultTimeoutMs: 600000
        maxTimeoutMs: 1800000
```

可选 `config` 字段：

| 字段 | 默认 | 说明 |
|---|---|---|
| `zcodePath` | 自动 | 留空时优先 `~/.local/bin/zcode`，否则 PATH 里的 `zcode` |
| `requireApproval` | `true` | 每次调用前走 DSH 审批；headless 可显式关闭 |
| `defaultTimeoutMs` | `600000` | `timeout_ms` 未传时的上限 |
| `maxTimeoutMs` | `1800000` | `timeout_ms` 允许的最大值 |

## 4. 安装 / 生效 / 回滚

安装到 profile（以 `superagent` 为例）：

1. `~/.dsh/profiles/superagent/package.json`：`dependencies` 加 `"@local/zcode-tool": "link:/Users/huweixing/.dsh/plugins/zcode-tool"`，`dsh.profile.bundles` 末尾加 `"@local/zcode-tool"`；
2. `~/.dsh/profiles/superagent/node_modules/@local/zcode-tool` 软链到插件目录；
3. 验证组合：`dsh --profile superagent --dump-config | grep -A4 zcode-tool`；
4. 生效：profile 启用了 `dsh-hmr` 时，bundle 列表变化会触发热重载（无需重启）；否则重启宿主
   `nohup ~/.dsh/bin/super-restart.sh superagent >/tmp/… 2>&1 & disown`。
5. 回滚：删掉 `bundles` 里的 `@local/zcode-tool` 与依赖、删软链，等 HMR/重启；插件源码目录保留即可随时恢复。

## 5. 验证

本机执行（2026-11-22）：

- 单元测试：`npm test`（`node --test test/*.test.js`）——参数构造/校验、JSON 解析、sessionId 提取、审批判定、cwd/attach 校验、超时/取消/启动失败的进程组终止、fake ZCode 二进制的端到端 `execute`。20/20 通过。
- 真实 ZCode 集成：`guarded` 模式小任务，exit 0、`sessionId=sess_67c6b3a0-b475-48a9-8e3f-9a19c7353a00`、`response=正常`、60.5 s、66,536 tokens（消耗 Z.ai coding 配额）。
- headless 宿主加载测：临时 profile（base + headless + 本插件，`requireApproval:false`）真实启动 DSH，模型调用 `zcode_run` 成功：`sessionId=sess_a1731b1c-2bfb-46ce-8518-66893c5ba8a1`、`response=正常`、57.2 s、66,509 tokens，DSH 会话事件 `tool/result isError=false`。
- 审批默认值实测（同一临时 profile + `--patch` 覆盖回 `requireApproval:true`）：真实 headless 宿主上工具被拒，`isError=true`、`error.name=ApprovalError`、`error.code=APPROVAL_UNAVAILABLE`、正文 `Error: tool "zcode_run" requires approval, but no approval channel is available`；ZCode 进程未启动（拒绝发生在 pre-execute 阶段）。
- 线上 superagent profile：`dsh --profile superagent --dump-config` 可见 `@local/zcode-tool` 插入行；宿主 HMR 已热加载（无需重启），通过宿主 inspector（127.0.0.1:9230 CDP，Host realm）读取 Cordis 根 Context 的 `tools.schemas()`，126 个工具中包含 `zcode_run`，参数为 `task/cwd/mode/timeout_ms/attach/resume`、`mode` 枚举含 `guarded` 且默认 `guarded`。

复测命令（推荐顺序）：

```bash
cd ~/.dsh/plugins/zcode-tool
node scripts/verify-live.mjs          # 零成本：本地契约 + 线上宿主注册（inspector 读 Cordis 注册表）
node scripts/verify-live.mjs --real   # 追加一次真实 ZCode 调用（消耗 Z.ai 配额，需已登录）
npm test                              # 20 项单元测试（fake ZCode，不耗配额）
```

`verify-live.mjs` 默认输出示例：

```text
[PASS] local contract: default mode=guarded, params=task,cwd,mode,timeout_ms,attach,resume, approval=ask
[PASS] live host registration (inspector 9230): 126 tools, zcode_run found, params=task,cwd,mode,timeout_ms,attach,resume, mode default=guarded
Result: PASS (plugin is loaded in the live host; ...)
```

退出码 0=PASS、1=FAIL；`--json` 输出机器可读结果；宿主 inspector 端口默认从 `~/.dsh/state/dsh-superagent-restart.log` 自动发现，可用 `--inspector-port` 覆盖。线上 GUI 的「审批弹窗点击」无法由脚本验证，需人工按第 5 节 GUI 路径点一次。

## 6. 已知限制

- **同步阻塞**：长任务会占用一次工具调用直到结束/超时（上限默认 30 分钟）；没有后台 job 集成。超长任务应拆小或提高 `timeout_ms`（部署上限内）。`timeout_ms` 到点先 SIGTERM，最多再等 5 秒 SIGKILL + 3 秒硬结算，因此实际返回可能比 `timeout_ms` 晚至多约 8 秒。
- **配额**：真实调用消耗 Z.ai GLM coding 配额（每次含完整 ZCode 系统提示词，实测小任务约 6.6 万 input tokens）。
- **版本耦合**：依赖 ZCode CLI 的 `--mode`/`--output-format json`/`--resume`/`--attach` 参数面（本机 0.17.1 验证）。ZCode 升级后先跑 `zcode --help` 与本插件单测/集成测。
- **审批语义**：`ok` 是进程级结果；ZCode 内部的工具失败可能仍以 exit 0 结束，需要读 stdout/stderr。
- **guarded 在无人值守时的拒绝**：ZCode 的 `guarded` 对危险操作仍需其自身审批客户端；headless（含 DSH 工具调用）没有 ZCode 审批通道时，这些操作会失败而不是自动放行。这是刻意安全默认；确实需要无人值守写文件时，显式选 `edit`（工作区编辑通常免审批）或隔离环境下的 `yolo`，并自行承担风险。
- **输出截断**：超长 stdout 会截断，完整会话请用返回的 `sessionId` 在 ZCode 侧查看（`zcode --resume <sessionId>`）。

## 7. 文件

```
index.js           插件本体（工具注册 + 审批 + 子进程管理）
cordis.patch.yml   bundle 层：插入 zcode-tool 行
package.json       包清单（dsh.bundle.patch）
test/              node:test 单元测试（无外部依赖）
README.md          本文件
```
