# 安装 OpenDesign（opendesignHQ）插件 — 2026-11-23

工单：`b82f339510ebabf3682ff960f5076e69`（飞书：「安装插件opendesignHQ」）
验收标准（开工即定）：交付物 = OpenDesign 接入插件装进 superagent profile 且运行中宿主真实加载 provider；验证方式 = 运行宿主注册表探针 + web client bundle 证据；边界 = OpenDesign 账号登录与真实模型推理不在本工单内（账号是用户资产）。

## 结论

- **已装**：`dsh-opendesign-corouter@0.3.5`（npm，MIT）装入 `~/.dsh/profiles/superagent`，bundle 已注册，宿主已重启加载。
- **已实测验证**（非声称）：
  1. 运行宿主（launchd 托管，重启后 pid 58210）的 llm 注册表里出现两个 provider：`opendesign-corouter-plan`（OpenDesign CoRouter · 套餐赠送）与 `opendesign-corouter-paid`（OpenDesign CoRouter · 付费模型），`settingsNs=llm-opendesign-corouter`，`defaultBaseURL=https://amr-link.open-design.ai/v1`，`nativeAuth.oauth=true`（设备授权）。探针：`work/verify-corouter-live.mjs`（零副作用，CDP 直读 `listProviders()`/`listConfigurableProviders()`，exit 0，输出 PASS）。
  2. Web 客户端注入生效：宿主下发的 client bundle 列表含 `dsh-opendesign-corouter/client.js`（带 token 抓取首页 HTML 可见）。
  3. 安装时 pnpm 供应链检查通过（lockfile 642 条目政策校验）。
- **未验证（如实声明）**：
  - 真实模型调用未跑——需要 OpenDesign 账号授权（设备授权或工作空间 API Key）。本机此前无 OpenDesign 痕迹（无 `~/.amr/`、无桌面应用、无 `vela` CLI），账号属用户资产，本工单不能也不应代登录。
  - 插件作者在 README 自述「真实推理和已安装 Profile 的完整联调仍待验证」，即 0.3.5 的真实推理链路在上游也标注为待验证。
  - 模型选择器里的模型列表为空属预期：登录后由插件从官方网关拉目录（首次使用及十分钟后按需刷新）。

## 用户词「opendesignHQ」的核实（官方来源）

- GitHub org **OpenDesignHQ** 存在（2026-11-16 创建），0 个公开仓库；OpenDesign 产品本体在 `nexu-io/open-design`（Apache-2.0，约 109k stars，官网 open-design.ai，© Powerformer, Inc.）。"opendesignHQ" 是官方组织名，不是某个包名。
- **不存在**叫 `opendesignhq` 的 npm 包（`npm view opendesignhq` 404；registry 搜索、`@opendesignhq` scope、`dsh-opendesignhq` 等变体均无）。
- OpenDesign 官方的对外接线产品是 **CoRouter**（corouter.open-design.ai，"Unified AI Hub"）：API Key + 端点接入其他 Agent，官方 Supported agents 列表明确含 **DeepSeek Harness**。
- 官方三步法：① 控制台建 API Key → ② 经 CC Switch / Magpie 接入 → ③ 在 Agent 里用。官方没有第一方 DSH 插件包；DSH 侧的接入由社区插件承载（官方插件目录 `dsh-plugin-catalog`（12763 条）与 `awesome-dsh-plugin` 注册表中 OpenDesign 相关 8 个，无 "opendesignHQ"）。

## 选型：为什么是 dsh-opendesign-corouter

| 候选 | 结论 | 理由 |
| --- | --- | --- |
| `dsh-opendesign-corouter` 0.3.5（KouzakiUmi） | **选定** | 2026-11-22 仍在发版；自带设备授权登录（不依赖 OpenDesign 桌面应用，本机没有）；双 provider（套餐赠送/付费模型）+ 四层额度；peer 声明范围覆盖本机 dsh 0.2.2-rc.3；npm OIDC trusted publishing；包内无 install/postinstall 脚本；运行时只连官方端点（open-design.ai / amr-api / corouter / amr-link，lib 内 grep 佐证）；有 SECURITY.md、测试与 CI |
| `dsh-opendesign-go` 0.1.24（EliteOtaku） | 备选，未装 | 额度读本机 OpenDesign 客户端（本机未装该应用），模型面较窄 |
| 额度显示类（runway/limit/od-quota/quota-card/balance-meter 等） | 不选 | 只解决「看额度」，不解决「用模型」；依赖已有 provider 或桌面端 |
| `dsh-opendesigner` / `dsh-open-design-preset` | 不选 | 前者是本地可视化设计器（同名不同物）；后者是把 DSH 变设计工作室的预设，依赖本地 OpenDesign 应用 MCP，本机没有 |

## 安装过程（可复现）

```console
# 1. 安装（pnpm 转发，自动写入 dependencies + dsh.profile.bundles）
dsh plugin --profile superagent add dsh-opendesign-corouter
# ✓ Lockfile passes supply-chain policies (642 entries)
# dependencies: + dsh-opendesign-corouter 0.3.5；bundles 末尾自动加入 "dsh-opendesign-corouter"

# 2. 重启宿主加载插件（launchd 托管的既定入口）
nohup ~/.dsh/bin/super-restart.sh superagent > ~/.dsh/state/restart-corouter-20261123.log 2>&1 & disown
# 自检通过：新进程 pid=58210 监听 3082（旧 pid 16948）

# 3. 运行宿主验证（本仓库）
node work/verify-corouter-live.mjs
# PASS: plan=true paid=true
```

peer 依赖警告属既有常态（本 profile 多个已工作插件同类提示，如 cordis ~4.0.5 vs 已装版本），不阻塞加载——探针实测 provider 已注册为证。

## 用户侧只剩一步（要用模型时）

设置 → **OpenDesign CoRouter → 连接与登录** → **开始设备授权**（临时 Chrome 打开官方授权页确认；也可复制链接到常用浏览器，或在设置页直接粘工作空间 API Key / 设 `COROUTER_API_KEY`）。登录后回到模型选择器选「OpenDesign CoRouter · 套餐赠送」或「· 付费模型」。

## 回滚

```console
dsh plugin --profile superagent remove dsh-opendesign-corouter
# 再重启宿主即可（super-restart.sh superagent）
```
