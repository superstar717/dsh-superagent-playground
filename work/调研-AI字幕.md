# 调研：FocuSee「AI 字幕」功能定义与复刻可行性（工单 cf5489894391）

日期：2026-11-15（Asia/Shanghai）。来源消息：用户问「其中有一个AI字幕的功能 是什么」。

## 一、官方定义（已核官网用户指南，抓取于 2026-11-15）

来源：[AI字幕（中文指南）](https://focusee.imobie.net/guide/ai-subtitles.htm)、
[AI Subtitles（英文指南）](https://focusee.imobie.com/guide/ai-subtitles.htm)、
[Captions（本地模型免费档指南）](https://focusee.imobie.com/guide/auto-captions.htm)。

FocuSee 的 AI 字幕 = 在录屏编辑器里，**根据视频中的语音讲解自动生成带时间轴的字幕**的功能：

- **双引擎**：
  - 高级模型（Advanced Model）：云端 AI，准确率更高、语言更广，**计费 1 积分/分钟**；
  - 本地模型（Local Model）：**免费、本机推理**，分 Nano / Basic / Pro 三档精度，
    支持 10 种语言（英/法/德/西/意/日/简中/繁中/韩/葡）。
- **音频源**：麦克风、系统声音或耳机。
- **交互流程**：编辑页左侧「AI字幕/Captions」→ 选引擎 → 选语言（自动识别或指定）→ 生成 →
  左侧逐句列出、可逐句改文本 → 样式设置（字号/位置/间距）→ 可开关/重新生成 → 预览导出。

## 二、复刻版现状（本机 focusee-clone，分支 agent/ai-subtitle-feature-cf5489894391）

- 字幕**渲染链已实现**：`renderer/render.js` drawFrame 按 `{start,end,text}` 找当前句，
  画半透明底 + 居中文字，预览与导出共用（固定样式）。
- 手动添加字幕入口已有（字幕 tab，从播放头起持续 2.4s）。
- **未实现**（界面文案自述，app.js L343/L489）：AI 字幕识别、字幕样式/位置编辑、跟随音频自动断句。
- 用户已把复刻版装成 `/Applications/FocuSee Clone.app` 在用。

## 三、实现评估：可复用本机 SenseVoice 管线，结论=可实现，工作量小

对应关系：FocuSee 的「本地模型免费档」≈ 我们要做的这一档（本机推理、免费、离线）；
其「高级模型」是付费云服务，复刻不涉及。

| 环节 | 本机已有 | 需要补的 |
| --- | --- | --- |
| ASR 引擎 | SenseVoice-small + fsmn-vad（`~/.local/sensevoice-asr/`，RTF≈0.12 实测，中英准确率实测优于 whisper-base） | 转写脚本目前只出全文纯文本，**无句级时间戳**——需小扩展：fsmn-vad 分段 → 逐段转写 → 输出 `{start,end,text}` 列表（标准 funasr 用法，约 30–50 行） |
| 音轨提取 | `/usr/local/bin/ffmpeg` 已装；项目视频为 webm/mp4 文件 | ffmpeg 抽音轨 → 16k wav（一条命令） |
| 进程编排 | main.js 已有 ffmpeg 调用先例 | 主进程 IPC：抽音轨→调 venv python→回读 JSON→写 `project.captions` |
| 前端 | 字幕 tab + 渲染链 | 「AI 生成」按钮 + 进度 + 逐句可编辑列表（对齐 FocuSee 交互） |
| 样式编辑 | 无（固定样式） | 可选二期（字号/位置/间距） |

**如实差异**：SenseVoice 支持 5 种语言（中/英/日/韩/粤，auto 检测），比 FocuSee 本地模型的 10 种窄；
但用户主场景中文，实测准确率更强。环境依赖：venv 在
`~/src/compare-ocr-models-8ca7b0b3fd79/test/venv`（勿删），模型缓存 `~/.cache/modelscope` 离线可用；
独立 app 打包若要脱离本机环境需把依赖/模型打进包（成本高，建议先按本机依赖实现）。

## 四、结论

- 「AI 字幕」= 语音→自动生成时间轴字幕（云端计费档 + 本机免费档双引擎），交互含逐句编辑与样式设置。
- 复刻版做的是「本机免费档」同级能力：SenseVoice 出句级时间戳 → 现有字幕渲染链直接吃。
- 评估为实现可行、改动集中在转写脚本扩展 + 一条 IPC + 字幕 tab 前端；是否动手等用户拍板。
