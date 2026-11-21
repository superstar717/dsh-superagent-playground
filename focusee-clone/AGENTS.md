# focusee-clone 项目现状（给下一个会话）

最后更新：2026-11-15。项目复盘全文：`../work/复盘-focusee-clone.md`；功能差异：`../docs/DIFF-REPORT.md`。

## 当前结论

- PR #32–#36 已全部合并进 main：录制 → 自动缩放 → 成片样式 → 导出全链路可用，
  含 摄像头画中画（实时烘焙 + 独立圆形预览悬浮窗）、提词器、布局片段、背景移除。
- 真机验证口径：`FOCUSEE_DATA_DIR=/tmp/x "./build/FocuSee Clone.app/Contents/MacOS/Electron"
  --focusee-user-data /tmp/ud --e2e-rec --e2e-rec-takes=2 --e2e-rec-cancel-take=1 --e2e-rec-cam`
  ALL_OK=true（连续段数/取消/摄像头/移动预览窗均可组合）；证据落 `$FOCUSEE_DATA_DIR/artifacts/`。
- 本机 `/Applications/FocuSee Clone.app` 用 `scripts/package-app.sh` 就地更新；更新后必须用
  安装包二进制重跑一次 e2e 再交给用户。

## 硬约束（违反即翻车，均有事故背书）

1. **主进程禁止对悬浮条/预览窗 executeJavaScript**（teardown 期原生 SIGSEGV）——一切控制走 ipc
   事件（`control:*` 通道），见 `test/stop-flow.test.mjs`。
2. **悬浮控制条窗口必须不透明**：macOS 15+ ScreenCaptureKit 忽略内容保护，透明窗口直接入镜；
   圆角观感用原生窗口圆角 + full-bleed 样式实现；烘焙循环用主进程上报的 `record:pillRect`
   镜像填充把控制条从成片移除（`renderer/app.js` drawBakedFrame）。
3. **复用窗口每段录制必须重置状态**：悬浮条/预览窗按新 `startedAt` 走 `rearmForNewTake()`，
   闩锁/计时器/按钮文案一起复位。
4. **圆形元素画进圆的包围正方形**（中心对齐），越界钳制按包围盒——`pipRectAt` 已封装，勿手写坐标。
5. **相机方形裁剪一律 `object-fit: cover` 语义**（源取中心方、目的取圆的包围正方形）。
6. **e2e 启动必须 `--focusee-user-data <dir>`**：否则与已安装应用共用 userData/单实例锁，静默退出。
7. **强杀进程后 SCK 拒绝新会话（Timeout starting video source）**：`kill -9 replayd` 让 launchd
   重启即恢复；同一 bundle 路径不要同时跑两个捕获进程。
8. **预览页每一路 getUserMedia 都要登记并在 stop/隐藏/被替换时释放**（`renderer/cam-preview.js`
   的 liveStreams 集合 + attachSeq 代号守卫）：attach 信号可能重叠（状态重放+显式调用各发一次），
   被取代的流不释放 = 摄像头停止录制后常开（2026-11-15 事故）。

## 未实现（有意边界，见 DIFF-REPORT）

真实点击事件（需输入监控权限+签名）、AI 字幕、音频增强、云分享、多语言。
提词器在 macOS 15+ 可能入镜（内容保护失效的已知限制，未做烘焙移除）。
