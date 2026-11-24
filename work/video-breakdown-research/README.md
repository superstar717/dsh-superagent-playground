# 视频拆解原型（CPU，本机可落地）

配套调研报告：[调研报告.md](调研报告.md)

## 文件

- `video_breakdown.py`：主入口。硬切检测（PySceneDetect，缺失时 ffmpeg 兜底）+ 1fps 画面换版扫描 + 关键帧 + 口播分段 + Markdown/JSON 报告。
- `asr_segments.py`：SenseVoice-small + fsmn-vad 句级转写，输出带时间戳的 JSON（需要 funasr/torch/soundfile 环境）。

## 快速开始

```bash
# 1) 环境：复用系统/conda 的 cv2、numpy，只装 scenedetect
python3 -m venv --system-site-packages .venv-scene
.venv-scene/bin/pip install scenedetect

# 2) 拆解（ASR 环境可用时自动调用；没有就只出画面/镜头层）
.venv-scene/bin/python video_breakdown.py input.mp4 -o out

# 3) 口播环境不在默认位置时，显式指定
SENSEVOICE_PY=/path/to/python-with-funasr \
  .venv-scene/bin/python video_breakdown.py input.mp4 -o out
```

输出：`out/report.md`、`out/breakdown.json`、`out/keyframes/*.jpg`、`out/asr.json`（如启用 ASR）。

`demo/` 是用 ffmpeg 合成的 12s 四段纯色视频生成的无隐私样例，可直接对照输出格式。

## 已验证范围

- 合成 4 段硬切视频：4/4 切点正确。
- 竖屏动效（无硬切）：1fps 换版扫描得到与人工看帧一致的段落边界。
- 真人口播（无硬切）：自动跳过画面扫描，避免每 2 秒一个假段落。
- 9 分钟 576×1024 HEVC 视频：硬切检测可用（约 76s）。

未验证：TransNetV2/OmniShotCut 等神经镜头模型的精度与速度；OCR/景别/运镜分类不在本脚本范围。

## 注意

- 真实视频、转写文本、关键帧可能包含隐私/商业内容；提交到公开仓库前先脱敏。
- ASR 文本未经校对；引用前核对专有名词。
- 画面段落是启发式分段（±1s），不是镜头语言级分镜。
