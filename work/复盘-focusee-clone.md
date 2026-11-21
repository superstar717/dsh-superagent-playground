# 项目复盘 — FocuSee 复刻（学习原型，PR #32 → #36）

复盘时间：2026-11-15 14:30（Asia/Shanghai）
项目位置：`focusee-clone/`（本仓库）；安装实例：`/Applications/FocuSee Clone.app`
评价标准：**用户真机可用**——单测绿、CI 绿都只是过程指标，最终口径是「打包应用在真机上连续使用不踩坑」。
本复盘只记录事实、取舍与可迁移的教训；与 FocuSee 原版的功能差异见 `docs/DIFF-REPORT.md`。

## 一、最终事实（截至 2026-11-15 14:30）

- **PR #32（原型）→ #34（停止崩溃）→ #36（二次停止 + 预览窗 + 头像圆形 + 控制条移除 + 拖动崩溃）全部合并进 main**，CI 2/2 全绿。
- 真机验证口径：打包应用 e2e（`--e2e-rec-takes=N --e2e-rec-cancel-take=N --e2e-rec-cam`）ALL_OK=true，
  覆盖 连续 4 段 / 取消路径 / 拖动预览窗 / 含摄像头烘焙；证据随 PR 入库（`docs/evidence-865c48b/`）。
- 本机 `/Applications/FocuSee Clone.app` 与 main 同一构建（就地更新 + 安装后重跑 e2e）。
- 用户真机反馈共 6 次往返（E159 的统计口径），逐条根因见「三、犯过的错」。

## 二、做得对的

1. **净室方法**：不反编译、只看可见界面/控件树/官网，差异如实写进 DIFF-REPORT——学习复刻的边界立住了。
2. **每次真机反馈都带回一条护栏**：textual tripwire（`test/stop-flow.test.mjs`，33 条断言）把每个事故类
   固化成可 grep 的不变量，同类问题回归时 CI 直接拦下。
3. **「修复前必失败 / 修复后必过」的证据对照**：`--e2e-rec-two` 在修复前构建复现 take2 停止失效、
   修复后 ALL_OK=true，证据 JSON 随 PR——修复声明可对账（E160 的正面实践）。
4. **事件契约替代跨窗口注入**：悬浮条/预览窗所有控制走 ipc 事件（pillReady/stopSignal/cancelSignal/
   attachCamera/previewReady），彻底避开 executeJavaScript 的原生崩溃类（E158）。
5. **就地更新 + 安装后验证闭环**：`package-app.sh` → 覆盖 /Applications → 用安装包二进制重跑 e2e →
   重启给用户，交付即所见。

## 三、犯过的错（逐条：现象 → 根因 → 现在的护栏）

| # | 现象 | 根因 | 护栏 |
|---|---|---|---|
| R1 | 黑屏 / 时长 0 / 停止即整体退出 | 隐藏窗口节流 + renderer 引用主进程变量 + 跨窗口 executeJavaScript 崩溃 | `backgroundThrottling:false`、teardown 只碰本地态、禁 executeJavaScript（E158/E159） |
| R2 | 第二次录制无法停止（本工单起因） | 悬浮条窗口跨录制复用，`stopped` 闩锁从不复位，按钮/计时也停在上一段 | `rearmForNewTake()` 按新 startedAt 全量重置；e2e 同进程连跑 ≥2 段（E161） |
| R3 | 拖动圆形预览窗即弹崩溃框 | `reportMove` 把 `.bounds` 赋给 `display` 后又读 `display.bounds.x`（二次解包） | 三处坐标计算归一 + 空值守卫 + e2e 真实移动窗口步骤 |
| R4 | 成片头像上下被削平（透镜形） | 相机方形裁剪画进 `w×h` 参考矩形，而圆形裁剪直径是 `d`——横幅相机时圆的上下两段落在矩形外 | 方形裁剪画进圆的包围正方形（烘焙+编辑器两处）；`pipRectAt` 按圆包围盒钳制 + 单测 |
| R5 | 控制条出现在成片里 | macOS 15+ ScreenCaptureKit 忽略窗口内容保护，`setContentProtection` 不再保证排除 | 主进程实时上报悬浮条矩形，烘焙帧用其正下方内容镜像填充移除（E162） |
| R6 | 头像「不是圆的」的另一半原因：预览窗归属错位 | 预览嵌在方形控制条窗口里（矩形视频），与烘焙的圆形两套几何 | 预览独立为圆形悬浮窗，位置即成片画中画位置，尺寸与烘焙圆同步 |

