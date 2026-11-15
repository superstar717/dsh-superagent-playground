# 编码器与录制负载实测：H.264 硬编验证 + 负载归属（工单 8dae0e8b1c01）

日期：2026-11-16 凌晨（Asia/Shanghai），机器：2017 MacBook Pro，Intel i7 4C/8T + 16GB，
macOS 26.x（darwin 25），Electron 45.2.2（Chromium ~144）。构建：本分支 = master(8c9c472) + H.264 优先（装机版同款改动）。
工具与原始数据：`work/perf/`（measure-take.sh / summarize-run.py / analyze-sample.py / bench-bake.js），
逐轮数据在 `work/perf/runs/<label>/`（app.log、top.txt、pids.txt、probe.json、renderer-sample.txt）。

## 1. 结论（一句话）

**H.264 硬编是真的**：MediaRecorder `video/webm;codecs=h264,opus` 在本机实际走 VideoToolbox
硬件编码（Intel KBL Quick Sync），录制输出确为 H.264（6 段实测全为 h264 Baseline，无一回退 VP9）；
**编码不再是大头**：录制中「编码+捕获管线」的渲染进程 CPU 从 VP9 的 ~43–60% 降到 ~7–14%（约 4–5 倍），
编码工作移入 GPU 进程（+7%）后总占用约减半。上一轮的优化方向已被真机数据证实。

## 2. H.264 硬编验证（三重证据）

1. **产物**：e2e 真录 6 段（r1/r4/r5/r8/s1/s3 等）ffprobe 全部 `h264 Baseline 1680×1050`
   （runs/*/probe.json）；VP9 对照组为 `vp9 Profile 0`。装机版（用户正在用的
   /Applications/FocuSee Clone.app，app.js=retro 分支+H.264 同款改动）行为一致。
2. **编码器栈**：录制中采样 VTEncoderXPCService（VideoToolbox 的编码 XPC 服务，仅 h264 录制时出现
   CPU，VP9 段为 0）→ 栈内出现 **AppleIntelKBLGraphicsVADriver / VAME / MTLDriver**（Kaby Lake
   硬件编码驱动，s3-h264-vtxpc/vtxpc-6357.txt）；Apple 软编特征（jvt*/CPEL*）为 0。
3. **线程形态**：VP9 录制时渲染进程出现 3 条 **CodecWorker** 线程（libvpx 软编，s2 样本），
   H.264 录制时渲染进程 **没有** CodecWorker（s1 样本）——编码不在渲染进程，符合 Chromium 平台
   编码器（VideoToolbox，GPU 进程宿主）的形态。

## 3. CPU A/B（无摄像头，16s 真录，同机同环境，ABBA 交错）

| 指标（8 线程机器上，单核=100%） | VP9 软编 | H.264 硬编 | 变化 |
| --- | --- | --- | --- |
| 编辑器渲染进程（软编宿主） | 43.2–60.3% | **7.3–14.5%** | ≈ ÷4–5 |
| GPU 进程（硬编宿主） | 7.5–8.4% | **14.2%** | +6–7（编码移入） |
| 应用进程树合计（窗口期内均值） | 22.8–33.1% | **6.2–11.8%** | ≈ ÷2–3 |
| WindowServer（两轮共有） | 35.8–38.7% | 40.1% | ≈平（非编码项） |
| 系统整体 idle | 28–32% | 26–31% | ≈平（环境负载主导） |

数据：r2/r3/r6/r7（VP9，15 个窗口内样本）、r4/r8/s1（H.264）；raw 在 runs/。
s1/s2 为背靠背复测（中间只差一次重启），差距方向与幅度一致，**可复现**。

**读法**：编码这块的成本从「≈0.5–0.6 个核的渲染进程软编」降到「GPU 进程 ≈0.14 核 + 渲染 ≈0.07 核」，
总降幅约 0.3–0.4 个核。录制画面的编码链路已经不是瓶颈。

## 4. 「还卡」的归属：环境占大头（实测）

同一时段的机器基线（所有 run 的 top 样本一致显示）：

| 进程/组 | 占用（窗口均值 → 峰值） |
| --- | --- |
| Google Chrome（全部 helper 合计） | 5.5–7.4% 均值，**峰值 90–110%**（前台标签，含 04:38 空闲时段 54%+32% 两个 helper） |
| 本机 knowledge-agent 服务 | 单点实测 37.4% |
| WindowServer | 20–43% |
| 机器整体 idle | 26–32%（即 8 线程常驻 ~2/3 占满） |

