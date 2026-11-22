# DEPLOY-NOTES — ZCode DSH 插件（zcode_run，工单 3b6d806d01ea）

日期：2026-11-22（Asia/Shanghai）
状态：**已落地并生效（HMR 热加载，未重启宿主）**。
源码唯一事实源：`~/.dsh/plugins/zcode-tool/`（git tag `v0.1.0`）；本仓 `work/zcode-tool/` 为快照。

## 1. 变更点（live `superagent` profile）

| 位置 | 变更 | 备份 |
|---|---|---|
| `~/.dsh/profiles/superagent/package.json` | dependencies 增 `"@local/zcode-tool": "link:/Users/huweixing/.dsh/plugins/zcode-tool"`；`dsh.profile.bundles` 末尾增 `"@local/zcode-tool"` | `package.json.bak-zcode-20261122-211525` |
| `~/.dsh/profiles/superagent/node_modules/@local/zcode-tool` | 软链 → 插件目录 | — |
| `~/.dsh/profiles/superagent/pnpm-lock.yaml` | 增 link importer 条目（specifier/version 与 package.json 一致） | `pnpm-lock.yaml.bak-zcode-*` |
| `~/.dsh/profiles/superagent/cordis.patch.yml` | 最终未改（调试时加过注释，已还原，与备份逐字节一致） | `cordis.patch.yml.bak-zcode-20261122-211802` |

插件自身的 `cordis.patch.yml` 插入 `zcode-tool` 行，config：`requireApproval:true`、`defaultTimeoutMs:600000`、`maxTimeoutMs:1800000`。

## 2. 生效方式

profile 启用了 `dsh-hmr`；manifest 的 bundles 列表变化触发 reconcile，新 bundle 被热加载。**宿主未重启**，所有现有 GUI 会话未中断。

运行期确认（不是看日志）：宿主 inspector `http://127.0.0.1:9230/json` → 连 CDP target → Host realm `Runtime.evaluate` → 读 Cordis 根 Context 的 `tools.schemas()`：

- 126 个工具中包含 `zcode_run`；
- schema：6 参数 `task/cwd/mode/timeout_ms/attach/resume`，required=`task`，`mode` 枚举 `guarded/plan/build/edit/yolo`，default `guarded`。

组合确认：

```bash
dsh --profile superagent --dump-config | grep -A5 zcode-tool
```

## 3. 验证摘要（详见 `work/zcode-tool/VERIFICATION-2026-11-22.md`）

- 单元测试 20/20；
- 真实 ZCode `guarded` 任务通过（60.5 s，66,536 tokens）；
- headless 宿主 E2E 通过（`tool/result isError=false`，57.2 s）；
- 审批默认 fail-closed 实测（`ApprovalError` / `APPROVAL_UNAVAILABLE`，ZCode 未启动）；
- 线上 profile HMR 注册表确认（见上）。

未验证：线上 GUI 实际点审批；superagent 冷重启；其他 mode/attach/resume 真实任务；真实长任务超时。

## 4. 回滚

```bash
cd ~/.dsh/profiles/superagent
# 1) 从 package.json 删除依赖与 bundles 中的 "@local/zcode-tool"（或用备份覆盖）
# 2) 删除软链
rm node_modules/@local/zcode-tool
# 3) HMR 会在 manifest 变化后 reconcile；若未生效则重启宿主
nohup ~/.dsh/bin/super-restart.sh superagent >/tmp/superagent-restart.log 2>&1 & disown
```

完整回滚可用备份：`cp package.json.bak-zcode-20261122-211525 package.json` 后同样触发 reconcile/重启。

## 5. 注意

- 插件源码目录不要删（profile 用 link 引用，删了下次启动会缺 bundle）。
- 改插件源码后 HMR `root: []` 不监听源码文件：需靠 profile manifest/patch 变化触发 reconcile，或重启宿主。
- 真实调用消耗 Z.ai coding 配额（实测小任务约 6.6 万 input tokens/次）。
- 判断运行中宿主是否加载，用 inspector 注册表探针，不要用「日志没有插件行」判断（LESSONS E210）。
