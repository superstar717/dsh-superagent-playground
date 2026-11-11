# SCOPE（工单范围声明）

- 做什么：把 superagent 工单工作区（playground worktree）纳入开工门禁——改 `~/.dsh/bin/gate_pretool.sh` v3（SCOPE.md 轻量语义）、e2e 真拦验证、PR 存档、最后重启 superagent。
- 不做什么：不动 hooks.json / docs_gate / 研究项目门禁语义；不改 executor.prepare；不给 ~/src 全目录纳管。
- 依据：用户 2026-11-11 对 work/方案-活跃目录纳管.md 三项参数回复「确认」（trigger e1cb339754d55bf073049841d1f10081）。
