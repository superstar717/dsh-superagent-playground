# DEPLOY-NOTES — P1 设备授权安全锁 + P2 重复 PR 预检（工单 ae3297f806b9）

日期：2026-11-13（Asia/Shanghai）
结论：**已在一台正在运行的 superagent 宿主上落地并完成「该拦时真拦」e2e**；未重启宿主、未改
`~/.dsh/hooks.json`。P1 全部规则在已加载的 `gate_pretool.sh`（PreToolUse(Bash)，脚本每次调用现读）
里生效；P2 因 hook 子进程拿不到登录钥匙串，改在 `gh` 入口 `~/.local/bin/gh-agent`（同一命令环境）
实现，警告随命令 stderr 在 PR 创建前可见。三条自测共 33 项通过，CI 工作流已随 PR 提供。

---

## 1. 来源与范围

2026-11-13 复盘把 4 条经验分为「值得机制化 / 不建议硬门禁」，其中：

- **P1 = LESSONS E132**（设备授权并发 / 被 `pkill` 误杀）→ 值得机制化；
- **P2 = LESSONS E133**（同一线程多工单重复提 PR）→ 部分机制化，**警告式、不硬拒**；
- E85（ready 前复盘归位）不做硬门禁；E123（CDP pages/探测）维持规则。

路由注记要求：**P1 免重启生效、P2 警告式不硬拒**。本工单按此执行；未把 11:55 新增但当前宿主
（PID 44273，02:00:23 启动）未加载的 `orchestrator_report` 证据门禁算进本工单防线。

## 2. 关键发现：hook 子进程读不到登录钥匙串（决定 P2 放在哪里）

最初按「P1/P2 都并入 gate_pretool.sh」实现：PreToolUse 里查 open PR 同文件重叠，写待提醒记录，
再由 PostToolUse（`lessons_intercept.sh`）注入模型可见警告。脚本级自测全过，但真实会话 e2e 暴露：

```
hook 内 gh pr list → rc=1
gh auth status --json hosts → {"state":"error","error":"HTTP 401: Bad credentials","tokenSource":"default"}
security list-keychains → "A Module Directory Service error has occurred."（只剩 login.keychain-db）
```

对比：同一台机器上，Bash 工具命令里的 `gh` 正常（`(keyring)`，scopes 含 workflow），`security
list-keychains` 列出 4 个钥匙串。结论：**hook 子进程的 Security 会话不可用**，gh 回落到无 token
（401）。为避免把 token 落到明文（`--insecure-storage`）或引入更强的耦合，P2 改为在 `gh` 入口
`~/.local/bin/gh-agent` 实现——它与真正的 `gh pr create` 同一进程环境，钥匙串可用；警告写到命令
stderr，**在 PR 创建之前**就进入工具输出，比「创建后再提醒」更符合 E133 的意图。

> 这一发现也解释了 E132 的现场：`gh auth status` 在这台机器上会间歇性报 keyring timeout/invalid
> （21:22 实测出现过一次，重试即恢复）。`gh-auth-safe.sh` 的校验因此带 3 次重试 + API 兜底。

## 3. 变更清单

| 位置（本机） | 本仓副本 | 作用 |
| --- | --- | --- |
| `~/.dsh/bin/gh-auth-safe.sh` | `work/scripts/gh-auth-safe.sh` | **P1 单点入口**：mkdir 串行锁、等待在跑流程自然结束（不杀）、授权后验本机 scopes + GitHub 侧 `X-OAuth-Scopes`；`--dry-run` 用于自测 |
| `~/.dsh/bin/gate_pretool.sh`（v3→v4） | `work/scripts/gate_pretool.sh` | **P1 强制层**（已加载 hook，现读生效）：拒绝直接 `gh auth login/refresh`（含 `sudo`/`bash -c` 包裹）、拒绝 `pkill/killall/kill` 针对 gh / gh auth（含 `pgrep … | xargs kill`）；原研究项目/工单 SCOPE 门禁语义不变 |
| `~/.dsh/bin/gh-pr-overlap-precheck.sh` | `work/scripts/gh-pr-overlap-precheck.sh` | **P2 预检**：`git diff origin/main...HEAD` ∩ open PR 的 `files`，命中打印警告；失败/超时静默并记日志 |
| `~/.local/bin/gh-agent`（2 行→带预检） | `work/scripts/gh-agent` | **P2 挂载点**：检测到 `gh pr create` 时先跑预检；`DSH_PR_OVERLAP_OK=1` 显式豁免 |
| `~/.dsh/bin/gh-auth-safe_selftest.sh` | 同名 | P1 wrapper 自测（fake gh，9 项） |
| `~/.dsh/bin/gate_pretool_selftest.sh` | 同名 | P1 门禁自测（18 项） |
| `~/.dsh/bin/gh-pr-overlap-precheck_selftest.sh` | 同名 | P2 预检自测（6 项） |
| — | `.github/workflows/gh-auth-pr-gate-selftest.yml` | CI 跑上述 3 个自测（`SELFTEST_BIN=work/scripts`，无需真实凭证） |

备份：`~/.dsh/bin/gate_pretool.sh.bak-v3`、`~/.local/bin/gh-agent.bak-20261113`。

未改：DSH 宿主代码、`hooks.json`、图谱问答/其他门禁判定、`blocked_report_gate.sh`。

## 4. P1 设计要点

