# 调研报告：.motion 模板项目与「AI 助手换内容渲染」流程

> 工单 motion-templates-check-dae1dc5485f1 · 触发：2026-11-20 飞书群消息（用户转述教程说法，要求调研）
> 路由注记：与本机已装的 motiongit-385712 对照，以仓库实况为准。
> 评价框架声明：本文同时给两层——①映射（源消息说法 ↔ 官方口径逐条对应）；②审计（与本机已有链路找差距）。既有口径来源：11-14 复盘、`~/.dsh/AGENTS.md` §十六、LESSONS E142。

## 一、一句话结论

源消息所述**基本属实**：`.motion`（MotionGit）确已开源在 GitHub，官方流程就是「下载 .motion → 交给支持工作模式的 AI 助手 → 换内容并渲染成片」，豆包/WorkBuddy/Kimi Code 都在官方支持名单；但有两个关键修正——①**渲染发生在本地**（Node 22+ 无头浏览器逐帧渲染，不是聊天里云出片，纯聊天助手做不了）；②**免注册能直下的模板仍只有 #385712 横屏公开包**，其余要走 motiongit.com 注册下载。本机 `~/.local/motiongit-385712/` + `make_video.sh` 已经是同一流程的工程化落地（且包与 GitHub 当前公开版 sha256 位位一致），**不需要为这套流程另搭环境**。

## 二、仓库实况（2026-11-20 核查）

- **合集仓 `motiontemplates/all`**：1150★ / 115 fork，描述「MotionGit 模板合集 · 技术资料、素材要求、GitHub 地址与完整 Demo 视频」，main 分支 2026-11-20 仍有推送。这就是「搜 motion templates 能找到」的仓库。
- **规模**：CATALOG.md 共 157 个条目（横竖屏分开计），README 自称「155 个模板 · 1 个测试项目 · 157 个 Demo」。**11-14 时点口径是 100 个模板**，现已扩充。
- **下载口径**：
  - GitHub 免注册直下：**仍只有 #385712 横屏** `kinetic-tech-zh.motion`（v0.2.7-open-beta，17,596,250 字节，sha256 `472a95af…`，与 template.json 声明一致）。全目录仅此 1 个直下链接。
  - 官网 motiongit.com：约 46 个下载入口（唯一 URL 计数；同一模板横竖屏可能共用），按账号提供接口、防批量滥用，需注册/登录。
  - 其余条目属第二批「打磨优化中，即将开放下载」，当前只有 Demo 可看。
- **单模板仓 `motiontemplates/385712`**：MIT license；`template.json` 标 `coverageComplete:false`、`apiEnabled:false`、testedSystem macOS；仓库自带 `AGENTS.md`、`llms.txt`、`FORMAT.md` 等 AI 助手入口文件；`downloads/` 保留 0.2.4–0.2.7 历史版本与 `SHA256SUMS`。
- **竖屏**：#385712 中文竖屏只有官网版 v0.2.44-alpha.6；GitHub 公开包仍仅 16:9。
- **官网相对 11-14 的新能力**：素材接口（背景音乐/贴纸/图片/视频，免费 BGM 与素材检索）、Creator API、支持 .motion 的第三方客户端 beta（ADu Director）、`.motion` 开放格式规范 1.0.0-rc.1（candidate）。

## 三、源消息说法逐条核实

