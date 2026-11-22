# 项目复盘：ZCode DSH 插件（zcode_run）— 2026-11-22

工单：`3b6d806d01eaf1184ece5c3da470dd99`
交付：本地插件 `@local/zcode-tool` v0.1.0（唯一事实源 `~/.dsh/plugins/zcode-tool/`，git tag v0.1.0），已装入 `~/.dsh/profiles/superagent` 并通过 HMR 热加载；仓库内 `work/zcode-tool/` 为源码快照。
宿主：DSH `0.2.2-rc.3`；ZCode CLI `0.17.1`（源码构建 v3.18.2）。
完整验证命令与输出：`work/zcode-tool/VERIFICATION-2026-11-22.md`（= 插件目录同名文件）。

## 一、最终事实

1. `zcode_run` 已注册：参数 `task/cwd/mode/timeout_ms/attach/resume`，默认 `mode=guarded`；返回 `{ok, exitCode, sessionId, stdout, stderr, timedOut, durationMs}`。
2. 安全语义：**永远显式 `--mode`**（不依赖 `zcode --prompt` 的 yolo 默认）、超时/取消 SIGTERM→SIGKILL 进程组、默认每次调用走 DSH 审批（`tools/pre-execute` ask）、输出双上限。
3. 线上状态：`~/.dsh/profiles/superagent/package.json` 已加 link 依赖与 bundle 行；软链已建；`pnpm-lock.yaml` 同步补了 link importer 条目；`dsh --profile superagent --dump-config` 可见 `zcode-tool` 行；宿主 inspector 读 Cordis 根 Context 的 `tools.schemas()` 确认 126 个工具中含 `zcode_run`（schema 与代码一致）。**未重启宿主。**
4. 验证状态：单元测试 20/20；真实 ZCode `guarded` 小任务通过（60.5 s，66,536 tokens，`sessionId=sess_67c6b3a0-...`，`response=正常`）；headless 宿主端到端通过（`sessionId=sess_a1731b1c-...`，57.2 s，66,509 tokens）；审批 fail-closed 实测（`ApprovalError` / `APPROVAL_UNAVAILABLE`，ZCode 未启动）。
5. 未验证（显式标注，不当作已完成）：线上 GUI 实际点一次审批；superagent profile 冷重启；`plan/build/edit/yolo` 真实任务；`attach`/`resume` 真实调用；真实长任务超时（仅 fake 进程验证杀进程组）。

## 二、「声称完成」vs「实际验证过」

| 声称 | 证据 | 状态 |
|---|---|---|
| 工具注册与参数契约 | 单测 `apply registers...`；线上 inspector 读 `tools.schemas()` 得到 6 参数、required=task、mode 枚举/default | 已验证 |
| 默认 guarded | `buildZcodeArgs` 单测断言必带 `--mode`；真实 ZCode 调用 `mode=guarded` 通过 | 已验证 |
| 超时杀进程组 | `runProcess kills the process group on timeout`（fake 长任务，200 ms 超时、SIGTERM 后 close） | 已验证（fake）；真实 ZCode 长任务未验 |
| 调用方取消 | `runProcess honours caller aborts`（AbortController + fake 长任务） | 已验证（fake） |
| 审批默认 fail-closed | 真实 headless 宿主调用被拒：`ApprovalError/APPROVAL_UNAVAILABLE`，ZCode 未启动 | 已验证 |
| 审批 ask 正常放行（线上 GUI） | 无 | **未验证** |
| headless 宿主能加载并执行 | 临时 profile 真实 `dsh` 进程 + 会话事件 `tool/call`/`tool/result` | 已验证 |
| superagent 线上生效 | HMR 后 inspector 实时注册表含 `zcode_run` | 已验证（HMR）；冷启动未验 |
| 超时/输出截断的模型可见渲染 | 单测 render/parse；真实结果 57–60 s 文本正常 | 部分验证 |

## 三、做得对的

1. **先读官方契约再写代码**：DSH `publish/tool/adding-a-tool/tool-execution-pipeline`、`app-boot`、HMR README；ZCode `02-cli-reference/05-permissions/06-sessions/13-automation`。因此一次写对 `dsh.bundle.patch` 行、裸 `ctx.tools.register` 的 JSON Schema 形状（LESSONS E39 同款坑）、`tools/pre-execute` ask 语义。
2. **不 import `@deepseek-ai/dsh-*`**：本地 link 包只用 Node 内置模块，规避 peer 解析问题；与 stat-research-gate 策略一致。
3. **测试分层且低成本**：先 fake ZCode 二进制把 `execute` 全链路（spawn→JSON→sessionId）跑通，再花两次真实 ZCode 配额做关键验证；fake 长任务验证超时/取消，不烧配额。
4. **审批用真实宿主验证 fail-closed**：不是只测单元函数，而是在临时 profile 里真实启动 DSH、让模型调用、读会话事件确认 `APPROVAL_UNAVAILABLE` 且 ZCode 未启动。
5. **没有为了"安装生效"直接重启宿主**：先用 inspector 读运行期注册表，确认 HMR 已加载，避免中断所有 GUI 会话与本次 worker 的报告。

