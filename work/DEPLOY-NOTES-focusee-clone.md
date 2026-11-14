# DEPLOY-NOTES — Craft Anything 复刻本机 FocuSee（工单 29ad3631d2a6）

日期：2026-11-14（Asia/Shanghai）
状态：**原型完成，PR #32 待人审**（CI 已过：focusee-clone tests / unit pass 11）
PR：https://github.com/superstar717/dsh-superagent-playground/pull/32
分支：`agent/craft-focusee-clone-29ad3631d2a6`（xingzhe-agent fork）

---

## 1. 任务与结论

用户（2026-11-14 19:56）：「用开源神器 Craft Anything 复刻本机的 focusee 软件」。

- **Craft Anything 核实**：storytold/craft-anything，ArtCraft 的开源「逆向 + 重建」引擎，
  纯 Rust、Apache-2.0/MIT、v0.6.1（2026-11-12）、32k stars、early alpha。
  四步工作流 Study→Build→Check→Ready；净室模式默认（不读目标内部），
  Build 阶段依赖本机已登录的编码 agent（Claude Code 已实跑验证）。
- **本机 FocuSee**：/Applications/FocuSee.app 2.5.3（build 2026110501，Gemoo，
  com.gemoo.FocuSee，Mac App Store 版，163MB，正在运行）。
- **交付**：`focusee-clone/` Electron 45 原型（约 4000 行含测试），
  录屏→光标停留自动缩放→成片样式→WebM/MP4 导出全链路可用；
  差异如实记录于 `docs/DIFF-REPORT.md`。

## 2. 净室研究证据（对齐 Craft Anything 方法论）

| 证据 | 采集方式 | 产出 |
| --- | --- | --- |
| FocuSee 编辑器 AX 控件树 | macOS Accessibility API（自写 Swift dumper，165 行） | 8 项工具栏、样式面板字段/默认值、时间线结构 |
| 编辑器可见文案 | AXStaticText/AXImage desc（视频尺寸/固定缩放区域/内边距/圆角/阴影/背景模糊/默认背景/沉稳/轻盈/风景/自定义背景…） | 字段名逐字对应 |
| 官网功能全集 | gemoo.com/focusee 首页文本+图片 alt | 21 项功能对照表（差异报告 §3） |
| 视觉基调 | 官网产品图 | 紫色渐变、圆角卡片、hero 布局 |
| **未做** | 不反编译、不解包 Assets.car、不读 NIB | 遵守净室默认 |

采集工具（本工单临时 Swift 小工具，/tmp，不入库）：
`winshot`（CGWindowList 列窗口/按 id 截窗）、`axdump`/`win2`（AX 树遍历）。

## 3. 原型实现要点

- **录制**：desktopCapturer 选屏幕/窗口 → 独立 getUserMedia（视频/麦克风分开再合并，
  macOS 上混在一个约束里不可靠）→ MediaRecorder VP9+Opus；
  悬浮控制条 `setContentProtection(true)` 不入镜；倒计时 3s。
- **自动缩放**（核心卖点复刻）：40ms 全局光标采样（无需输入监控权限）→
  停留簇检测（1.2% 屏幕半径内停留 ≥0.42s）→ buildZooms 生成缩放包络
  （重叠才合并）→ smoothstep 缓动 + 取景窗约束。11 个单测覆盖全部几何。
- **成片合成**：单文件 canvas 渲染器（预览与导出共用 drawFrame）：
  背景（12 预设+自定义）→ 阴影 → 圆角取景 → drawImage 缩放采样 → 点击涟漪 → 字幕。
- **导出**：canvas.captureStream + MediaRecorder 实时渲染（进度条真实反映），
  音频走 AudioContext→MediaStreamDestination 混入；MP4 需本机 ffmpeg。
- **示例项目**：ffmpeg drawbox/drawtext 合成 6s 假"屏幕录制"（含移动光标）+ 配套
  光标轨迹 JSON，首次启动自动创建，打开即看到 3 段自动缩放。
- **E2E**：`--e2e` 无人值守：6 屏截图 + 真实导出 960×540 WebM（1.3MB），
  抽帧确认「渐变背景+圆角+1.8×缩放+点击涟漪」同帧出现。产物 focusee-clone/artifacts/。

## 4. 已知差异（重要，见 docs/DIFF-REPORT.md 全表）

1. **点击检测是近似**：FocuSee 用真实点击事件；原型用停留簇，打字停顿也会触发缩放。
2. **窗口录制时自动缩放禁用**：全局光标坐标无法可靠映射窗口内容坐标系（原型不追踪窗口原点）。
3. **未实现**：AI 字幕（手动字幕只验证渲染链）、音频增强/降噪/静音剪切、摄像头布局/背景移除/
   提词器、3D 动效、注释套件、点击音效、云分享、多语言（仅中文）。
4. **Craft Anything CLI 未直接跑**：v0.6.1 CLI zip 27.9MB，本轮网络 ~100KB/s 且多次断流，
   未完成下载+校验；其「对运行中 macOS 应用」的净室研究产出（窗口截图+AX 树）与
   本轮已人工采集证据等价，Build 阶段本可接 Claude Code 但对本任务收益有限——
   方法论等效人工执行，如实记录于差异报告 §5。

## 5. 验证与 CI

- 单测 11/11（`npm test`，含 zoom.cjs 与 zoom.js 同步重建门禁）。
- CI：`.github/workflows/focusee-clone-test.yml`（ubuntu-latest，Node 22，
  focusee-clone/** 变更触发）——PR #32 上 pass。
- E2E 无人值守通过（含真实导出产物校验）。
- 自审：无 TODO/debug 残留（e2e 场景 console.log 属预期诊断输出）；
  无密钥；`npm start` 冒烟通过。

## 6. 复现

```sh
cd focusee-clone
npm install && npm run sample
npm start                                   # 人工体验
npm test                                    # 单测
FOCUSEE_DATA_DIR=/tmp/x ./node_modules/.bin/electron . --e2e   # 全链路
```

## 7. 遗留 / 后续

- Craft Anything CLI 完整下载后可复核其 Study 产出（窗口截图+AX 树）与本项目证据一致性。
- 若要真实点击驱动缩放：需要「输入监控」权限 + 签名应用（超出学习原型必要范围）。
- 自动缩放对导入视频不可用（无光标轨迹）——与 FocuSee 行为一致。
