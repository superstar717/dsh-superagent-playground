# DSH 0.2.2 升级执行清单（本机 superagent）

目标：`0.2.1-rc.5` → `0.2.2-rc.3`；宿主重启约 10–20 秒，所有会话会断开（superagent 恢复中断工单）。

## 已完成的准备（本次）

- 备份：`~/.dsh/backup/dsh-0.2.2-<timestamp>/`（profile package/cordis、hooks.json、orchestrator.sqlite、superagent lib）
- `dsh-superagent` 兼容补丁：`agent/request` 监听在检测到 0.2.2 的 `agent.model` 时不再改路由（0.2.1 行为保持）
- profile：
  - `cordis.patch.yml` 增加 `fs-observation-policy: disabled: false`（保留先读后写防护）
  - `package.json` 的 bundles 移除 `@deepseek-ai/dsh-experimental-tool-worktree`（已并入新工作树入口）
- 隔离预演：临时 CLI `0.2.2-rc.3` + 临时 `DSH_HOME` 启动本 profile（Feishu/GitHub 源禁用，端口 3199），确认插件加载
- 未在本次执行：`~/deepseek-harness` checkout 升到 `dsh-v0.2.2-rc.3` 并重建 3 个 link 包。旧 link 包（0.2.1-rc.5）在 0.2.2 下经预演可用；后续单独更新（更新后需再重启一次生效）。

## 切换

```bash
# 在终端（不要在 DSH 会话里）执行；setsid 让脚本脱离宿主进程组，先停宿主再装包
cd /Users/huweixing/src/dsh-upgrade-review-c1b51ce39d17
python3 -c 'import os; os.setsid(); os.execvp("bash", ["bash", "work/upgrade/switch.sh", "0.2.2-rc.3", "0.2.1-rc.5"])' \
  > ~/.dsh/state/switch-launch.log 2>&1 &
# 若 setsid 失败，退回：nohup bash work/upgrade/switch.sh 0.2.2-rc.3 0.2.1-rc.5 &
```

脚本行为：

1. 等 20 秒（让 orchestrator 收到「待重启」报告）。
2. 停 3082 宿主；`npm i -g @deepseek-ai/dsh@0.2.2-rc.3`。
3. 启动 `dsh --profile superagent --no-open --port 3082`，最多等 180 秒。
4. 健康检查通过 → `~/.dsh/state/upgrade-status.json` 写 `ok`，跑 `post-restart-check.sh`。
5. 失败 → 自动装回 `0.2.1-rc.5`、重启，状态写 `rolled_back`（再失败写 `failed`）。

日志：

- `~/.dsh/state/upgrade-0.2.2.log`（切换过程）
- `~/.dsh/state/dsh-superagent-current.log`（新宿主启动日志）
- `~/.dsh/state/post-restart-check.txt`（自动检查输出）

## 重启后人工/工单检查

1. `bash work/upgrade/post-restart-check.sh`（在宿主会话内跑，可同时验证 hooks 桥接：先跑一次 bash 命令再看 `/tmp/hook_payload/last.json` 时间）。
2. Web 打开 `http://127.0.0.1:3082`（同端口 cookie 30 天，刷新即可；`~/.dsh/bin/dsh-web-open` 可打印/打开链接）。
3. Feishu @机器人 发一条测试消息，确认收发。
4. Hooks：尝试一个应被拦截的命令（`gh auth login`，`gate_pretool` 会拒绝），确认被拒；写一个受管文件确认 `docs_gate` 行为。
5. 打开一个旧会话 + 新建会话，确认历史恢复和模型路由（orchestrator/router/worker）。
6. UI 冒烟：侧栏、工单面板、设置页、插件页、kanban、媒体台、memory-evolve 页面。
7. 低风险工单：问一个只读问题，确认派单/回收。

## 回滚

```bash
PID=$(lsof -tiTCP:3082 -sTCP:LISTEN | head -1); [ -n "$PID" ] && kill "$PID"
npm i -g @deepseek-ai/dsh@0.2.1-rc.5
nohup dsh --profile superagent --no-open --port 3082 > ~/.dsh/state/dsh-superagent-current.log 2>&1 &
```

插件补丁向后兼容（无 `agent.model` 时走旧逻辑），profile 配置改动对 0.2.1 无害。升级期间新建的会话/工单数据可能无法被 0.2.1 读取（存储只承诺新读旧）。

## 已知限制

- 未在真实 0.2.2 上跑过工单全链路（预演禁用了 Feishu/GitHub 源）；重启后按上面第 1–7 项验收。
- 3 个 link 包仍是 0.2.1-rc.5 构建；预演通过，但建议后续按 `~/deepseek-harness` tag `dsh-v0.2.2-rc.3` 重建。
- 13 个第三方插件与 7 个本地插件的客户端 UI 未逐个源码审计，靠重启后冒烟。