- **串行锁**：`~/.dsh/state/gh-auth.lock`（`mkdir` 原子）。后来者等待（默认 900s，
  `GH_AUTH_LOCK_TIMEOUT`），超时明确失败；只在持有 pid 已退出/元数据缺失超过 5s 时清理失效锁。
- **不杀进程**：启动前 `pgrep -fl 'gh auth (login|refresh)'`，有在跑流程就等其自然结束
  （默认 300s，`GH_AUTH_PROC_WAIT`），超时也**不杀**；门禁同时拒绝任何针对 gh auth 的 pkill/kill。
- **授权后校验**：先 `gh auth status --json hosts`（3 次重试，避免 keyring 瞬时失败）核对本机
  active 账号 scopes；再读 GitHub 侧 `X-OAuth-Scopes` 头核对，二者缺一即 rc=3，并明确提示
  「不要杀进程，重新完整走一次授权」。`--json` 读不到时用 `gh api user` 兜底（API 可用 + GitHub
  侧 scopes 满足即通过，避免误杀正常会话）。
- **用法**：`gh-auth-safe.sh refresh -s workflow` / `login [gh auth login 参数]` / `verify` /
  `status` / `doctor`；日志 `~/.dsh/state/gh-auth-safe.log`（1MB 轮转）。

## 5. P2 设计要点

- `gh-agent` 只在参数出现 `pr create`（子命令序列）且 `DSH_PR_OVERLAP_OK≠1` 时调用预检；
  其余 gh 命令零开销。
- 预检：本地仓库 → `origin/main|master|HEAD` 为 base → `git diff --name-only base...HEAD`；
  每单必改的簿记文件（`work/SCOPE.md`、`work/项目复盘.md`、`work/DEPLOY-NOTES.md`、`work/验证记录-*.md`）
  不作为重叠证据，避免每个工单 PR 都因这些共享路径互报（E133 同类误伤）；
  `gh pr list --state open --limit 50 --json number,title,headRefName,files`；同名分支跳过；
  交集非空即输出警告（最多 5 个 PR、每个 8 个文件），并写
  `~/.dsh/state/gh-pr-overlap.log`。**任何失败/超时都静默 exit 0**，绝不阻断 PR 创建。
- 警告文案含 E133 处置建议（若是重复提交，关闭自己那份并注明以哪份为准）与豁免方式。
- 不改 gh 退出码、不改 PR 内容。

## 6. 验证（摘要；完整记录见 [work/验证记录-设备授权与重复PR.md](验证记录-设备授权与重复PR.md)）

1. **该拦时真拦（真实宿主会话）**：`gh auth refresh -s workflow`、`bash -c "gh auth refresh …"`、
   `pkill -f "gh auth refresh"`、`pgrep -f "gh auth refresh" | xargs kill` 均被 PreToolUse 拒绝，
   命令未执行。
2. **放行与校验**：`~/.dsh/bin/gh-auth-safe.sh verify -s workflow` 真实跑通（本机 scopes 含
   workflow，GitHub 侧头一致）；缺少 scope 时 rc=3 并给出正确指引。
3. **P2 真实链路**：在含重叠文件的临时 clone（分支改动 `work/gate_pretool.v3.sh`，与 open PR #12
   同文件）执行 `gh pr create --help`，命令输出**先**出现警告（#12 / 文件），`DSH_PR_OVERLAP_OK=1`
   时不出现。
4. **脚本级**：gate 18/18、precheck 7/7、wrapper 9/9（并发串行、失效锁、等待在跑流程、scope
   通过/缺少、簿记文件过滤、日志）；用 `SELFTEST_BIN=work/scripts` 跑仓库副本同样通过（CI 路径）。

## 7. 回滚

```bash
cp ~/.dsh/bin/gate_pretool.sh.bak-v3 ~/.dsh/bin/gate_pretool.sh   # 只想退 P1 强制层
cp ~/.local/bin/gh-agent.bak-20261113 ~/.local/bin/gh-agent        # 退 P2
rm -f ~/.dsh/bin/gh-auth-safe.sh ~/.dsh/bin/gh-pr-overlap-precheck.sh   # 退 P1 入口
# 自测/日志文件可留：~/.dsh/bin/*_selftest.sh、~/.dsh/state/{gh-auth-safe.log,gh-pr-overlap.log}
```
回滚后 `gh auth refresh` 恢复直连（有并发/误杀风险）；P2 恢复为无预检。宿主无需重启
（hook 脚本现读、gh-agent 每次调用现读）。

## 8. 边界与未解决

- `orchestrator_report` 证据门禁仍**未加载**（hooks.json 11:55 改、宿主 02:00 启动；E127 同类）；
  需重启 + 「该拦时真拦」e2e 才算防线。本工单未重启，避免中断在跑的会话。
- `gh-agent` 是 dsh-superagent 的 agent gh 入口；直接调用真实 gh 二进制（`/usr/local/bin/gh`）
  或非 agent 环境不经过 P2 预检。P2 只覆盖 agent 的常规 `gh pr create`。
- P2 预检对 `gh pr create --help`、`--dry-run` 也会跑（无副作用，最多多 ~2s）。
- 本机 keychain 在并发 gh 进程下会间歇失败（E132 现场同源）。wrapper 已重试 + API 兜底；
  P2 预检失败则静默跳过，不会阻断创建。
- `.github/workflows/` 需要 `workflow` scope；当前 token 已含（2026-11-13 20:32 用户授权）。
