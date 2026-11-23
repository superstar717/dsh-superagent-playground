# video-shotcraft 真实能力调研（以仓库代码/文档为准）

> **调研时间**：2026-11-23 12:00–12:20 CST
> **上游版本**：`Vincentwei1021/video-shotcraft` @ [`59f3e9b`](https://github.com/Vincentwei1021/video-shotcraft/commit/59f3e9b9e936ff2bce0e18446226d770a3f2f61f)（2026-11-21）
> **方法**：完整克隆仓库读代码/文档；用 GitHub API 取元数据；拉取在线 Gallery 的 `library.json` 与 `showcase.json`；查官方模型文档；在本机跑一次 Remotion still 渲染。**没有拿到视频原片/链接，以下按你给的摘要逐条核**；若原话与摘要不同，以原片为准。
> **证据等级**：A=仓库代码/文件；B=仓库文档/作者自述；C=第三方实测/转述；D=视频单方说法。

## 一句话结论

**项目是真的，但视频把它说大了。** 它是一个给 Claude Code / Codex 用的 **Agent Skill**（124 张镜头配方卡 / 150 个镜头样式 + 36.2 秒模板 + 浏览器工作台 + 剪映导出模块），不是“普通人一键出片的 App”，也不是视频生成模型。核心能力（用真实页面截图写 Remotion 代码、自动排分镜、出 MP4、导剪映草稿）在仓库里都有对应实现；但“150 个大厂经典动效库”“剪映画面前分层”“便宜模型媲美 Opus 5.5”这些说法需要降级理解，部分没有仓库证据。

![本次实测渲染的模板 frame 150（1920×1080，缩放到 1280 宽）](assets/video-shotcraft-frame150.jpg)

*本次在 macOS 13.7.8 上 `npm ci` + `npx remotion still ... --frame=150` 成功产出的真实画面；不是官方样片截图。*

## 它到底是什么

先纠正一个常见误解：**它不是一个“视频生成模型”，也不是一个独立 App。**

- 仓库根目录的 `SKILL.md` 是给 coding agent 读的“制作手册”；`references/` 是方法论文档；`references/shots/` 是 124 张配方卡；`demos/` 是每张卡的 Remotion 参考实现；`template/` 是一支可运行的 36.2 秒成片工程；`workbench/` 是交付后的浏览器剪辑台；`jianying-export/` 是剪映草稿安装模块。
- 仓库自己写得很清楚：**“It is not a video generator. Every frame is drawn by code from your own screenshots and copy.”**（[`README.md` L39](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/README.md#L39)；中文版 [`README_CN.md` L38](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/README_CN.md#L38)）
- 它的“自动化”来自**外部 coding agent**（Claude Code / Codex 或兼容 agent）读这些文档、跑命令、写 TSX；仓库里没有内嵌 LLM API 调用，也没有“输入一句话就出片”的独立服务。
- 工作流是：抓真实页面 → 选镜头卡排分镜 → 写 Remotion 代码 → 卡点/音效 → 渲染与逐帧验收 → MP4 / 工作台 / 剪映草稿。
- 运行环境不是“装个 App”：Node/npm、ffmpeg/ffprobe、uv（BGM 节拍分析）、puppeteer（抓页面）、Remotion 首次下载无头 Chrome，以及一个能读写文件、执行命令的 coding agent（[`README_CN.md` L180–L189](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/README_CN.md#L180-L189)）。

## 逐条核验

| 视频摘要里的说法 | 仓库里的实际情况 | 判定 |
|---|---|---|
| **150 个大厂经典动效库** | 124 张配方卡 / 150 个镜头样式（10 类）；README 致谢确实列了 ClickUp、Perplexity、Slack、Notion、Figma、Framer、Bear、Raycast、Pitch、Miro、Superhuman、Loom 等 12 家产品宣传片作为“动效语言研究”来源；但实现是**从零重写**，仓库不含原片素材/品牌资产，且明确“无关联、未背书”；逐卡来源表只覆盖 38 张，部分来源标注“未获复刻许可”。 | **数字基本属实；“大厂授权/原版库”不成立，口径夸大** |
| **自动分镜** | `SKILL.md` + `references/pipeline.md` 定义了 8 阶段流程；在“自主自由创作”模式下，agent 可连续推进、不逐阶段等确认；“共同创作”模式则会在产品简报、视觉方向、镜头映射、最终分镜处让用户确认。仓库没有独立的“分镜算法”代码；这是 agent 行为。 | **能力上成立，但不是一键产品功能；依赖 agent/模型** |
| **自动写动效** | agent 会读选中的配方卡 + 对应 `demos/` 的 TSX，再改写成目标产品的 Remotion 代码。`SKILL.md` 明确说“凭卡名和理解新写＝放弃全部调校积累”。仓库提供 124 张卡和 150+ demo，不是文本→视频模型。 | **成立，但准确说是“写/改 Remotion 代码”，不是“生成视频”** |
| **自动配卡** | 仓库没有叫“自动配卡”的功能。若指“给功能挑镜头卡”：`pipeline.md` 阶段 2 会扫描全部卡片的 frontmatter，由 agent 为每项功能选首选/备选卡；若指“自动配乐/卡点”：有 `references/music-beat-sync.md` 的方法，需要 BGM，由 agent 跑 librosa/uv 分析，不是打包好的一键按钮。 | **表述模糊；挑卡/卡点都“有方法、无独立功能”** |
| **导出剪映草稿（字幕/音效/画面前分层）** | 真实实现：`jianying-export/` 有 Mac/Windows 安装模块、模板片专用 `aifl_promo.py`、冒烟测试；`references/jianying-export.md` 给出完整建轨方法。**但**：Mac 剪映 11.2 实测通过，Windows 未真机验证；剪映保存后单向加密；新机器常缺设备指纹、需 donor 草稿；画面前景/背景**没有分层**——底片是一条按镜头切段的视频轨，镜头内动效已烘焙，只有可选画中画；字幕/音效才是独立轨。 | **“字幕/音效分轨”属实；“画面前分层”不准确；平台/版本限制明显** |
| **便宜模型媲美 Opus 5.5** | 仓库通篇没有出现 `Opus` / `Anthropic`；没有模型基准、没有“便宜模型”配置，只写“为 Claude Code 和 Codex 调校”。**另外，摘要里“Opus 5.5 型号名称与官方命名不符”这条是错的**：Claude Opus 5.5 是官方真实型号（2026-09-22 发布，Bedrock 型号 `claude-opus-5-5`，1M context / 128K output）。 | **“型号不存在”不成立；“便宜模型媲美 Opus 5.5”无仓库证据，属视频单方说法** |
| **普通人也能做 / 发布会级质感** | “降低门槛”相对成立，但绝对门槛不低：要装 Node、ffmpeg、uv、puppeteer、Remotion Chrome，要能跑本地 dev server，要有一个能执行 shell 的 coding agent（Claude Code/Codex 订阅），还要会处理渲染/素材/验收。“发布会级”没有客观标准；模板画面质量确实不错（本次 still 可见），社区 Showcase 有 25 条投稿，其中 22 条来自其他作者（3 条为作者自带样片），但都是自投稿/作者策展，不是独立质量评测。 | **“降低门槛”相对成立；“普通人”“发布会级”是营销化表述** |
| **开源项目** | 代码/文档 Apache-2.0；但整条链路不是全免费/全开源：Remotion 有自己的许可（个人/小团队免费，公司可能需要付费），Freesound/BGM 有逐文件许可，Claude Code/Codex 要订阅，渲染要时间和硬件。仓库自己写了 Remotion 许可提醒（[`README_CN.md` L258](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/README_CN.md#L258)）。 | **代码开源属实；“免费/零门槛”不成立** |

## 详细核验

### 1. “150 个大厂经典动效库”：数字对，来源叙事要小心

- **数字口径**：`README_CN.md` 写“124 张配方卡，分 10 类，共 150 个镜头”（[L121](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/README_CN.md#L121)）；`gallery/api/library.json` 的 stats 也是 `cardCount: 124`、`styleCount: 150`、`previewCount: 150`。所以 **150 是“镜头样式/样片数”，不是 150 张卡**；视频把两者混着说。
- **“大厂”有依据，但不是“大厂库”**：README 致谢明确列了 12 家公司的官方宣传片作为研究来源（[L262–L265](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/README_CN.md#L262-L265)）。但同一段紧接着说：**“从零重新实现的动效技法（时序、缓动、编排），仓库中不包含上述影片的任何素材、画面或品牌资产。所有商标归各自所有者所有，上述公司与本项目无关联，亦未对本项目背书。”** 这不是“把大厂的库搬过来”，而是“看片拆手法、自己重写”。
- **逐卡来源只覆盖 38 张**：`references/shots/ATTRIBUTION.md` 开头写“2026-08 新增 48 张，2026-10 精简后现存 38 张”，逐卡来源映射也只有 38 张卡（[L1](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/shots/ATTRIBUTION.md#L1)、[L48](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/shots/ATTRIBUTION.md#L48)）；其余 86 张没有逐卡来源说明。
- **法律边界**：ATTRIBUTION 明确写“**所有实现均为从零重写**”“来源作品‘公开发布’**不等于**授予复刻或衍生的许可”，并对多个来源标注“**未获复刻许可**”（[L4](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/shots/ATTRIBUTION.md#L4)、[L15](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/shots/ATTRIBUTION.md#L15)、[L31–L39](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/shots/ATTRIBUTION.md#L31-L39)）。对商用用户，这是需要自己评估的风险，不是“开源就随便用”。

**结论**：说“150 个镜头样式、灵感来自大厂宣传片”是准确的；说“150 个大厂经典动效库”会让人误以为是大厂授权/原版素材库，属于营销化包装。

### 2. “自动分镜、自动写动效、自动配卡”：是 agent 工作流，不是产品功能

- **模式设计**：`SKILL.md` 把完整宣传片分成三种模式——直接用 Ink Press 模板、自主自由创作、共同创作（[L29–L53](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/SKILL.md#L29-L53)）。自主模式明确写“Agent 自主推进，不逐阶段等待确认”；共同模式则在产品简报、视觉方向、镜头映射、最终分镜处要求用户确认（[`references/guided-free-creation.md`](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/guided-free-creation.md)）。所以“自动”是**有条件**的：选自主模式才连续跑；选共同模式会停下来问。
- **没有内嵌模型**：我在仓库里搜 `opus` / `anthropic` / `openai` / `gemini` / `llm`，文档和代码里没有模型调用；外部服务调用主要是 Freesound 音效搜索和 Upload-Post 社交发布（另有 GitHub API 用于 Gallery 构建）。分镜/写动效/选卡全部由外部 agent 完成。仓库里也搜不到独立的“自动分镜”脚本——`grep 分镜` 只命中 Markdown 文档和部分 demo 的注释/文案。
- **分镜确实是流程的一部分**：`references/pipeline.md` 阶段 2 是“功能到镜头映射”（扫描 `references/shots/` 全部卡片的 frontmatter，为每项功能选首选/备选卡，[L115–L128](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/pipeline.md#L115-L128)）；阶段 3 是“分镜与制作放行”，要求写完整分镜表（镜头顺序、时长、页面状态、卡与变体、主动作、素材、字幕、转场、SFX，[L132–L144](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/pipeline.md#L132-L144)）。这是给 agent 的作业指导书，不是一段可执行的“分镜算法”。
- **第三方实测（C）**：IndieHackers 上一位用户 2026-10-18 的文章说，用 video-shotcraft + Opus 5.5 的完全自主模式，agent 自己产出了产品简报、视觉方向和逐镜头分镜，并把每个切点钉在音乐拍上（[原文](https://www.indiehackers.com/post/i-made-two-launch-videos-for-my-karmit-with-opus-5-5-one-with-a-video-skill-one-with-a-single-prompt-here-s-how-they-compare-84f4dded14)）。这说明“自动分镜”在能力上确实跑得通，但仍是**特定 agent + 特定模型**的实测，不是仓库自带的确定性功能。

**结论**：视频说“自动分镜/自动写动效”不算造谣，但它省略了主语——**是 Claude Code/Codex 在自动，不是 video-shotcraft 在自动**。没有 coding agent，这个仓库只是一套文档 + 代码素材。

### 3. 剪映草稿导出：真的，但“画面前分层”和“一键”都不准确

`references/jianying-export.md` 把能力边界写得很清楚：

| 层 | 剪映里的形态 | 可编辑度 |
|---|---|---|
| 镜头内动效（运镜/粒子/3D/逐元素编排） | **烘焙进底片** | 仅整段变速/调色 |
| 镜头边界 | 底片按镜头切段（同一文件不同 `source_timerange`） | 变速/重排/删减 |
| 屏幕空间字幕/解说 | 剪映原生文本轨 | 内容/字号/颜色全开 |
| SFX / BGM | 剪映音频轨（带音量） | 全开 |
| 用户点名的独立元素（logo/计数等） | **可选：画中画图层** | 位置/大小/透明度 |

（[`references/jianying-export.md` L19–L24](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/jianying-export.md#L19-L24)）

所以：

- **“字幕/音效独立轨”是真的**：字幕重建为原生文本轨（中英双语还会拆两轨），SFX/BGM 独立音轨。
- **“画面前分层”不是真的**：底片只有一条视频轨，按镜头切段；镜头内动效已经烘焙，不能像 AE 那样逐元素调。只有用户点名的独立元素可以走可选的画中画图层。
- **“一键导出”也不是**：`jianying-export/aifl_promo.py` 是 **Ink Press 模板片专用**脚本，时间线三张表逐条抄自 `template/src/aifl/Main.tsx`（[L1](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/jianying-export/aifl_promo.py#L1)）。换一个项目，要改三张表或另写脚本；这不是一个通用 CLI。
- **平台限制很硬**：Mac 剪映专业版 11.2 实测通过；Windows 版“按上游支持路径实现但未真机验证”（[L11–L13](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/jianying-export.md#L11-L13)）；剪映保存后单向加密，改完只能重导；新机器往往没有明文老草稿，`macify` 会明确报错，需要 `donor_draft`（[L161](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/jianying-export.md#L161)）；Mac 草稿含本机设备标识（`device_id`/`hard_disk_id`/`mac_address`），**不要直接分发给别人**（[L181](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/references/jianying-export.md#L181)，[`mac_draft.py` L1–L14](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/jianying-export/mac_draft.py#L1-L14)）。

**结论**：剪映导出是“真代码、真方法、作者真机验证过 Mac 11.2”，但它是**模板片/定制工程级别的导出方案**，不是“任意片子一键导剪映”，更没有“画面前景/背景分层”。

### 4. “便宜模型媲美 Opus 5.5”：仓库没有证据；型号本身是真的

- **仓库没有任何模型基准**：搜 `Opus` / `Anthropic` 为空；README 只写“为 Claude Code 和 Codex 调校”（[L84](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/README_CN.md#L84)），没有“便宜模型 vs Opus 5.5”的对比、成本表或评测集。
- **“Opus 5.5 型号名称与官方命名不符”这条判断是错的**：官方/云厂商文档确认 Claude Opus 5.5 存在——AWS Bedrock 模型卡标题就是 “Claude Opus 5.5”（[AWS 模型卡](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-opus-5-5.html)）；Anthropic News 有 “Introducing Claude Opus 5.5”（2026-09-22，[Newsroom](https://www.anthropic.com/news)）。所以不能拿“型号名不对”当疑点；真正要核的是**效果/成本对比**，而仓库没给。
- **外部旁证（C，非仓库证据）**：Post-Cutoff 转述作者 2026-09-25 的 X 演示，称 Opus 5.5 “made the whole 3:44 video from one sentence, including BGM music and sound-effect synthesis”，并称其为代际跃升（[Post-Cutoff](https://postcutoff.com/v/vincentwei-opus-5-5-one-sentence-video-x/)）。这条至少说明：**Opus 5.5 的基线很高**；当基座模型足够强时，skill 的边际价值更多在“稳定产出、可编辑、可复用工作流”，而不是“能不能做”。它不直接证明“便宜模型 + skill 能媲美 Opus 5.5”，但让这个说法更需要独立 A/B，而不是一句口号。

**结论**：不要因为“Opus 5.5”这个名字就怀疑视频造假；但“便宜模型媲美 Opus 5.5”目前没有任何仓库证据，属于视频单方表述。要用便宜模型，必须自己拿同一 brief 做 A/B（成片质量、返工次数、token/时间成本），仓库不提供这个保证。

### 5. “普通人也能做 / 发布会级 / 开源”：三个词都需要限定

- **“普通人”**：README 的环境要求是 Node/npm、ffmpeg/ffprobe、uv、puppeteer、Remotion 无头 Chrome（[L180–L189](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/README_CN.md#L180-L189)）；还要一个能执行 shell、读写文件的 coding agent（Claude Code/Codex），以及处理素材、渲染、逐帧验收的耐心。这不是“装个剪映”的门槛。
- **本次实测发现一个 README 没写的门槛**：在我的 macOS 13.7.8 上，`npx remotion still` 能出单帧；但 `npx remotion render --frames=0-30` 在音频探测阶段失败，Remotion 明确提示 “requires macOS 15 (Sequoia) or later”，`ffprobe` 因 `_AVCaptureDeviceTypeContinuityCamera` 符号缺失而 SIGABRT。模板 pin 的是 Remotion 4.0.484（[`template/package.json` L11–L14](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/template/package.json#L11-L14)）。也就是说：**macOS 13 用户可能连 1 秒带音频片段都渲不出来**，单帧能出只是“看起来能跑”。README 只写“已在 macOS 上测试”（[L189](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/README_CN.md#L189)），没有写 macOS 15 这个硬门槛。这是文档缺口，不是视频宣传点，但会直接影响“普通人能不能用”。
- **“发布会级”**：模板是 36.2s / 1085 帧 / 1920×1080，审美规则写得很细（镜头卡、参数、hold 帧预算、卡点、音效句式）。本次 still 的画面确实有“产品发布片”的质感；在线 Showcase 有 25 条投稿、23 位作者（其中 3 条是作者自带样片，22 条来自其他作者）。但“发布会级”没有客观阈值，也没有第三方质量评测；它是主观判断，不是可验证参数。
- **“开源”**：代码/文档 Apache-2.0，这部分是真的；但 Remotion 许可、Freesound/BGM 逐文件许可、Claude Code/Codex 订阅、渲染硬件和时间，都是成本。仓库自己提醒了 Remotion 许可（[L258](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/README_CN.md#L258)）；视频如果只说“开源免费”，是不完整的。

### 6. 维护与真实使用：热度高，但不是“独立质量认证”

- 截至 2026-11-23 12:xx CST：**22,145 stars / 2,040 forks**；创建于 2026-07-19；Apache-2.0；4 个 open issue；主作者 63 次提交，其他贡献者少量。热度是真实的，但 star 数不等于质量。
- 在线 Gallery 是活的：`GET https://vincentwei1021.github.io/video-shotcraft/api/library.json` 返回 124 卡/150 样式；Showcase 有 25 条投稿（3 条作者样片 + 22 条其他作者），说明确实有人用它出片。
- CI 有含金量，但不是全链路：`pr-checks.yml` 跑 tsc strict、vitest、Freesound 离线单测、每个 demo 的首帧冒烟渲染（[L172–L189](https://github.com/Vincentwei1021/video-shotcraft/blob/59f3e9b9e936ff2bce0e18446226d770a3f2f61f/.github/workflows/pr-checks.yml#L172-L189)）；**没有整片渲染、没有剪映真机链路、没有工作台交互的端到端测试**。剪映的 `smoke_test.py` 是手动跑的本机测试，不在 CI 里。
- 维护风险：主作者单人维护为主，近期 PR 有相当一部分是微信群/赞助/README 更新（#143–#154 等），不是核心代码；对“长期稳定”要有预期管理。

## 宣传疑点（按严重度）

1. **“大厂经典动效库”容易被误解为授权/原版库。** 实际是“研究大厂宣传片后从零重写的配方卡”；README 自己写了“无关联、未背书”，ATTRIBUTION 还标注了多个“未获复刻许可”的来源。商用前应做来源/法务评估，不要把“开源”当成“素材可随便用”。
2. **“150”混了卡和镜头。** 124 张卡 / 150 个镜头样式；视频说“150 个库”会让人以为是 150 张可复用卡。
3. **“自动”省略了主语。** 是 Claude Code/Codex 在自动，不是 skill 自带模型；没有 coding agent，它只是一套文档 + 素材。共同创作模式还会多次要求确认，不是全自动。
4. **“剪映画面前分层”不准确。** 真实情况是一条按镜头切段的底片 + 原生字幕轨 + SFX/BGM 轨 + 可选画中画；镜头内动效烘焙。Mac 11.2 实测、Windows 未验证、单向加密、新机器需 donor 草稿。
5. **“便宜模型媲美 Opus 5.5”没有仓库证据。** 仓库没有模型基准；Opus 5.5 是真实型号；作者自己的 X 演示反而说明 Opus 5.5 基线很高。要用便宜模型，必须自己做 A/B。
6. **“普通人/发布会级/开源”是营销词。** 需要 Node/ffmpeg/uv/puppeteer/Chrome + coding agent + macOS 15（本次实测）/Linux；Remotion 商用可能收费；时间成本不低。
7. **“开源”只覆盖代码/文档。** 素材、音效、BGM、Remotion、模型订阅各有各的许可/成本；视频如果只说“开源”，是不完整的。

## 本次实测记录（可复现）

**环境**：macOS 13.7.8（22H730），Node v24.15.0，npm 11.12.1，ffmpeg N-124654。
**上游**：`git clone https://github.com/Vincentwei1021/video-shotcraft`，HEAD `59f3e9b`。

```bash
cd video-shotcraft/template
npm ci
npx remotion still src/index.ts AiflPromo /tmp/vsc-frame150.png --frame=150
# 成功：1920×1080 PNG，1,156,832 bytes（本报告配图即此帧）

npx remotion render src/index.ts AiflPromo /tmp/vsc-clip.mp4 --frames=0-30 --concurrency=1
# 失败：Remotion 4.0.484 requires macOS 15；ffprobe SIGABRT
# Symbol not found: _AVCaptureDeviceTypeContinuityCamera
```

**结论**：模板代码能编译、能出单帧；但“带音频的成片渲染”在本机受 macOS 版本限制，未能完成。
**未测**：整片 1085 帧渲染、剪映真机导入/编辑、Workbench 交互、Freesound 下载、页面抓取脚本。
**为什么没继续**：这些需要 macOS 15/Linux + 剪映客户端 + 真实产品页面，超出“读仓库核验”的范围；继续跑也不会改变核心结论，只会增加环境噪声。

## 值不值得用：分人给建议

| 你是谁 | 建议 |
|---|---|
| **有 Claude Code/Codex、会 Node 的开发者/技术自媒体** | **值得试**。先用 Ink Press 模板跑一支 36.2s 的片子，熟悉 `npm ci` → `remotion still` → 替换截图/文案 → 整片渲染的链路；配方卡和 `template/` 是真资产。注意 macOS 15/Linux，别在 macOS 13 上硬扛。 |
| **非技术用户/只想“一句话出片”** | **现在还不适合**。没有独立 App/GUI 生成入口；要装环境、给 agent 文件权限、处理渲染错误。等一个封装好的产品/服务，或者直接用剪辑师 + 模板。 |
| **商用/品牌方** | **先法务再动手**。检查配方卡来源（ATTRIBUTION 的“未获复刻许可”）、替换模板里的演示截图/数据、确认 Remotion 商用许可、剪映导出在目标平台实测。不要直接拿作者样片里的品牌/数据商用。 |
| **想用便宜模型替代 Opus 5.5** | **没有现成答案**。仓库没有基准；建议用同一 brief、同一素材，做“便宜模型 + skill” vs “Opus 5.5 + skill/单 prompt”的 A/B，记录成片质量、返工次数、token/时间成本。不要相信“媲美”这种没有样本量的说法。 |
| **只想要 150 个动效灵感** | **Gallery 值得逛**。150 条样片 + 124 张卡，分类/参数/踩坑写得细；但注意“大厂”是研究来源，不是授权库。 |

## 局限与待核实

- **没有视频原片/链接**：只能按你给的摘要核；如果原片说的是“150 个镜头”而不是“150 张卡”，或者“自动配卡”原意是“自动配乐卡点”，结论里的措辞要相应调整。
- **只测了一台机器、一个 still 帧**：没有整片渲染、没有剪映真机、没有 Workbench 交互；macOS 13 的渲染失败是环境限制，不代表仓库在 macOS 15/Linux 上不行。
- **外部证据是 C 级**：IndieHackers、Post-Cutoff 都是第三方转述/个人实测，不是同行评审或受控实验；引用它们是为了说明“有这种使用方式/作者有过这种表述”，不是当作仓库事实。
- **数字是时点值**：star/fork/issue/Showcase 数会变；本报告写于 2026-11-23。
- **“未发现”≠“不存在”**：我在仓库里没搜到 Opus/Anthropic/LLM 调用、没搜到独立分镜脚本；这只能说明“在这个 commit 的仓库里没有”，不能排除作者在其他仓库/私域有别的实现。

## 附录：关键链接与核验命令

**仓库/在线**
- 仓库：https://github.com/Vincentwei1021/video-shotcraft
- 本次 commit：https://github.com/Vincentwei1021/video-shotcraft/commit/59f3e9b9e936ff2bce0e18446226d770a3f2f61f
- Gallery：https://vincentwei1021.github.io/video-shotcraft/
- `library.json`：https://vincentwei1021.github.io/video-shotcraft/api/library.json
- `showcase.json`：https://vincentwei1021.github.io/video-shotcraft/api/showcase.json

**关键文件**
- `README_CN.md`（124/150、环境、许可、致谢）
- `SKILL.md`（三种模式、工作流、验收）
- `references/pipeline.md`（8 阶段）
- `references/jianying-export.md`（剪映分层/平台限制）
- `references/shots/ATTRIBUTION.md`（38 张来源、授权边界）
- `jianying-export/aifl_promo.py` / `mac_draft.py` / `windows_draft.py`
- `template/package.json`（Remotion 4.0.484）

**模型**
- AWS Bedrock Claude Opus 5.5 模型卡：https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-opus-5-5.html
- Anthropic Newsroom：https://www.anthropic.com/news

**外部旁证（C）**
- IndieHackers 双版本对比：https://www.indiehackers.com/post/i-made-two-launch-videos-for-my-karmit-with-opus-5-5-one-with-a-video-skill-one-with-a-single-prompt-here-s-how-they-compare-84f4dded14
- Post-Cutoff 对作者 X 演示的转述：https://postcutoff.com/v/vincentwei-opus-5-5-one-sentence-video-x/

**快速核验命令**

```bash
# 仓库元数据
gh api repos/Vincentwei1021/video-shotcraft \
  --jq '{stargazers_count,forks_count,open_issues_count,created_at,license:.license.spdx_id}'

# 124 卡 / 150 样式
curl -s https://vincentwei1021.github.io/video-shotcraft/api/library.json \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["stats"])'

# 25 条 Showcase
curl -s https://vincentwei1021.github.io/video-shotcraft/api/showcase.json \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d["items"]))'

# 复现单帧
git clone https://github.com/Vincentwei1021/video-shotcraft /tmp/video-shotcraft
cd /tmp/video-shotcraft/template && npm ci
npx remotion still src/index.ts AiflPromo /tmp/frame150.png --frame=150
```

---

**最后一句**：这条视频值得看，但把它当“普通人一键出片的开源神器”会失望；把它当“给 Claude Code/Codex 的一套高质量产品片制作方法论 + 配方库 + 模板/工作台”会更接近事实。先用模板跑通一支，再决定要不要投入。
