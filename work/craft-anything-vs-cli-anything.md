# 调研：craft-anything 与 cli-anything 对比说明

> 调研日期：2026-11-07。数据来源：GitHub API（仓库元数据、Release、贡献者）、两仓库官方 README、PyPI 官方源、官网连通性检查。
> 约定：以下均为官方来源可查证的信息；查不到的明确标注"未查到"，不做推测。Star 数等为当日快照。

## 一句话结论

两个都是 2026 年 AI-agent 生态里爆火的同名风格（"X-Anything"）开源项目，但**来自不同团队、解决不同问题，是互补关系不是竞品**：

- **Craft Anything**（storytold / ArtCraft 社区，Rust）：看懂任意软件是怎么做的，再让 AI 编码 agent **复刻一个你自己的新版本**。
- **CLI-Anything**（HKUDS，Python）：给任意软件**自动生成 agent 可用的 CLI**，让 AI agent 去驱动现有软件（不重写软件本身）。

## 基本信息（2026-11-07 快照）

| | Craft Anything | CLI-Anything |
|---|---|---|
| 仓库 | [storytold/craft-anything](https://github.com/storytold/craft-anything) | [HKUDS/CLI-Anything](https://github.com/HKUDS/CLI-Anything) |
| 定位原话 | "understand how any software works, and craft your own" | "Making ALL Software Agent-Native" |
| 主语言 | Rust（约 9.8MB 代码） | Python（≥3.10，约 11MB 代码） |
| Stars | ≈19,400 | ≈58,400 |
| Forks | ≈3,650 | ≈5,250 |
| 贡献者 | 68 | 100+（按页上限） |
| Open issues | 214 | 240 |
| 创建时间 | 2026-10-31（仅一周） | 2026-03-08（约 8 个月） |
| 最新提交 | 2026-11-07（当天，极活跃） | 2026-09-22（约 6 周前） |
| Release | v0.5.0（2026-11-06），一周内连发 5 个版本 | v0.4.0（2026-06-25），此后无新版本 |
| 许可 | **MIT 或 Apache-2.0 双许可**（任选其一；品牌商标除外） | **Apache-2.0**（注：PyPI 包 cli-anything-hub 元数据标 MIT） |
| 官网 | getartcraft.com（ArtCraft 社区） | clianything.cc / hkuds.github.io/CLI-Anything |
| 技术报告 | 未查到 | arXiv:2606.03854《CLI-Anything: Towards Agent-Native Computer Use》 |
| 安装渠道 | GitHub Releases 安装包（Win/macOS/Linux/FreeBSD，签名+公证）+ WASM 网页版；源码需 Rust 1.97+；未上 crates.io/npm/PyPI | PyPI：`pip install cli-anything-hub`（v0.4.1，2026-07-09）；Claude Code 插件市场；`npx skills add` |

## 定位与能力对比

### Craft Anything：逆向理解 + 复刻重建
- **核心流程**：Study（检查原作）→ Build（编码 agent 构建新项目）→ Check（与原作对比相似度）→ Ready（打开/继续修改迭代）。
- **引擎**：纯 Rust 逆向检查引擎，**320 个工具**（约 300 个引擎工具，每个都是 CLI 子命令 + MCP 工具），覆盖原生程序、.NET、Java、Android、Apple、Electron/JS、网站、固件、抓包、数据库、游戏文件；自带反汇编器/反编译器（Deep 模式下可用已装的 Ghidra）。
- **两种模式**：Clean-room（默认：只依据"看得见的"证据，不读原作代码/文件/源码）与 Deep（本机私有使用时读取内部实现）。官方明确：clean-room 是工具取舍规则，不是系统级沙箱。
- **构建 agent**：首选 Claude Code（用你本机登录态，项目不经手账号）；Codex 适配器已写但未经真机验证；Copilot CLI、Grok 走 ACP；其他 ACP agent（Gemini CLI、Qwen Code、opencode、goose 等）可切换，官方称仅 Maki 实测跑通。
- **形态**：桌面应用（egui）+ CLI（`craft-anything-cli`）+ MCP server + 浏览器 WASM 文件识别器。
- **声明状态**：官方自认 **early alpha**。可用：Claude Code 作为 builder 的网站/应用/游戏复刻工作流、三宽度网页比对、Unity/Unreal/Godot 游戏重建、Deep+Ghidra；部分能力"未实测"。
- **红线声明**：不绕过 DRM/登录/反作弊；不主动复制受版权保护的素材。

### CLI-Anything：把现有软件包装成 agent 的 CLI
- **核心能力 1（生成）**：7 阶段自动流水线——给定一个有代码库的软件，自动完成架构设计、CLI 实现、测试计划、测试编写、文档与 SKILL.md 生成、直至 PyPI 发布。方法论沉淀为 `HARNESS.md`（自称 single source of truth）。
- **核心能力 2（分发）**：**CLI-Hub** 包管理器（`pip install cli-anything-hub`），官方称收录 40+ 现成 agent-native CLI：GIMP、Blender、Krita、FreeCAD、QGIS、LibreOffice、OBS、Audacity、Zotero、Obsidian、Calibre、Joplin、Draw.io、n8n、Zoom、Godot、Ollama、ComfyUI 等（覆盖创意/办公/科研/游戏/网管等类别）。
- **Agent 适配**：Claude Code 插件（marketplace）、Pi 扩展、OpenClaw、Cursor、nanobot、Codex/Gemini/Qoder skill 等多种接入方式；输出统一 JSON + 人类可读双模式；统一 REPL（ReplSkin）；每个 CLI 自动生成 SKILL.md 供 agent 发现。
- **质量基线**：README 测试汇总表 **2,464 个测试通过**（约 30 个 harness 的 unit+E2E），E2E 直连真实软件（LibreOffice 出真 PDF、Blender 真渲染）。
- **官方 Limitations（如实转述）**：依赖 frontier 级模型（弱模型产出质量差）；目标软件只有二进制、没有源码时质量显著下降；常需多轮 `/refine` 迭代。

## 成熟度与风险对比

| 维度 | Craft Anything | CLI-Anything |
|---|---|---|
| 项目年龄 | ~1 周（org 本身约 3 周前才建库） | ~8 个月 |
| 增长 | 一周 19.4k stars，每日多提交，5 个 release | 8 个月 58.4k stars，曾上 GitHub Trending / Trendshift |
| 当前节奏 | **极快**（当天仍有提交，隔天发版） | **明显放缓**：最后 release 2026-06-25、最后 PyPI 2026-07-09、最后提交 2026-09-22；README 新闻止于 2026-05-30 |
| 自评状态 | early alpha（官方明示部分功能未实测） | 生产级测试基线，但官方写明对模型与源码的强依赖 |
| 发布物完备度 | 四平台签名/公证安装包 + WASM，工程化程度高 | PyPI 包 + 插件市场 + skills 分发，工程化程度高 |
| 组织背书 | storytold / ArtCraft（社区组织，旗下还有 PhotoCraft 等十余个同风格应用仓库，star 都很小）；**未查到背后公司/机构信息** | HKUDS（GitHub 知名开源组织，同门有 DeepTutor 56k★、nanobot 49.9k★、LightRAG 40.6k★、DeepCode 16.8k★，本周仍在活跃推送）；有正式 arXiv 技术报告 |

## 相同与互补

**相同点**：都借 "X-Anything" 命名潮流；都面向 AI agent（而不只是人）；都把能力同时暴露为 **CLI + MCP**；都强调证据/结构化输出；GitHub 上存在大量同名镜像/包装仓（如 shuv1337/craft-anything 镜像、saintedKyle/craft-anything-skill、ItamarZand88/CLI-Anything-WEB 等），主流所指即上述两个主仓。

**互补而非竞争**：
- 产物不同：Craft Anything 输出**一个新的软件项目**；CLI-Anything 输出**驱动既有软件的 CLI 接口**。
- 依赖不同：Craft 逆向不需要目标源码（Clean-room 明确不读）；CLI-Anything 官方声明**必须有源码**才有一流效果。
- 可组合：理论上可先拿 CLI-Anything 驱动现有软件完成工作；要"再造一个自己的"时用 Craft Anything。

## 与本机 agent 生态（DSH/OpenClaw）的相关线索

- CLI-Anything 官方支持 OpenClaw（2026-03 社区合入支持），CLI-Hub meta-skill 在 ClawHub/SkillHub 有上架，agent 可自主发现并安装 CLI。
- DSH 生态已出现 Craft Anything 的桥接项目：Fanqi89/dsh-craft-anything（89★，把 craft-anything CLI 桥接为 `mcp__craft__*` MCP 工具）。

## 未查到 / 不确定的信息（如实说明）

1. 两项目**未查到任何官方关联**（不同组织、README 互不引用）；同属一拨命名潮流仅为观察，非官方说法。
2. Craft Anything 背后的 ArtCraft/storytold 团队的公司或机构背景：未查到官方信息。
3. Craft Anything README 列出的 16 个 "Craft App Suite" 应用是否全部真实可用：未逐一验证（各仓 star 都很小）。
4. CLI-Anything 主仓 2026-09-22 之后无提交，是否转移到别处或仅暂停：未查到官方说明。
5. "测试 2,464 通过""40+ CLI""320 工具"均为两项目官方 README/PyPI 自述数字，未独立复测。

## 证据文件

- `work/research/craft_meta.json`、`work/research/cli_meta.json`（GitHub API 元数据）
- `work/research/craft_releases.json`、`work/research/cli_releases.json`（Release 列表）
- `work/craft_readme.md`、`work/cli_readme.md`（两仓库官方 README 全文快照）
- PyPI `cli-anything-hub` 官方 JSON（v0.4.1，2026-07-09）
