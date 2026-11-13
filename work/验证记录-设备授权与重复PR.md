# 验证记录 — P1 设备授权安全锁 + P2 重复 PR 预检（工单 ae3297f806b9）

日期：2026-11-13 21:16–21:45（Asia/Shanghai）
方式：**真实宿主会话内验证 + 脚本级自测**。当前宿主 PID 44273（2026-11-13 02:00:23 启动）未重启；
`hooks.json` 未改动；P1 依赖的 `gate_pretool.sh` 由 hooks-claude-code 按次调用（改动即时生效）。

## 1. 真实会话 e2e（PreToolUse 门禁 / gh-agent 预检）

| # | 场景 | 预期 | 实测 |
|---|---|---|---|
| E-1 | `gh auth refresh -s workflow` | 拦 | ✅ 拦：「安全门禁：检测到直接执行 `gh auth login/refresh`…」，命令未执行 |
| E-2 | `bash -c "gh auth refresh -s workflow"` | 拦 | ✅ 拦（嵌套命令同样识别） |
| E-3 | `pkill -f "gh auth refresh"` | 拦 | ✅ 拦：「检测到 pkill/killall/kill 针对 gh / gh auth 进程…」 |
| E-4 | `pgrep -f "gh auth refresh" \| xargs kill` | 拦 | ✅ 拦（pgrep→kill 组合识别） |
| E-5 | `~/.dsh/bin/gh-auth-safe.sh verify -s workflow` | 放行且校验 | ✅ 放行；输出「授权校验通过：github.com scopes=gist, read:org, repo, workflow；要求包含： workflow」，rc=0 |
| E-6 | 临时 clone（分支改 `work/gate_pretool.v3.sh`，与 open PR #12 同文件）内 `gh pr create --help` | 放行 + 创建前警告 | ✅ 警告先于 gh 输出：`重复 PR 预检（警告，不拦截）：分支 test/overlap 与 1 个 open PR 存在同文件重叠：#12 门禁覆盖 v2 … → work/gate_pretool.v3.sh` |
| E-7 | `DSH_PR_OVERLAP_OK=1 gh pr create --help`（同仓库/分支） | 放行且无警告 | ✅ 无警告，gh 正常输出 |
| E-8 | 本工单真实 `gh pr create`（PR #22） | 只对代码/CI 类文件告警，不对每单必改簿记文件告警 | ⚠️→✅ 首次告警把 #12–#18 全部列为与 `work/SCOPE.md` 重叠（每单都改该文件），属系统噪声；已加簿记文件过滤（SCOPE/复盘/DEPLOY-NOTES/验证记录），selftest 增 `bookkeeping-only-silent`（7/7），过滤后同类 PR 不再误报 |

E-6/E-7 的临时仓库：`gh repo clone superstar717/dsh-superagent-playground /tmp/e2e-pr-repo -- --depth 30`，
分支 `test/overlap` 只新增 `work/gate_pretool.v3.sh`（与 PR #12 的既有文件同路径），未推送、未创建 PR。

## 2. P2 放置位置的事实依据（hook 子进程钥匙串不可用）

最初 P2 在 PreToolUse 内实现（写待提醒记录 → PostToolUse 注入）。真实 e2e 中 PreToolUse 报：

```
重复 PR 预检跳过：gh pr list 失败/超时（rc=1：HTTP 401: Requires authentication (https://api.github.com/graphql)）
```

在 hook 内做最小诊断（已全部移除，仅留记录）：

| 探测（hook 子进程内） | 结果 |
|---|---|
| `gh auth status` / `gh auth status --json hosts` | `state:error`，`tokenSource:"default"`，`HTTP 401: Bad credentials` |
| `/usr/local/bin/gh auth status --json hosts`（绕过 worker shim） | 同样 401 |
| `security list-keychains` | `A Module Directory Service error has occurred.`（仅 login.keychain-db） |
| `env` | `HOME=/Users/huweixing`，`SECURITYSESSIONID=186a5` 与 shell 相同，`GH_TOKEN/GITHUB_TOKEN` 未设置，uid=501 |

