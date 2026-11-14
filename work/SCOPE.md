# SCOPE — P1 设备授权安全锁 + P2 重复 PR 预检（工单 ae3297f806b9）

来源：2026-11-13 飞书复盘建议，按 LESSONS E132 / E133 落地机制；路由注记要求 P1 免重启生效、P2 警告式不硬拒。

## 本工单做什么

1. **P1（E132）设备授权并发 / 误杀**：新增 `~/.dsh/bin/gh-auth-safe.sh` 作为 gh 设备授权单点入口——
   串行锁（同一时刻只允许一个流程，等待而不是杀进程）、禁止 `pkill/kill` 针对 `gh auth` 进程、
   完成后自动验 `gh auth status` scopes（并核对 GitHub 侧 token scopes）；把「禁杀进程 + 直接
   `gh auth login/refresh` 必须走 wrapper」并入已加载的 `~/.dsh/bin/gate_pretool.sh`（Bash PreToolUse，
   脚本每调用现读，改后即生效，不重启宿主）。
2. **P2（E133）重复 PR**：`gh pr create` 前预检 open PR 同文件重叠（PreToolUse 内完成检查），
   重叠时经已加载的 PostToolUse hook 注入**警告**（不硬拒）；支持命令前缀 `DSH_PR_OVERLAP_OK=1`
   显式豁免。
3. 交付：本机生效 + 脚本级自测 + 真实会话 e2e（该拦时真拦、警告真出现）+ 本仓 `work/` 存档与 PR。

## 不做什么

- 不重启宿主、不改 `~/.dsh/hooks.json`（因此 11:55 新增但当前宿主未加载的 `orchestrator_report`
  证据门禁仍不在本工单生效范围；如需生效另做重启 + e2e）。
- 不改 DSH 宿主源码、不改图谱问答/其他既有门禁的判定语义（`gate_pretool.sh` 原研究项目/工单
  SCOPE 拦截逻辑保持不变）。
- 不硬拒重复 PR（README、AGENTS 等共享文件易误伤），不代用户完成设备授权确认。
