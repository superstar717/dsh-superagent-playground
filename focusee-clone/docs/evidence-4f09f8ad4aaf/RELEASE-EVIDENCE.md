# 证据：录制结束后资源未释放 → 二次录制卡（工单 4f09f8ad4aaf）

日期：2026-11-22 00:05–00:50（Asia/Shanghai）。机器：2017 MacBook Pro（Intel i7 4C/8T + 16GB），
macOS 26.x，Electron 45.2.2。本目录全部数据由 `work/perf/measure-two-takes.sh` 真机采集
（打包应用经 LaunchServices 启动，真实屏幕+摄像头两段录制，每段 8s，`--e2e-rec-hold` 停录后
继续采样 50s 空闲窗），CPU 为 top 单核百分比。

## 1. 用户实例取证（装机版 /Applications/FocuSee Clone.app，工单开始时正在运行）

时间线（projects 目录 mtime + VDCAssistant 日志，见 `live-instance/vdcaassistant-user-instance-timeline.txt`）：

| 时间 | 事件 |
| --- | --- |
| 23:17:58 | 用户第 1 段录制起流（StartStream，client 25035） |
| 23:27:36 | 第 1 段停录，相机正常释放（StopStream，17345 帧）——**停录路径相机释放本身是好的** |
| 00:00:22 | 第 2 段录制起流 |
| ~00:00:59 | 第 2 段项目落盘（projects/rec-mwqlhc8l mtime 00:00），用户 00:02 反馈「录第二个视频非常卡」 |
| 00:12:36 | **相机仍在推流（21987 帧已送）**，直到本工单把该实例温和退出才 StopStream——停录后相机被白拖 12 分钟 |

该实例退出前的 24s CPU 采样（`live-instance/gpu-burn-sample-pre-fix.txt`，00:08–00:10，
12 个 top 帧，应用全程空闲）：

| 进程 | 均值 CPU | 峰值 |
| --- | --- | --- |
| GPU 进程 | **23.8%** | 28.8% |
| 编辑器渲染进程 | 5.2% | 6.1% |
| video_capture 服务 | 3.3% | 4.0% |
| 合计（常烧） | **≈0.33 核** | |

即：用户录完第 2 段后，应用「空闲」状态下持续烧约 1/3 个核；第 2 段正是在第 1 段遗留负载
之上录的（用户体感「非常卡」）。自 13:19 启动至 00:08，GPU 进程累计 29:33 CPU 分钟、
编辑器渲染进程累计 27:35 CPU 分钟。

## 2. 根因（代码级，三处，均在摄像头画中画路径）

1. **bake 合成循环永不停止（主犯，对应空闲 GPU 高烧）**
   `renderer/app.js`：帧循环句柄存在局部变量 `bakeRaf` 里，`finishRecording` 清理的却是
   `rec.bakeRaf`（从未被赋值）→ 开摄像头录制结束后，30fps 全分辨率 `drawImage` 合成 +
   `bakeCanvas.captureStream(30)` 永不停止。渲染进程持续合成、GPU 进程持续吃帧——
   正是取证里 GPU 23.8% 空闲高烧的来源，且每多录一段多叠一个循环（越录越卡）。
2. **预览气泡可在「无活动录制」时抓相机，且无人停止（对应相机被白拖）**
   `renderer/cam-preview.js`：`attachCameraPreview` 无「take 是否活动」门控；
   `did-finish-load` replay / 晚到的 `control:attachCamera` 都会在 take 结束后重新
   `getUserMedia`，而此时窗口已隐藏，visibilitychange 不再触发，无人调用 stop——
   与上一工单实测的「取消后 ~8s 重取、占用 45 分钟」同类。本机 00:00:22→00:12:36 的
   12 分钟拖住是同类的另一形态：`getUserMedia` 握手挂起期间 take 结束，晚到的流在
   隐藏窗口里挂上后无人停止。
3. **拆除只靠「窗口隐藏」这一间接信号**：主进程没有显式 take 结束事件，页面错过
   visibilitychange 就漏。replay 缓存 `lastControlInfo` 也不随 take 结束而清空。

## 3. 修复（对应三处根因）

- `app.js`：句柄改存 `rec.bakeTimer/rec.recordSource/rec.bakeEls`；新增
  `releaseTakeCapture()` 在 teardown 起点立即停帧循环、清 video 元素 srcObject、
  停 bake captureStream 轨道；flush 完成后立即停设备轨道（900ms 定时器降级为兜底）；
  +1.5s 全量清扫并发布 `window.__lastTakeRelease`（liveTracks 计数）。
- `cam-preview.js`：`attachCameraPreview` 双重门控——await 前检查 take 活动状态，
  await 后（握手可能横跨 take 结束）再查一次并立即释放；显式 `takeEnded` 事件把
  take 状态归零（startedAt=0/stopped=true），此后任何 replay/可见性变化都无法复活采集；
  页面每次 attach/stop 变化向主进程推送 `{attached, startedAt, tracksLive}`。