结论：**录屏应用自身（H.264 后）只剩 ~0.2 个核；用户感知的「卡」主要来自 Chrome 标签（≈0.5–1 核）
+ knowledge-agent（≈0.4 核）+ WindowServer（≈0.3 核）等环境负载在 8 线程上的叠加。**
「面板标签切走/最小化」依旧是单项收益最大的一步（与上一轮建议一致，数据不变）。

## 5. 意外发现：摄像头被闲置实例占用 45 分钟（隐私相关）

VDCAssistant 日志（log show）：用户正在运行的 FocuSee Clone 实例（pid 5880）在 **03:49:55** 开始
流式占用 FaceTime 摄像头（一段未保存的录制取消后 ~8s 重新获取，之后**从未停止**），直到 04:34:41
我方将其退出才释放（累计 ~45 分钟、79,330 帧；期间摄像头指示灯常亮，其他应用报
`NotReadableError: Could not start video source`，包括有摄像头权限的装机版本身）。
运行中的构建包含 retro 分支的释放修复，但该路径仍会泄漏——**建议作为下一个工单的修复点**：
cancel/teardown 后再次校验「无录制时零采集」，或加 idle 看门狗。

## 6. 摄像头画中画（bake）场景：本轮未能实测 + 合成基准替代

**真机 bake 场景被两个独立问题挡住**：
1. 03:49–04:34 摄像头被用户实例占用（见 §5，已排除——退出后设备本身可用，ffmpeg 可采集）；
2. 04:30 起 macOS 屏幕捕获子系统（ScreenCaptureKit）在本机进入饱和/卡死状态：04:30 前的
   8 次捕获会话正常（pill 起来 13–16s），之后 4 次（打包版×2、开发版×2）全部在源枚举/捕获启动
   阶段挂起，pill 20s 等待内不出现。本轮未重启系统，未能自愈。

**替代：合成基准**（bench-bake.js，完全复刻 drawBakedFrame 的每帧工作：全屏 drawImage + 镜像填充 +
圆裁剪 PiP + 描边；captureStream(FPS) + MediaRecorder h264 8Mbps；无屏幕捕获参与；15s 窗口、13 个
CPU 样本，c 系列 4 组）：

| 配置 | GPU 进程 CPU | 渲染进程 CPU | 合计（8 线程机器的单核百分比） |
| --- | --- | --- | --- |
| bake30 + h264 录制（线上形态） | 28.9% | 15.5% | **17.1%** |
| bake15 + h264 录制（30→15 后形态） | 15.0% | 8.1% | **8.9%** |
| bake30 不录制（纯合成开销） | 13.0% | 3.0% | 6.2% |
| bake15 不录制 | 8.1% | 1.9% | 3.8% |

分解：30→15 使「合成画布 + 送帧编码」整链近似减半（17.1→8.9，−0.08 核）；其中画布本身 −0.024 核，
编码送帧 −0.058 核。注意合成基准不含真实屏幕视频解码与相机采集，属**上限偏保守的隔离测量**；
真实录制中这两项会让绝对值更高，但 30→15 的「减半」比例关系可迁移。

## 7. 对「下一刀」的建议（降帧率 30→15 / 按需烘焙）

- 编码已近乎免费（§3）；合成基准显示 30→15 还能再省 ≈0.08–0.1 核（§6），
  但对比环境负载（Chrome 标签一项就 0.5–1 核）属于二档收益；
- **推荐顺序：① 录制时切走面板/多余 Chrome 标签（≈0.5–1 核，零代码）→ ② 退出/降级 knowledge-agent
  （≈0.4 核）→ ③ 若开摄像头画中画仍卡，再把 bake 降到 15fps（≈0.08–0.1 核，一行改动）**；
- 按与用户的既有约定，默认帧率保持 30 不动，等用户点头才改。

## 8. 导出路径复核（H.264 优先对导出同样生效）

`electron . --e2e` 全链路（示例项目→自动缩放→导出）实测：导出文件
`exports/…-focusee-export-960x540.webm` = **1,295,089 字节，h264 Baseline 960×540**（VP9 时代同场景
约 1.3MB，大小与码率一致）。e2e 汇总里 `export.bytes:0` 是**测试架汇报位**（渲染侧返回值），磁盘
文件真实 1.3MB，产品无影响；单测 33/33 通过。

## 9. 复现方式

```sh
cd focusee-clone
# 单段 16s 真录 + CPU/栈采样（codec 可换 vp9 做对照）
bash ../work/perf/measure-take.sh <label> h264 0 16000
# 合成 bake 基准（无屏幕捕获）
bash ../work/perf/bench-run.sh <label> 30 1 15
# 汇总
python3 ../work/perf/summarize-run.py ../work/perf/runs/<label>
python3 ../work/perf/analyze-sample.py ../work/perf/runs/<label>/renderer-sample.txt
```
