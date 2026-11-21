# 真实点击捕获（plan A，工单 0cdd8d5c7d18）

## 为什么

此前自动缩放用「光标停留簇」近似点击，与真 FocuSee 的判定依据相反：
果断点击（停留 <0.42s）触发不了，读文档的长停顿反而缩放；且坐标按宽、高分别
归一化，半径实为椭圆；匀速慢移会被累积成合法停留，缩放点取停顿中点而非点击瞬间。

现在：**录制时启动一个 macOS 全局点击监听 helper，缩放/点击涟漪用真实点击；
helper 缺失或无辅助功能权限时自动退回（改进过的）停留判定。**

## 架构

```
native/click-tap/main.swift      listen-only CGEventTap，独立进程（崩溃不连累录制器）
  │  stdout JSON 行协议：
  │    {"type":"status","ok":…,"ax":…,"reason":"listening"}     启动时一次
  │    {"type":"event","kind":"leftMouseDown","button":0,"x":…,"y":…,"ts":…}  每次 DOWN/UP
  │  --probe：创建一次 tap 即退出（权限徽标用，exit 0/4）
  ▼
main.js ClickTap 模块            capture:begin 拉起 / capture:end SIGTERM 回收；
  │  事件 ts 与光标采样同用 Date.now 时钟 → t 落在同一条录制时间轴
  ▼
capture:end → { cursor, clicks, clickCapture }
  ▼
renderer/app.js                  clicks.length ? clicksToActions(真实点击)
                                 : detectActions(停留兜底，圆形半径+速度门+停留末端)
  ▼
p.clicks（缩放包络 + 点击涟漪共用同一份数据）、p.clickSource = 'real' | 'dwell'
```

要点：

- **listen-only**（`kCGEventTapOptionListenOnly`）：helper 永远不能改写/吞掉用户输入。
- **独立进程**：helper 挂死不影响录制；TCC 责任进程是签名后的 app bundle，
  授权一次跨重打包稳定（配合 scripts/package-app.sh 的自签证书）。
- **权限探测**：`--probe` 短进程 + 录制对话框「真实点击」徽标 + 缩放面板
  「点击源」行 + 打开辅助功能设置的深链按钮。
- **兜底判定改进**（三缺陷的 #2/#3，无权限时仍然生效）：
  1. 半径按显示宽度归一、`aspect` 校正 dy —— 1920×1080 横竖同为 23px 圆；
  2. 簇内中位步进速度 ≤ maxSpeed（默认 12px/s）才算停留 —— 24px/s 匀速爬行被拒；
  3. 动作时刻取簇末端（指针停稳处），位置取停稳坐标 —— 最接近「点击瞬间」。

## 为什么自建 helper（候选复核）

| 候选 | 结论 |
|---|---|
| global-mouse-events 1.2.0 | **Windows only**（包描述明确），macOS 不适用 |
| iohook | 已死，Electron ABI 长期失配 |
| osx-mouse / ffi 系 | 陈年未维护，新 Node/Electron 不可用 |
| keyspy 1.1.1 | 最接近：Swift CGEventTap helper + stdio，鼠标事件含坐标。不采用的原因：postinstall 从 GitHub releases 下载二进制（安装期网络依赖 + 供应链面）、以键盘为主（sudo-prompt/cli/keymap 等负担）、无机器可读的 tap 创建状态（无法可靠探测权限）、tap 可阻断输入（我们只要 listen-only） |
| 自制 Swift helper（采用） | 60 行、无 node-gyp/ABI 问题、无安装期下载、协议可控（权限状态+探针）、编译工具（swiftc/CLT）在打包机上已验证存在 |

## Windows

JS 层（spawn helper、JSON 协议、采集→归一化→缩放）与平台无关；Windows 只差一个
`SetWindowsHookEx(WH_MOUSE_LL)` 的 helper 可执行文件（需有 Windows 环境编译/实测）。
当前没有 helper 时一切照旧走停留兜底。

## 验证状态（诚实清单）

| 项 | 状态 |
|---|---|
| helper 单体：AX 环境下合成真实点击 → JSON 事件坐标/时刻精确 | ✅ 实测（3 次点击 → 6 事件，坐标位位正确，通用二进制 arm64+x86_64） |
| 兜底判定：圆形半径 / 速度门拒爬行 / 飞入后停顿不误杀 / 停留末端语义 | ✅ 单测（zoom.test.mjs，npm test 41/41 绿） |
| 真实点击映射 / 去重 / buildZooms 真实点击优先 | ✅ 单测 |
| 无权限自动退回 + UI 可见 | ✅ 代码路径 + 录制对话框徽标/缩放面板点击源行（dev Electron 无授权场景即走此路径） |
| 打包后的 app + 用户授予辅助功能后的端到端 | ⚠ 需要人：打包 → 首次录制 → 系统弹辅助功能授权 → 允许 → 再录，确认缩放落在真实点击上（打包脚本已把 helper 以同一身份签名） |