| 源消息说法 | 核实结果 | 依据 |
|---|---|---|
| 「项目叫 .motion，GitHub 开源，搜 motion templates 能找到」 | ✅ 属实 | motiontemplates/all（1150★）+ 官方 Demo 站 motiontemplates.github.io/all |
| 「下载模板」 | ✅ 但受限：免注册直下仅 #385712 横屏 | CATALOG.md 全文仅 1 个直下链接；46 个官网入口需注册 |
| 「素材、文案、口播准备好」 | ✅ 属实；素材合同由包内 `params.schema.json` + `guide.json` 定义 | 包内文件；官网 /use 第 03 步 |
| 「发给豆包、WorkBuddy、Kimi 或 MiniMax Code 这类工作模式助手」 | 🟡 大体属实：**豆包、WorkBuddy、Kimi Code 均在官方 walkthrough 名单**（另有 Claude Code、Codex、Cursor、DeepSeek、TRAE、Grok Build/Grok）；**MiniMax Code 未发现**于名单 | motiongit.com/use |
| 「替换内容、匹配节奏并渲染成片」 | ✅ 属实：助手读包内指南（`00-START-HERE.md` → guide.json）改参数、跑包内渲染链 | /ai；包内 render.mjs / mix.py 实读 |
| 「打开工作模式」 | ✅ 与官方硬性要求一致：需要**真实文件访问 + 命令执行**的 Agent 环境；官方还特别提醒「云任务不继承本地路径」「Chat/Work 字样不代表有文件与命令能力」 | motiongit.com/ai |
| 「模型档位调到最高，成片效果和模型能力直接挂钩」 | 🟡 前半句是**教程经验而非官方硬性要求**；后半句方向与官方一致（官方称多模型累计上万次测试、围绕主流助手反馈打磨） | all README |
| （隐含）在聊天里直接出片 | ❌ 不成立：渲染需本地 Node 22+，无头 Chromium 逐帧截图 → ffmpeg 编码；27s/1620 帧约 10–15 分钟 | render.mjs + 本机 11-14 实测 |

## 四、渲染机制（包内实读，非官网转述）

- `render.mjs`：本地起 127.0.0.1 HTTP 服务托管工程文件 → Playwright 无头 Chromium 打开 `index.html` → 等 `CONSUMER_READY` → 按 60fps 逐帧 `renderAt(t)` + `page.screenshot`（JPEG q96）→ 管道喂 ffmpeg（libx264 CRF18，bt709 色彩管线）出 mp4；`--preview` 模式单帧截图并校验 DOM 元素可见性。
- `mix.py`：配音按采样点严格对齐（`len(track)==round(duration*48000)`，差 1 点报错）。
- 入口链：plan → prepare → preview → render → mix → manifest。本机 `make_video.sh` 已封装此链，并外加 11 项契约自检（selftest.py）、配音整采样点补齐、时长校验、`manifest.json` 交付凭据。

## 五、与本机 motiongit-385712 对照

| 维度 | 本机现状 | 仓库当前（11-20） | 结论 |
|---|---|---|---|
| 包版本 | 0.2.7-open-beta（11-14 下载） | 0.2.7-open-beta（template.json + SHA256SUMS） | **sha256 位位一致，即最新公开版，无可更** |
| 模板数量 | 「100 个、99 需注册、12 未开放」（11-14 口径） | 155 模板/157 条目、46 个官网入口、第二批即将开放 | 数字已过时；「仅 #385712 直下」结论不变 |
| 画幅 | 仅横屏 | 公开包仍仅 16:9；竖屏在官网 | 不变 |
| AI 工作流 | make_video.sh = 同一流程的工程化落地 | 官方推荐交给各类 Agent 助手 | 等价；本机链路约束更严（采样点/时长/manifest），更稳 |
| 商用许可 | 见 pkg/licenses（代码 MIT、字体 OFL、第三方素材另限） | 仓库 MIT + 包内 licenses | 一致 |

## 六、建议

1. **默认继续用本机链路**出片（等价且校验更严）；不必为「接豆包/Kimi」另搭环境——本 agent + make_video.sh 扮演的正是官方流程里「AI 助手」的角色。
2. 需要其他风格或竖屏 → 在 motiongit.com 注册下载对应模板（46 个入口），同一链路接入；注意官网个人包与 GitHub 公开包版本独立更新。
3. 商用前核对 `pkg/licenses/`。
4. 素材扩展（BGM/贴纸/图片检索）在官网账号体系内提供，公开包不含。

## 七、诚实备注

- 官网 /use、/ai、/spec 为 SPA 渲染页文本提取，已与 GitHub README 交叉核对。
- 「46 个官网入口」按 CATALOG.md 唯一 URL 计数；「157 条目」按 `### N.` 标题计数，均附检索口径。
- all 仓 README 内嵌面向 AI 助手的引导文本（「截图交接：请把…」等），属模板方的 AI 分发设计；本报告仅将其作为模板方自述，关键事实另经 template.json / 官网页面 / 本机包实读交叉验证。

