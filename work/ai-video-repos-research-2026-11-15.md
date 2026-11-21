# 视频提到的 5 个 AI 视频仓库 · 清单核对报告

- 工单：video-skills-review-1a681e3015c8（源：飞书群 2026-11-14 消息，用户看视频抄的清单）
- 核实日期：**2026-11-15**（全部数据当日经 GitHub API `gh api` 实测：stars/forks/最近推送/许可证原文/README/文件树）
- 评价框架声明：本报告前半是**审计**（名字对不对、仓库在不在、许可证是什么），后半是**复用映射**（对照 `~/.dsh/AGENTS.md` 第 16 节的现有口播管线：motiongit 模板路线 + 真人换声/Wav2Lip 口型路线 + SenseVoice ASR + 逐句字幕）。未克隆运行任何仓库，复用结论基于 README/许可证文本/文件结构，未实测渲染。

## 一、结论速览

| # | 视频里的名字 | 实际仓库 | 存在 | Star | 最近推送 | 许可证 |
|---|---|---|---|---|---|---|
| 1 | awesome-opus-5-videos | [yihui-dev/awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos) | ✅ | 15,213 | 2026-10-13 | MIT |
| 2 | awesome-opus-5-videos（双语版） | [zhuyansen/awesome-opus-5.5-video](https://github.com/zhuyansen/awesome-opus-5.5-video)（最接近项，见 §2.2） | ✅ | 337 | 2026-11-14 | **无许可证** |
| 3 | lemo-opuscars | [lemomo-ai/lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) | ✅ | 16,117 | 2026-11-12 | **多重许可**：代码 MIT / 文档 CC BY-NC 4.0 / 影片 CC BY 4.0 |
| 4 | pdcom-video-mexicat | [mexicat/pdoom-video](https://github.com/mexicat/pdoom-video) | ✅ | 3,903 | 2026-10-05 | MIT |
| 5 | PDcom-Video-JohnHeibel | [JohnHeibel/PDoomVideo](https://github.com/JohnHeibel/PDoomVideo) | ✅ | 2,931 | 2026-09-25 | **无许可证** |

5 个仓库全部真实存在。视频转写名与真实名有三处出入：

- 「opuscars」实为 **lemo-opuscar**（单数，无 s）；
- 「pdcom」实为 **P(doom)**——来自歌曲名 *I'm Upping My P(doom)*；
- 第 4、5 项是**同一首歌的两个独立 MV 工程**：#4 是用户 `mexicat` 的 `pdoom-video`，#5 是 `JohnHeibel` 的 `PDoomVideo`（"PDcom-Video-作者名" 是转写拼接，不是仓库命名规则）。

另有用户追加的第 6 个项目 **aicodeking/leanrea**（非视频项目，逆向提效 skill），核对见 §五。

## 二、逐项核对

### 2.1 yihui-dev/awesome-opus5-5-videos（对应视频第 1 项）

- 2026-09-27 创建，最后推送 2026-10-13（README 内容更新停在 2026-10-12），15,213⭐ / 1,606 forks，14 个 open issues。
- 内容：Opus 5.5 生成的爆款代码视频案例库（HTML/Canvas/SVG/Three.js 等代码渲染，无视频模型），**703 条提示词**（`prompts/` + `data/videos.json`），418 条在 Skillry 上有对照重制，每条链回作者原帖。分类：动效 58 / 科普 16 / 3D 场景 14 / 游戏 12。
- 许可证 **MIT** ✅。视频描述「附原帖和提示词」与实际一致。

### 2.2 zhuyansen/awesome-opus-5.5-video（对应视频第 2 项「双语版」，最接近项）

- 2026-09-27 创建，**仍在日更**（最后推送 2026-11-14），337⭐ / 36 forks。
- `README.md`（英文）+ `README.zh-CN.md`（中文）双语 ✅；分类与视频口径吻合：动效与 UI、**产品演示与广告**、**科普教育**、角色与故事、**3D 世界与仿真**、游戏、音乐剪辑。
- 规模：2,806 个作品（Opus 5.5: 2617 / Sonnet 5.5: 144 / Fable 5.5: 130），643 个带提示词（316 条完整提示词）；收录线为原帖 5,000+ 播放；`cases.json` 结构化数据；在线浏览站 jasonzhu.ai。
- 许可证：**仓库无 LICENSE 文件**（文件清单已核实）→ 默认版权保留，只能浏览/参考。
- 认定说明：视频没给 URL，这是「双语 + 分类吻合」的最接近项；备选：[chuspeeism/awesome-opus-5-5-videos](https://github.com/chuspeeism/awesome-opus-5-5-videos)（114⭐，中文为主、300 例）与 [X-RayLuan/awesome-opus-5-5-video-prompts](https://github.com/X-RayLuan/awesome-opus-5-5-video-prompts)（25⭐，EN+中文提示词）。存在认错可能。

### 2.3 lemomo-ai/lemo-opuscar（对应视频第 3 项）

- 2026-09-26 创建，最后推送 2026-11-12，16,117⭐ / 2,014 forks，7 个 open issues。
- 定位：给 coding agent 用的「代码制片风格工具箱」。**当前 99 种风格**、15 个分类（README 口径；`styles/` 目录现含 101 个条目）。视频说的「59 种」对应较早版本，具体哪个版本是 59 未逐版考证（2026-11-12 一次新增 33 种）。每种风格 = STYLE.md 风格提示词 + 一支纯代码渲染的演示片（画廊站 lemomo-ai.github.io/lemo-opuscar）。
- 制片链：选风格 →（可选分镜确认）→ agent 写代码逐帧渲染 canvas/WebGL → **TTS 旁白**（默认 Kokoro）→ 免费采样库配乐 → 混音。**无视频生成、无实拍素材**。配套技术指南 ✅：`TECHNIQUE.md`（逐帧渲染/声音/音乐/混音）、`DIRECTOR.md`、`AGENTS.md`/`CLAUDE.md`。依赖：Node 20+、ffmpeg 7+（Ubuntu 24.04 自带 6.1 不够）、Python 3.11+ 或 uv。
- 安装：`claude plugin install lemo-opuscar@lemolab`（其他 agent 可复制 `plugin/skills/lemo-opuscar/`）。上游声明为 Claude 调优（effort high），**其他模型能否复现风格未验证**。
- 许可证（读的是 LICENSE + REUSE.toml 原文，GitHub API 归类显示 NOASSERTION/"Other"）：
  - **代码**（core/、tools/、styleboard/、plugin/、各演示片代码）：**MIT**；
  - **文档**（全部 Markdown，含各风格 STYLE.md、TECHNIQUE.md）：**CC BY-NC 4.0**（非商业），但作者附加许可：允许你和你的项目团队**照文档做片（含商业/客户委托片）**并把改编文档放进交付的项目文件；对外再分发/装进产品/售卖仍需商业授权（lemomo.studio@gmail.com）；
  - **影片/图片**（演示片、海报、剧照、字幕 srt）：CC BY 4.0；
  - **6 条 TTS 旁白音轨被排除**（Edge TTS/Doubao TTS 生成）：不可提取复用；
  - **Clawd（橙色小吉祥物）被排除**：是 Anthropic 的 IP，无授权；
  - **你用工具箱做出的片子归你，可商用，无需署名**；
  - 版本边界：LICENSE 原文注明 **2.0.0 之前发布的版本及其 fork 沿用当时许可**；已实测旧快照（`assets` 标签）的 LICENSE 为纯 MIT —— 即旧版整库（含文档）按 MIT 用没问题，v2.0.0 起文档改 CC BY-NC。

### 2.4 mexicat/pdoom-video（对应视频第 4 项）

- 2026-09-24 创建，最后推送 2026-10-05，3,903⭐ / 433 forks，MIT ✅。
- 与视频描述逐条吻合 ✅：「卡拉OK式MV」＝ word-synced karaoke typography；「歌词逐词同步」＝ `data/lyrics.json` 存词级（部分音节级）时间戳；「本地渲染 4K 60帧」＝ 离线导出 1080p60 / 4K60，浏览器预览与离线导出逐帧一致（每帧是歌曲时间的确定性函数）。
- 技术栈：渲染 TypeScript + three.js（bun + Vite），离线渲染 = 无头 Chrome（playwright-core）抓帧 → WebSocket 传原始帧 → ffmpeg 合成；歌词对齐分析 = Python(uv)：**Demucs 分轨 + CTC 强制对齐、Whisper 交叉校验 + 节拍/强拍/起音/响度分析**（`analysis/align.py`、`analysis/analyze.py`）。
- 这是单首歌曲的完整工程（含歌曲音频本身，歌曲版权属原作者，见其 Credits），不是通用框架。

### 2.5 JohnHeibel/PDoomVideo（对应视频第 5 项）＋ 配套

- 2026-09-22 创建，最后推送 2026-09-25，2,931⭐ / 283 forks。**无 LICENSE 文件**（文件清单已核实）→ 默认版权保留，**只能拆解学习，不能搬代码**。
- 与视频描述逐条吻合 ✅：手绘风 MV 源码（p5.js + p5.brush 水彩笔刷、Clawd 角色）、`STORYBOARD.md` 分镜、`ANIMATION_GUIDE.md` 动画指南、`render.mjs` 渲染脚本（无头 Chrome 逐帧 + ffmpeg 合成 MP4，支持分段断点续渲、多 worker）。全部代码由 Opus 5.5 在 Claude Code 里两代生成，`STORYBOARD.md`/`ANIMATION_GUIDE.md` 也是模型写的。
- 歌曲音频随仓库附带（`assets/pdoom.mp3`），歌曲本身是第三方作品，同样不可再利用。
- **干净的可复用替代**：同一作者的 [JohnHeibel/ClaudeAnimationBase](https://github.com/JohnHeibel/ClaudeAnimationBase)（2,984⭐，**MIT**，README 自述是更通用可靠的 Claude 手绘动画基底）：p5.js + p5.brush 起步套件、Clawd 角色与 31 种表演情绪 + 指南。要玩手绘风用这个。注意 Clawd 形象是 Anthropic IP，商用物料慎用。

## 三、与现有口播/口型管线的复用评估

现有管线基线（`~/.dsh/AGENTS.md` §16）：默认走 motiongit 模板路线（`~/.local/motiongit-385712/`，仅横屏 1080p，B1–B4 分组 + 阅读停留凑时长）；真人路线 = 换声 + Wav2Lip 对口型（96×96 唇形上限）；字幕为逐句；ASR 用 SenseVoice；合成用 ffmpeg。

| 仓库 | 复用判定 | 说明 |
|---|---|---|
| yihui-dev 案例库 | **可复用（参考层）** | MIT；提示词可自由取用喂给任意 coding agent 产代码视频；案例视频本身版权归各自作者，商用成片需自行取得授权。与现有模板路线零冲突，是「模板之外的风格灵感库」。 |
| zhuyansen 双语清单 | **仅浏览参考** | 无许可证：cases.json/提示词清单不整库搬运、不进产品；当索引和找案例的入口用。更新最勤（日更）。 |
| lemo-opuscar | **复用价值最高，可直接接入** | 就是一条现成 skill 制片链（风格→分镜→代码逐帧渲染→TTS 旁白→配乐→混音），与口播场景天然契合（自带旁白/配音环节）；做出来的片子归我们、可商用。代码 MIT 可改造。约束：文档 CC BY-NC（自用做片 OK，别把 STYLE.md 等文档整编进对外产品；需要宽松许可可取 <2.0.0 旧版，其 LICENSE 为纯 MIT）；ffmpeg 7+ 依赖；上游为 Claude 调优，本机非 Claude 模型的风格复现质量未验证。与 Wav2Lip 口型路线无交集（它不做人脸/口型）。 |
| mexicat/pdoom-video | **可拆件复用（MIT）** | 最有工程价值的可搬运件是**逐词对齐分析链**（Demucs + CTC 对齐 + Whisper 交叉校验 → 词级时间戳）：搬进现有管线可把口播字幕从「逐句」升级为「逐词卡拉OK」，词级时间戳通常比 ASR 直出时间戳更稳。确定性时间线 + 无头 Chrome 抓帧 + ffmpeg 的渲染架构可作代码视频渲染参考。需从单歌曲工程中抽链适配。 |
| JohnHeibel/PDoomVideo | **仅拆解学习** | 无许可证，不搬代码。STORYBOARD/ANIMATION_GUIDE 当「AI 自写分镜/子代理指南」的方法论样本读。手绘风想动手就用其配套 ClaudeAnimationBase（MIT）。 |

综合判断：

1. **短期最值得动手**：`claude plugin install lemo-opuscar@lemolab` 试 1–2 条适合科普/讲解的风格，与 motiongit 模板路线做 A/B；两路并存不冲突（模板=固定版式快产，lemo=风格化代码片）。
2. **顺手可做的增强**：从 pdoom-video 抽 `analysis/` 对齐链（MIT），给现有口播字幕上词级时间戳。
3. **版权红线**：zhuyansen 与 JohnHeibel/PDoomVideo 无许可证 → 只看不搬；lemo 的 6 条 TTS 音轨、Clawd 形象（两个仓库都涉及）不提取、不商用。
4. 这 5 个项目都**不涉及真人换声/口型**，对 Wav2Lip 管线没有直接输入；它们与现有管线的交集在「代码渲染视频」与「字幕对齐」两处。

## 五、补充核对：aicodeking/leanrea（用户 2026-11-14 追加）

- [aicodeking/leanrea](https://github.com/aicodeking/leanrea) **真实存在**：MIT，4,277⭐ / 645 forks，2026-10-17 创建、最后推送 2026-10-19（单个 SKILL.md 项目，无持续维护压力）。
- 用户转述逐条核对：
  - 「8KB 的 SKILL.md」✅：`leanrea/SKILL.md` 实测 8,374 字节；
  - 「不装 MCP、不堆工具，直接跑本地命令行」✅：对照对象是 [morluto/rea](https://github.com/morluto/rea)（REA 6.5.0，207 个 MCP 工具；全量加载时上下文 400.7k tokens/$1.60，leanrea 仅 34.5k/$0.09）；
  - 「快 38%、便宜 35%、准确率基本持平」✅ 有出处，是**仓库自带基准**（`bench/BENCHMARK.md` + 原始数据 `bench/results/final.jsonl` + 可复跑脚本）：Claude Code headless + Sonnet 5.5、macOS arm64，4 个逆向任务 × 3 次 × 3 臂共 36 跑、正则对照手工答案键评分。结果 leanrea 388s / $2.17 / 74-75 分 vs REA 627s / $3.36 / 75-75 分 → 时间 −38%、成本 −35%、turns −56%、tokens −60%，准确率 74 vs 75（一处部分命中：报了旧 IPC 通道）。
  - 注意口径：38%/35% 是 **vs REA（MCP 路线）** 的数字；vs「完全不用 skill」的裸模型增益小得多（作者自述约 −19% 时间、−32% turns）。
- 作者自述的基准局限（README 原文）：每格仅 3 次、单模型单机；REA 按其最优情形测（Claude Code 延迟加载 MCP 工具；全量加载工具的 agent 才吃 400k-token 行）；Ghidra/Hopper/jadx 未安装、native 任务两臂都用 Xcode 工具。**本报告未复跑该基准**，数字按仓库自测采信。
- 定性：本质是一份「按 `file -b` 路由到每类目标最快命令 + 踩坑清单 + 证据纪律」的 cheat-sheet（SKILL.md 要求答案逐条标注 seen/inferred/unknown、`rg -uu` 搜解包树、批量探测单次调用、head 截断输出）——与本机工作约定第五节（报错先检索）和第十一节（缺失断言降级）的纪律同向。
- 归属说明：**与现有口播/口型视频管线无交集**，属逆向/agent 提效域；对本机 ida-reverse / ghidra-reverse / reverse-skill-router 栈是「轻量路由层」思路的参考。用户「深度加壳混淆仍需 IDA/Ghidra」的判断与 SKILL.md 自身定位一致（它是路由层，不替代反编译器）。
- 安装：`npx skills add aicodeking/leanrea`（skills CLI，支持 Claude Code / Codex / Cursor / Gemini CLI 等）。

## 六、补充核对：bojieli/ai-agent-book（用户追加）

- [bojieli/ai-agent-book](https://github.com/bojieli/ai-agent-book) **真实存在**（URL 大小写不敏感，规范名为全小写）：《深入理解 AI Agent：设计原理与工程实践》（李博杰 著），**Apache-2.0**，**58,020⭐ / 6,749 forks**、61 open issues，2025-09-09 创建、最后推送 2026-10-08。作者 GitHub 账号 bojieli（Bojie Li，Independent Researcher，3,352 followers）与书署名一致；「前华为天才少年」为其公开报道身份，本次未另行核实。
- 内容体系核对（README 2.0 版十章表，逐项命中）：上下文工程 ✓(ch2)、用户记忆/知识库 ✓(ch3)、工具调用与 MCP ✓(ch4)、Coding Agent ✓(ch5)、交互/语音/Computer Use ✓(ch6)、评估 ✓(ch7)、模型后训练 ✓(ch8)、持续进化 ✓(ch9)、多 Agent 协作 ✓(ch10)；**提示注入攻防 ✓**（ch2 专节「提示注入：上下文安全的核心威胁」，ch4 展开工具描述投毒/MCP 安全/Sidecar，ch5 展开三层护栏/网络出口控制——已抽查 ch2/ch4/ch5 原文命中）。
- 「90 多个可运行案例」核对：README 官方口径为 **109 个配套实验**（分章实验数 4+10+12+5+16+14+14+19+9+6 = 109，与总口径一致），分三档标注：✅ 可运行 / 📖 复现 / 🚧 设计，另含附录 22 个外部复现仓库（版本固定到 2026-07-30 checkout，9 个缺失 checkout 固定到不可变 SHA）。所以「90 多个」成立（实际 109）；但「每个都能在本地复现」要打折：部分实验依赖 API 密钥、浏览器/CUDA/FFmpeg/Ollama 等系统依赖或外部仓库，README 自己声明「源码存在或安装成功都不是实验完成声明」。环境要求 Python 3.11–3.13 + uv（推荐 uv.lock）。
- 其他事实：全书正文 `book/chapter1~10.md` + 配图 + 编译版 PDF/EPUB（releases）+ 15 种语言在线阅读站（bojieli.github.io/ai-agent-book）；姊妹篇 bojieli/ai-infra-book 已开源；GitHub Trending Project of the Day 徽章。
- 未证实项：「中文圈体系最完整」为宣传口径，无法客观验证（未做同类书对比），按未证实采信。
- 归属：与现有口播/口型管线无直接交集，属 **AI Agent 工程学习域**；对本机 agent 开发（含 DSH/superagent、jiangerhuo 记忆/图谱体系）的上下文工程、评估、提示注入防御章节有直接参考价值。

## 七、核实方法与局限

- 数据来源：GitHub REST API via `gh api`（repo 元数据、contents、git tree、README/LICENSE 原文），检索用 `gh search repos`；所有 star/日期/许可证数字为 2026-11-15 实测值，会随时间变化。
- 许可证判定以仓库内 LICENSE/REUSE.toml 原文为准，未依赖 GitHub 的归类字段（lemo-opuscar 在 API 中显示为 "Other"/NOASSERTION）。
- 局限：① 第 2 项「双语版」为最接近项推断，视频未给 URL，存在认错可能（备选已列）；② 未克隆运行任何仓库，渲染效果与依赖坑未实测；③ lemo-opuscar 旧版「59 风格」对应的具体版本号未逐版考证；④ 「视频里提到的」原始出处（哪个视频）我们未看到，仅按用户转写文本核对。