- `main.js`：`recordingActive` 贯穿 showControl→hideControl/cancel；`endTakeOnPillPages()`
  在 hide/cancel 时向悬浮条+气泡页发显式 `takeEnded` 并清空 replay 缓存；
  相机 attach replay 以 `recordingActive` 为门。e2e 新增四条释放断言：
  `bake-loop-stopped` / `tracks-released` / `preview-released` /
  `preview-still-released`（停录 5s 后仍须为释放态），保存与取消两条路径都跑。

## 4. 真机 A/B（同机同参数，两段 8s 摄像头录制，全部 ALL_OK）

窗口均值（单核百分比；p50 括注）：

| 窗口 | BEFORE GPU | AFTER GPU | BEFORE 编辑器 | AFTER 编辑器 | BEFORE 相机 | AFTER 相机 |
| --- | --- | --- | --- | --- | --- | --- |
| take1 录制中 | 51.6 | 45.9 | 19.9 | 18.5 | 4.7 | 4.5 |
| 两段之间 | 63.8 | **23.0** | 18.2 | 8.8 | 5.4 | 4.2 |
| take2 录制中 | 61.9 | 52.3 | 20.0 | 21.7 | 4.9 | 4.4 |
| **停录后空闲 50s** | **22.4**（p50 21.6，max 35.6） | **1.8**（p50 1.7，max 2.5） | 2.2 | 1.0 | 0.1 | **0.0** |

- **空闲烧核：GPU 22.4% → 1.8%（−92%）**，与用户实例取证（23.8%）同量级同形态；
  编辑器渲染进程 2.2% → 1.0%；相机 0.1% → 0。
- 最终代码确认轮（`after-fix2/`，与提交代码逐字一致）复测同样成立：
  空闲 GPU **1.5%**（p50 1.5，max 1.7）、编辑器 0.9%、相机 0.0，四条释放断言两段全绿。
- 「两段之间」GPU 63.8% → 23.0%：take1 结束即停合成，take2 不再叠在遗留负载上——
  「第二个视频卡」的直接来源被移除。录制中的负载（bake 合成本身）保持原样，属于
  录制必需成本（上一工单已单独量化过其优化空间）。
- 数据：`baseline-pre-fix2/`（修复前，含修复前采样器口径问题的第一轮
  baseline-pre-fix 仅留档）、`after-fix/`、`after-fix2/`（最终代码确认轮）。

## 5. 用户侧最终验证（修复包装入 /Applications 并重启应用，00:35 采样）

| 指标（应用空闲、窗口可见） | 修复前实例（00:08） | 修复后实例（00:35） |
| --- | --- | --- |
| GPU 进程 | 23.8% 均值 | **1.3% 均值** |
| 编辑器渲染进程 | 5.2% | 2.3% |
| video_capture 服务 | 3.3%（相机被占） | **无此进程** |
| 空闲合计 | ≈0.32 核 | **≈0.04 核** |

样本：`live-instance/gpu-after-fix-relaunch.txt`（15 帧 top，两轮一致）。
旧包备份：`/tmp/FocuSee Clone-prev-20261122.app`。

## 6. 局限（如实）

- AFTER 主表（after-fix 轮）运行的包比最终提交少两行语义等价改动（pagehide 包装、
  getUserMedia 后二次校验）——该两行不影响本轮测得的 bake 泄漏数字；最终代码的
  `after-fix2/` 确认轮四条释放断言 + 空闲窗复测同为全绿（数值见该目录 summary.json）。
- 用户实例的 12 分钟相机拖住的具体复活向量无法在其旧包上直接插桩证实（不修改用户
  运行中的进程）；修复按「切断该类全部复活路径」处理并用 e2e 断言兜住。
- 单核百分比对整机的影响按 8 线程折算：0.33 核常烧 ≈ 系统可用算力的 ~4%，但集中在
  GPU/渲染路径，与录制负载叠加时表现为可感知的卡顿。

## 7. fps 30→15（用户 2026-11-22 00:46 拍板「同意降低 fps」后落地）

只改开摄像头画中画的 bake 合成路径（`app.js` bake 循环与 captureStream 30→15，
不开摄像头的录制不变）。真机复测（`fps15-approved/`，同参数两段 8s 摄像头录制，
ALL_OK、四条释放断言全绿）：

| 窗口（单核%） | 30fps GPU | 15fps GPU | 30fps 编辑器 | 15fps 编辑器 |
| --- | --- | --- | --- | --- |
| take1 录制中 | 46.3 | **27.7**（−40%） | 19.4 | 14.5 |
| take2 录制中 | 38.2 | **24.2**（−37%） | 12.1 | 12.8 |
| 停录后空闲 | 1.5 | 1.6（不变） | 0.9 | 0.9 |

成片帧率实测 `r_frame_rate = 91/6 ≈ 15.2`（`fps15-approved/actual-framerate.txt`），
编码仍为 h264 Baseline。与上一工单合成基准（17.1%→8.9%）方向一致。

## 8. 复现

```sh
cd focusee-clone && ./scripts/package-app.sh
bash ../work/perf/measure-two-takes.sh <label> "$PWD/build/FocuSee Clone.app" 8000
python3 ../work/perf/summarize-two-takes.py ../work/perf/runs/<label>   # 脚本内已自动跑
```