环境侧两次踩坑（不属于应用代码，但拖了真机验证后腿）：
- 强杀 Electron 进程后 ScreenCaptureKit 拒绝新会话（`Timeout starting video source`），
  `kill replayd` 让 launchd 重启即恢复；同一 bundle 路径同时两个进程会互相挤占捕获。
- dev/e2e 实例与已安装应用共用 package.json name → 同一 userData → 同一单实例锁 →
  e2e 启动即静默退出；`--focusee-user-data` 隔离解决。

## 四、如果重来

1. **第一天就建真机 e2e 门禁**：同一进程连续 ≥2 段 + 取消路径 + 真实移动窗口 + 抽帧断言，
   而不是等用户真机踩坑后逐条补（E159：6 次反馈里 4 次是单测结构上覆盖不到的）。
2. **「复用实例」先列状态复位清单再写功能**：凡是单例窗口/常驻对象，列出每会话字段，
   流程开始全部复位——闩锁、计时器、按钮文案一起。
3. **依赖 OS 行为的特性标注系统版本敏感性**：内容保护、权限语义、捕获栈（E162），
   「不入镜」类承诺从第一天就设计捕获后兜底。
4. **坐标计算统一封装**：同一份「Display→bounds」取法全文件唯一，禁止各自解包
   （R3 的二次解包就是三处写法不一致养出来的）。

## 五、仍未解决 / 已知边界

- **真实点击事件**（自动缩放用光标停留簇近似）：需要「输入监控」权限 + 签名应用，超出学习原型范围。
- **AI 字幕 / 音频增强 / 云分享 / 多语言**：未实现（DIFF-REPORT §3/§4）。
- **提词器在 macOS 15+ 可能入镜**：同 E162 机制，烘焙移除目前只覆盖控制条；提词器区域大且位置可拖，
  镜像填充会明显破坏画面——如实标注为已知限制，未做「移除」承诺。
- 自动缩放对导入视频不可用（无光标轨迹）——与 FocuSee 原版行为一致。

## 六、机制落地清单（「哪些需要落地成机制」的答案）

| 机制 | 载体 | 状态 |
|---|---|---|
| 跨窗口只走 ipc 事件、禁 executeJavaScript | LESSONS E158 + 仓库 textual 测试 | ✅ 已落地 |
| GUI/录制类合并门 = 打包应用真机 e2e（≥2 段+取消+移动窗口+抽帧） | LESSONS E159 + 仓库 `--e2e-rec-takes/cancel-take` 场景 | ✅ 已落地 |
| 修复声明 ↔ diff 对账 | LESSONS E160 | ✅ 已落地 |
| 复用实例跨会话状态复位 | LESSONS E161 + `rearmForNewTake` + 测试 | ✅ 已落地 |
| macOS 15+ 内容保护失效、不入镜要有捕获后兜底 | LESSONS E162 + 烘焙镜像填充 | ✅ 已落地 |
| WebM 无时长头的探测 | LESSONS E163 | ✅ 已落地 |
| 强杀进程后 SCK 拒绝新会话 → kill replayd 恢复；同 bundle 双进程抢占 | LESSONS E164（本轮新增） | ✅ 已落地 |
| Electron 单实例锁按 userData：dev/e2e 必须隔离 userData | LESSONS E165（本轮新增） | ✅ 已落地 |
| 圆形元素按包围正方形绘制 | `pipRectAt` 单测 + 代码注释（项目内足够，不上升全局） | ✅ 已落地 |
| 项目现状与硬约束 | `focusee-clone/AGENTS.md`（本轮新增） | ✅ 已落地 |

不需要上升为机制的单点项：一次性环境排障手法（进 LESSONS 即可）、单个几何修复（单测覆盖）。
