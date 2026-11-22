# AGENTS — zcode-tool（项目现状）

## 这是什么

`@local/zcode-tool`：把 ZCode CLI 注册为 DSH 工具 `zcode_run` 的本地插件。唯一事实源是本目录（git 管理，tag `v0.1.0`），部署方式是 link 进 DSH profile。

- 工具名：`zcode_run`；入口：`index.js` 的 `apply(ctx, config)`
- 宿主契约：DSH `0.2.2-rc.3`，裸 `ctx.tools.register()` + 原生 JSON Schema（见 LESSONS E39 的写法约定）
- ZCode 契约：本机 `zcode` 0.17.1（源码构建），`--prompt/--mode/--output-format json/--attach/--resume`
- 当前部署：`~/.dsh/profiles/superagent`，bundle 列表末尾；已通过 HMR 热加载（2026-11-22）

## 项目现状（2026-11-22 收尾）

- 代码完成，单元测试 20/20；真实 ZCode 小任务、headless 宿主 E2E、审批 fail-closed（`APPROVAL_UNAVAILABLE`）、线上 HMR 注册、线上 GUI「ask→allowed-once→真实执行」（⑥）、会话策略 `never` 自动拒绝（`APPROVAL_REJECTED`，ZCode 未启动，⑦）均已验证，证据见 `VERIFICATION-2026-11-22.md`。
- 线上配置：插件默认 `requireApproval: true`，但 **superagent 线上已由 profile patch 关掉逐次审批**（`requireApproval: false`，2026-11-22 22:11 生效，见 VERIFICATION ⑧，备份 `cordis.patch.yml.bak-zcode-approvaloff-20261122-221030`）——该 profile 内 `zcode_run` 不再人工确认；会话策略 `never` 只影响仍要求审批的工具。默认 `guarded`、默认超时 10 分钟、上限 30 分钟。
- 我（Agent）在验证冷启动时的教训：**不要用 `launchctl submit` 承载任何非幂等动作（尤其重启/杀宿主）**——submit 作业是**无条件保活**（2026-11-22 23:41 实测：`exit 0` 的脚本 46 s 内被重拉 5 次；`launchctl print` 显示 `properties = keepalive`），本次因此 45.7 分钟重启宿主 32 次。再验冷启动一律前台跑，见 VERIFICATION ⑨ 与 LESSONS E212。
- 未验证：审批「人工点击 vs 自动应答器」不可区分；`plan/build/edit/yolo` 等模式真实任务；`attach/resume` 真实调用；真实长任务超时。改动后按 `VERIFICATION-2026-11-22.md` 的层级补测。（**冷启动已由 ⑨ 关闭**）

## 硬约束（改代码前先看）

1. **永远显式传 `--mode`**：`zcode --prompt` 默认 `yolo`，缺省会放开权限提示；默认必须 `guarded`。
2. **超时/取消杀进程组**：POSIX 用 `detached:true` + `process.kill(-pid)`，SIGTERM→5s→SIGKILL→3s 硬结算；不要只杀父进程。
3. **审批走 `tools/pre-execute` 的 `{kind:'ask'}`**：不要用 `ctx.tools.guard()` 当审批（guard 只能 deny）；默认 `requireApproval:true`，headless 才显式关闭。
4. **裸 register 的 schema 是标准 JSON Schema**：`required` 是数组、`additionalProperties` 显式布尔、`oneOf` 最多做 exact-one；参数校验自己写在 `normalizeToolArguments`，因为裸注册不做入参校验。
5. **不 import `@deepseek-ai/dsh-*`**：本插件只用 Node 内置模块，避免 link 包的 peer 解析问题（与 stat-research-gate 同策略）。
6. **输出有界**：单流采集 2,000,000 字符、模型可见 200,000 字符；`ok` 只表示进程退出码 0，不表示任务成功。

## 修改 / 重新部署

```bash
cd ~/.dsh/plugins/zcode-tool
npm test                       # 20 项；改参数/进程逻辑必须跑
git add -A && git commit ...   # 本目录是唯一事实源；改了必须提交
# 线上 profile 用 link，无需拷贝；HMR 会因 profile manifest/patch 变化热加载。
# 仅当 HMR 未生效或要冷启动验证时：
nohup ~/.dsh/bin/super-restart.sh superagent >/tmp/superapp-restart.log 2>&1 & disown
```

`superagent` 的安装点：

- `~/.dsh/profiles/superagent/package.json`：dependency + bundles 列表
- `~/.dsh/profiles/superagent/node_modules/@local/zcode-tool` → 本目录软链
- 插件自己的 `cordis.patch.yml` 带默认 config；profile 的 `cordis.patch.yml` 可按 id 覆盖

回滚：从 `dsh.profile.bundles` 与 dependencies 删除 `@local/zcode-tool`，删除软链；HMR/重启后工具消失。profile 备份见 `package.json.bak-zcode-20261122-211525`。

## 验证运行中宿主是否加载（不重启）

用宿主 inspector（当前 9230）在 Host realm 读 Cordis 根 Context：

```js
const table = globalThis[Symbol.for('dsh.inspector.realm-object-registries')]
let root; for (const registry of table.values()) root = registry.retained.get('object-1')
root.get('tools').schemas().map(s => s.name)   // 应包含 'zcode_run'
```

别用「host 日志里没有插件日志行」判断未加载（实测 HMR 已加载但 `ctx.logger.info` 未落盘）。

零成本一键验证：`node scripts/verify-live.mjs`（本地契约 + 线上注册）；加 `--real` 再跑一次真实 ZCode（耗配额）。退出码 0/1。