对照（Bash 工具命令内）：`gh auth status` 显示 `✓ … (keyring)`、scopes 含 workflow；
`security list-keychains` 正常列出 4 个钥匙串。结论：hook 子进程的 Security 会话不可用 → P2 改
`gh-agent`（与 gh 命令同环境）。此判断同时解释了 E132 现场 `gh auth status` 的间歇失败。

## 3. 脚本级自测

> 真实 e2e 还发现一个门禁误报：`pkill -f <无关模式>; pgrep -f gh-auth-safe_selftest` 被当成
> 「pgrep gh auth + kill」拦截（`gh-auth-safe` 命中了 `gh[-_]auth` 正则）。已把 pgrep 分支收窄为
> 只认 `gh` / `gh auth` / `gh.*auth`，并加 `allow-pgrep-own-selftest`、`allow-cleanup-combo` 两个用例。


| 套件 | 覆盖 | 结果 |
|---|---|---|
| `gate_pretool_selftest.sh` | 直接/嵌套/sudo 包裹的 `gh auth login/refresh` 拦截；`pkill`/`killall`/`kill $(pgrep …)`/`pgrep \| xargs kill` 拦截；非 gh 目标放行；`gh-auth-safe*` 自测/清理命令不被误判；非法 payload fail-closed；工单目录缺 SCOPE 拦截/有 SCOPE 放行 | **21/21** |
| `gh-pr-overlap-precheck_selftest.sh` | 有重叠警告（#12 + 文件）；无重叠静默；`DSH_PR_OVERLAP_OK=1` 静默；非 git 目录静默；gh 失败静默；仅簿记文件重叠静默；日志落盘 | **7/7** |
| `gh-auth-safe_selftest.sh` | scope 通过/缺少（rc=3）；两个 dry-run 并发串行（第 2 个等待、锁释放）；失效锁清理；等待在跑 gh auth 流（不杀）；status/doctor；日志 | **9/9** |

仓库副本同样通过（CI 路径）：`SELFTEST_BIN=$PWD/work/scripts bash work/scripts/…` → 21/21、7/7、9/9。
CI 工作流：`.github/workflows/gh-auth-pr-gate-selftest.yml`（ubuntu-latest，fake gh，无需真实凭证）。

## 4. 手工补充验证

- 串行锁：两个 `GH_AUTH_DRY_RUN=1 GH_AUTH_DRY_HOLD=3` 并发，第二个日志出现
  「另一个设备授权流程正在进行…串行等待…（不杀进程）」，总耗时 36s（含真实 keyring 校验）
  ——并发确实串行，锁最终释放。
- 失效锁：`mkdir gh-auth.lock; echo 999999 > pid` 后 dry-run → 「清理失效锁」后成功。
- 等待在跑流程：`/tmp/slowflow.*/gh auth refresh`（sleep 2）在跑时启动 wrapper → 等待约 2s 后继续，
  未杀进程。
- `gh-auth-safe.sh doctor`：显示锁状态、在跑流程、本机 scopes、GitHub 侧头、最近日志。

## 5. 核查结论

- P1 「该拦时真拦」：4 类危险命令真实被拒绝；放行路径真实可用且自动验 scopes。
- P2 「警告式不硬拒」：真实 `gh pr create` 前出现警告；显式豁免生效；预检失败不阻断。
- 免重启：`hooks.json` mtime 11:55:55 早于本次改动，宿主 PID 44273 启动于 02:00:23；规则仅靠
  `gate_pretool.sh`/`gh-agent` 现读即生效，无需重启（已用真实会话验证）。
- 未重启宿主带来的已知缺口：`orchestrator_report` 证据门禁（11:55 加入 hooks.json）仍未加载，
  需另做重启 + e2e，本工单不动。