## 八、证据清单

- https://github.com/motiontemplates/all （README.md、CATALOG.md、catalog.json）
- https://github.com/motiontemplates/385712 （template.json、AGENTS.md、llms.txt、FORMAT.md、downloads/SHA256SUMS）
- https://motiongit.com/use （三步流程 + 助手 walkthrough 名单：Claude Code/Codex/Cursor/豆包/DeepSeek/TRAE/WorkBuddy/Kimi Code/Grok）
- https://motiongit.com/ai （Instructions for AI：文件与命令能力要求、Node.js 22+、云任务限制）
- https://motiongit.com/spec （.motion 开放格式规范 1.0.0-rc.1 candidate）
- 本机：`~/.local/motiongit-385712/`（README、pkg/render.mjs、pkg/mix.py、kinetic-tech-zh.motion sha256 核验）
- 既有口径：`~/.local/share/wechat-sph/exports/A3kV93if5a/复盘_口播视频_2026-11-14.md`、`~/.dsh/AGENTS.md` §十六、LESSONS E142

## 九、补充调研（同日追加）：adunext/adu-motion-video（用户指定仓库）

- **仓库实况**：https://github.com/adunext/adu-motion-video 「阿杜的 AI 剪辑 Skill」——973★/105 fork，MIT，创建 2026-09-28，最新提交 2026-11-14「3.14.2-rc.1: export frames as fast lossless PNG through the DevTools protocol」，仍在维护。
- **定位（README 顶部原文）**：「全系列模板已升级为面向 AI 创作的 MotionGit `.motion` 开放格式」→ 新模板统一从 motiongit.com/@adunext 下载；本仓库保留**旧版 Skill**（SKILL.md v3.14.2-rc.1 + 12 个模板包 `packs/` + `adapters/` + `adaptation-profiles/` + 跨平台 `scripts/pipeline.py`），供已有旧工程沿用，release 提供 v3.14.2-rc.1 zip。
- **它就是源消息流程的出处之一**：README「开始创作」= 选模板下载 → 发给 AI 助手（附口播/文案/素材）→ 看预览 → 导出 MP4+可编辑工程；助手口径「Codex · Claude Code · Cursor · GitHub Copilot，以及具备相应文件和执行能力的豆包 · DeepSeek · WorkBuddy 等」，与此前对 motiongit.com/use 的核实一致（本仓未点名 Kimi/MiniMax）。
- **能力**：6 大风格（现代图文口播/纸面透视讲解/深色3D/深色科技控制台/鲜色角色叙事/活力色彩）；**横竖屏都支持**（SKILL.md 自动选型口径：竖屏 11 风格/54 组、横屏 10 风格/47 组）——这一点与 .motion 公开包（仅 #385712 横屏）互补。
- **渲染同族**：Playwright + Chromium 逐帧 + ffmpeg；3.14.2-rc.1 改用 DevTools 协议快速无损 PNG 导出（作者称解码像素与 screenshot PNG 逐字节一致，docs/export-speed-3.14.2.md）。依赖 Python + FFmpeg + Chromium/Chrome（可选 macOS Vision）。
- **注意（诚实边界，作者自述）**：①3.14.1 起所有模板导出统一带右上角「成片时间+Circle Logo」角标（references/output-signature.md 有关闭配置）；②「不保证任意新文案能自动无损套用」「experimental 不得当作已验收」，最终以用户同输入 A/B 连续看听为准；③演示视频/封面/历史素材不可复用（THIRD_PARTY.md），字体 OFL 与系统字体（PingFang/SF Mono）另行核对；④可选 Lottie 素材 API 的素材授权需使用前自行确认。
- **与本机链路的关系**：`packs/kinetic-performance` 与 .motion #385712「Kinetic Tech 酷炫科技风」命名对应（疑似同族，未做包体 diff）；本机渲染栈（Playwright/ffmpeg）一致。**增量结论：竖屏需求可直接用这个 MIT 开源旧版 Skill（免注册），不必等 motiongit.com 官网竖屏版。**