## 四、犯过的错（附可推翻归因的证据）

### 错误 1（中度）：把「宿主日志里没有插件日志行」当成「HMR 未加载」，差点直接重启宿主
- **事实**：改 `superagent` profile manifest 加 bundle 后，`~/.dsh/state/dsh-superagent-restart.log` 没有 `[zcode-tool]` 行，也没有 reload 日志；我据此判断 HMR 未生效，开始规划重启。
- **真相**：HMR 实际已热加载；插件 `ctx.logger.info` 那次没有落到该日志。用 inspector 读 Cordis 根 Context 的 `tools.schemas()` 一眼看到 `zcode_run` 已在 126 个工具中。
- **能推翻"日志缺失=未加载"归因的证据**：同一插件注册表探测在日志仍无新行时返回 `found:true`（见 VERIFICATION ⑤）。
- **预防**：验证运行中宿主是否加载，直接查运行期注册表（inspector CDP 片段已写入插件 `AGENTS.md`），不以日志缺席作否定证据；只有注册表也查不到才考虑重启。

### 错误 2（轻度）：Node 24 上 `node --test test/` 把目录当模块
- **事实**：首跑报 `Cannot find module .../test`。
- **修正**：`node --test test/*.test.js`，并写进 package.json script。
- **可推翻归因的证据**：错误信息 `MODULE_NOT_FOUND` 指向 `test` 目录；改成 glob 后 20/20。

### 错误 3（轻度）：首次执行新写可执行脚本 ~5 s，误以为插件 spawn 有性能问题
- **事实**：fake ZCode `execute` 首测 4.5–5.9 s，第二次 0.3 s。
- **归因**：macOS 对新建可执行脚本的首次执行校验（同一脚本第二次 <0.5 s；`spawn` 事件本身 15 ms）。非插件逻辑问题。
- **可推翻归因的证据**：`spawn-timing` 实验 shebang 首次 5904 ms / 第二次 308 ms / node 直跑 476 ms；单测断言仍全部通过。

### 错误 4（流程）：改 live profile patch 只为触发 reconcile，之后又还原
- 为验证 HMR 是否响应 patch 文件，往 `superagent/cordis.patch.yml` 追加了一行注释，随后从备份还原（最终逐字节一致）。**无功能影响**，但属于不必要的 live 配置触碰；下次先直接查注册表，不靠制造文件事件来探测。

## 五、如果重来会怎么做

1. 先建临时 headless profile 把插件加载/执行/审批三件事跑通，再改 live profile；live 只做一次 manifest 变更。
2. live 生效验证从「看日志」改为「inspector 读 `tools.schemas()`」，HMR 生效后不重启。
3. 单测直接用 `node --test test/*.test.js`；fake 可执行脚本先热身一次再断言耗时。
4. 真实 ZCode 集成用最小 prompt（本次两次各 ~6.6 万 input tokens，已是合理下限）；`attach`/`resume` 若要做真实验证，另立项避免长尾。

## 六、仍未解决 / 后续建议

1. **线上 GUI 审批未点过**：需要在 GUI 里让 agent 调一次 `zcode_run` 并点「允许」，确认弹窗文案与批准后执行链路。建议作为首次使用时的人工验收。
2. **冷启动未验**：下次正常重启 superagent 后，用 inspector 探针确认 `zcode_run` 仍在；预期无问题（bundle 已进 profile，headless 冷启动已验同类加载）。
3. **模式/附件/续跑**：`plan/build/edit/yolo`、`attach`、`resume` 只到参数构造层；需要时逐项真实跑。
4. **超时真实长任务**：用 ZCode 跑一个明确超过 `timeout_ms` 的任务，确认进程组无残留（`pgrep -f zcode.cjs`）。
5. **ZCode 版本耦合**：升级 CLI 后先跑 `zcode --help` 与本插件 20 项单测 + 一次真实小任务。
6. **仓库快照同步**：`work/zcode-tool/` 是快照，后续改插件必须同时更新两处（插件目录为准）。

## 七、时间记录（仅时间戳，不据此推断投入/质量）

- 会话开工：2026-11-22 20:55（Asia/Shanghai，会话上下文时间）。
- 插件首次提交与安装：约 21:15；HMR 注册表确认：约 21:20；收尾约 21:30。
- 两次真实 ZCode 调用：60.5 s / 57.2 s（工具 `durationMs`），各消耗约 6.65 万 input tokens（ZCode 输出 usage）。
- 依据仅限会话时间戳与工具输出；未记录人工投入时长，也不由时间差推断效率或质量。
