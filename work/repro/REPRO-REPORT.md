# 复现与修复报告：停止录制即整体退出（工单 6bc7e837b928）

日期：2026-11-15（Asia/Shanghai）。本轮按「真机复现 + 崩溃证据 + 抽帧验证成片」闭环，不再只靠单测。

## 1. 结论（一句话）

停止录制时应用「直接退出」的根因是**两处独立的缺陷叠加**，全部在本轮真机复现、定位并修复；
修复后真机录制（含摄像头画中画）保存成功、应用存活、编辑器回到前台，抽帧确认成片为
正常视频（1680×1050 VP9+Opus，约 26fps，画中画已烘焙进画面）。

## 2. 复现矩阵（真机，/Applications/FocuSee Clone.app）

| 轮次 | 构建 | 摄像头 | 结果 |
| --- | --- | --- | --- |
| R1 | 修复前（git abe059e == 安装包） | 关 | 复现：停止后 `__stopPhase` 卡死在 teardown-start，**保存永不开始**，25s 内无项目落盘（`project-saved FAIL none`），主进程虽未死但**所有窗口隐藏 = 用户视角的"直接退出"** |
| R2 | 修复前 | 开（用户路径） | 复现：同一死亡链 + 4 条控制台错误（见 §3）；PiP 在录制中已烘焙（pipDrawn=113/113）但保存失败 |
| R3 | 修复后 | 关 | 通过：`save-state=done`，项目落盘（3.31s），**零控制台错误**，应用存活，编辑器窗口回到前台（System Events 确认） |
| R4 | 修复后 | 开（用户路径） | 通过：同上（3.66s），camera.webm+recording.webm+project.json 齐全，应用存活 |

证据：`work/repro/evidence/r1..r4-*.log`、`r1..r4-report-*.json`（本机工单目录）。

## 3. 根因（互相独立，全部属实）

### 根因 A：renderer 引用了不存在的主进程变量 → 停止即"消失"（f616f88 引入）

`finishRecording`（renderer/app.js）的 teardown 里出现了 `mainWindow`——该标识符只在主进程
存在。真机 R1/R2 控制台证据：

```
[record] teardown error ReferenceError: mainWindow is not defined
Uncaught (in promise) ReferenceError: mainWindow is not defined
```

try 与 catch 里各写了一次，**两次都抛**→ save-started 与 saveRecordingFrom 永不执行
（录制必然丢失），且"把编辑器带回前台"的动作从未发生 → 悬浮条隐藏后**编辑器也不再显示**，
应用看起来"直接退出"（进程其实还活着）。git blame：f616f88（2026-11-15 04:21）从 main.js
抄到 renderer 的两行。

### 根因 B：recorder 事件回调读到已置空的 S.recording / 传错对象 → 保存链本身也是坏的

- `camRec.ondataavailable` 读 `S.recording.camChunks`，而 finishRecording 在 flush 前已把
  `S.recording = null` → `Cannot read properties of null (reading 'camChunks')`，摄像头分段丢失；
- `recorder.onstop = () => saveRecordingFrom(recorder)` 把 **recorder 本身**当 rec 传入 →
  `Cannot set properties of undefined (setting 'onstop')`，保存第一步就崩；即便 A 修好，
  这条也会让真实保存路径失效并抢先占掉 saved 防重入。

### 根因 C（历史崩溃）：跨窗口 executeJavaScript 原生崩溃（04:03 SIGSEGV）

崩溃报告 `Electron-2026-11-15-040339.ips`（com.focuseeclone.app，EXC_BAD_ACCESS
KERN_INVALID_ADDRESS 0x8）：主进程在悬浮条页面上调 `executeJavaScript`（inspector 桥）
时原生崩溃。上一轮 abe059e 声称"移除主进程侧调用"，但 **实际 diff 只改了 control.js，
main.js 里的 `stopPillCameraPreview()`（teardown 时的跨窗口 executeJavaScript）原样保留**
——本轮 git 证据确认（abe059e diffstat 只有 renderer/control.js）。该调用连同
`control:attachCameraPreview`、e2e 停止点击三处全部改为**事件驱动（ipcRenderer）+ 悬浮条
自身上下文执行**，main.js 中不再有任何指向悬浮条页面的 executeJavaScript。

### 附带核实：用户旧录像全是"静帧"

用户 02:07–03:55 保存的 4 个项目，`recording.webm` 解码仅 2–3 帧（9s+ 时长）——
静帧幻灯片。这些全部产生于 f616f88（隐藏窗口节流禁用）**之前**的构建；本轮修复后 R4
实测 96 帧/3.7s ≈ 26fps。属于上一轮已修、本轮真机复核确认的问题。

## 4. 修复内容（本 PR）

- `renderer/app.js`：删除两处 `mainWindow` 引用（编辑器回前台由主进程 hideControl 负责）；
  recorder/camera 事件回调一律捕获**局部 rec 引用**；onstop 只发 flush 信号，
  保存统一由 finishRecording 驱动（带 1.5s bounded flush 等待）。
- `main.js`：删除 `stopPillCameraPreview()`；`capture:hideControl` 不再触碰悬浮条页面
  （悬浮条 visibilitychange/pagehide 自停预览）；`control:attachCameraPreview` 改为发
  `control:attachCamera` 事件；e2e 桥探活改 `control:pillReady` ACK、停止点击改
  `control:stopSignal` 事件；新增 `--e2e-rec-hold`（真机观察模式，不烧掉现场）。
- `preload.js` / `renderer/control.js`：新增上述事件通道；悬浮条在自己的上下文完成
  相机预览 attach（onState withCamera 兜底再驱动一次，防早到信号丢失）。
- `test/stop-flow.test.mjs`（新增 6 条 tripwire）：renderer 不得引用 `mainWindow`；
  事件回调必须用局部 rec；onstop 不得直接驱动保存；main.js 不得对悬浮条页面
  executeJavaScript；事件通道齐备；hold 模式存在。单测 26/26（原 20 + 新 6）。

## 5. 抽帧验证成片（R4，含摄像头）

- `recording.webm`：VP9 1680×1050 + Opus，抽帧 4 张全部为真实桌面内容；
- 画中画：按悬浮条位置（顶部居中）烘焙进画面，裁剪区可见摄像头内容叠加于屏幕之上
  （本机凌晨环境光暗，画面为暗室+镜头环，属摄像头真实输入）；
- `camera.webm` 独立保存成功，可在编辑器内重排版；
- 帧文件（本机，不入库）：`work/repro/frames/`（r4_*.png、pip_topcenter.png、montage.png）。

## 6. 依赖说明

本分支为 PR #32（focusee-clone 原型）之上的续修，包含其全部提交（尚未合并）。
合并顺序：先 #32 或直接合并本 PR 均可（内容相同+本修复）。

## 7. 交付状态

- 安装包 `/Applications/FocuSee Clone.app` 已就地更新为修复版（仅 Resources/app JS，
  主可执行与授权不变），真机 R3/R4 即对该安装包验证；
- 用户的正常实例已重新打开（其历史项目完整保留）。
