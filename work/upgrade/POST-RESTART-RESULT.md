# DSH 0.2.2 升级结果（重启后自检）

- 时间：2026-11-14 09:36 CST
- 切换：`0.2.1-rc.5` → `0.2.2-rc.3`，`~/.dsh/state/upgrade-status.json` = `ok`，HTTP 401（未鉴权即健康）
- 新宿主：pid 32197，启动于 09:35:55；旧宿主已退出
- 回滚：未触发

## 通过项

| 检查 | 结果 |
|---|---|
| 版本 | `dsh --version` = 0.2.2-rc.3 |
| Web | `curl :3082/` = 401（服务正常，需鉴权） |
| 组合 | `dsh --profile superagent --dump-config` 通过；无 denied / skippedBundles |
| 配置 | `fs-observation-policy` disabled:false（先读后写保留）；worktree bundle 已从 29 个 bundles 移除 |
| 插件 | memory-evolve / agentero / kanban / inspector / LLM provider 等启动；无插件加载拒绝 |
| Hooks | PreToolUse 桥接触发（/tmp/hook_payload/last.json 更新）；直接 `pkill -f 'gh auth login'` 被 `gate_pretool` 拒绝（exit 2）；`gate_pretool_selftest` 21/21 |
| 状态 | orchestrator.sqlite quick_check=ok；39 tickets；79 sessions |
| 模型 | 本 worker 最近 request/header = deepseek-official/deepseek-flash/max |
| 自愈 | 重启后本工单按恢复说明重新开始（可正常执行 bash/工具） |

## 备注

- `dsh-kanban` 启动时对每个历史 workspace 打印 “check failed cannot read …/.dsh-kanban.json”，是第三方插件对无看板文件的逐目录检查噪音，非升级失败；看板页面需人工点开确认。
- Feishu 收发与 UI 页面未由脚本端到端验证；本工单若能在 Feishu 收到完成消息，即证明出站正常，入站可再发一条测试消息确认。
- `~/deepseek-harness` 与 3 个 link 包仍为 `0.2.1-rc.5` 构建（预演与实跑均可用，hooks 已实证）；按报告计划，后续单独 checkout 到 `dsh-v0.2.2-rc.3` 重建，需再重启一次生效。
- `dsh-superagent` 兼容补丁见 `dsh-superagent-0.2.2.patch`（本地 commit bbab471：0.2.2 固定路由时不再改 `agent/request`）。
