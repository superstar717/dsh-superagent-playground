# FocuSee Clone — 学习复刻原型

用 **Craft Anything 的净室（Clean room）方法**研究本机 FocuSee 2.5.3（Gemoo 出品的自动剪辑录屏工具），
然后按其可见界面与工作流复刻的一个 Electron 原型。不含 FocuSee 的任何代码、图标或素材；
不绕过任何 DRM / 登录 / 授权。

## 这是什么

一条完整的「录屏 → 自动缩放 → 成片」链路：

1. **录制**：屏幕或单个窗口 + 可选麦克风 + 可选摄像头画中画 + 可选提词器
   （悬浮控制条与提词器都不计入画面）。
2. **自动缩放**：分析光标轨迹，找到停留点（≈ 点击/停顿），自动生成缩放片段，
   进入/离开用 smoothstep 缓动，缩放窗口始终保持在画面内。
3. **成片样式**：画布比例（16:9 / 1:1 / 4:3 / 9:16 / 原始）、内边距、圆角、阴影、
   内边框、背景模糊，12 个渐变/纯色背景 + 自定义纯色。
4. **摄像头画中画 + 镜头布局**：录制的摄像头画面在编辑器中合成到画布，
   四角圆形 / 底部居中卡片五种布局，大小可调；导出时同样合成。
5. **3D 动效**：逐列透视（梯形映射）跟随光标倾斜，可调基础角度。
6. **提词器**：悬浮窗（透明、置顶、不入镜），可编辑讲稿、调字号、自动滚动。
7. **光标强调**：点击涟漪（可选色板）+ 可选光标高亮。
8. **导出**：实时渲染 canvas → WebM（VP9 + Opus）；装了 ffmpeg 可一键转 MP4。

## 运行

```sh
npm install          # Electron 45（本机有缓存）
npm run sample       # 生成示例项目用的演示视频（ffmpeg，合成画面，无第三方素材）
npm start            # 打开应用
npm test             # 11 个几何/自动缩放单元测试
```

首个运行会自动创建一个「示例录制」项目（点首页「打开示例项目」），
里面有 3 段由光标停留点生成的自动缩放，直接播放/导出即可验证全链路。

### 打包为独立应用

```sh
./scripts/package-app.sh   # 产出 build/FocuSee\ Clone.app（改应用身份并 ad-hoc 重签）
```

注意：替换 app 二进制后，macOS 的屏幕录制授权需要重授（列表开关关→开 + 重启应用）。

### E2E

```sh
FOCUSEE_DATA_DIR=/tmp/focusee-e2e ./node_modules/.bin/electron . --e2e
```

无人值守跑完 6 屏截图 + 1 次导出，产物在 `artifacts/`。

## 结构

```
main.js            Electron 主进程：录制、项目存取、ffmpeg、悬浮控制条
preload.js         contextBridge IPC 面
renderer/
  index.html       首页 + 编辑器 + 录制/导出/设置弹层
  app.js           界面状态、录制编排、导出编排、inspector 面板
  zoom.js          纯几何/自动缩放数学（被测试直接引用）
  render.js        canvas 合成：背景、取景框、缩放、点击涟漪、字幕
scripts/
  make-sample.js   合成示例视频 + 光标轨迹（ffmpeg drawbox/drawtext）
  build-zoom-cjs.js  zoom.js → zoom.cjs（测试用 CommonJS 副本，npm test 自动重建）
test/zoom.test.mjs  11 个用例：停留点检测、缩放包络、取景矩形、坐标映射
```

## 已知边界（与 FocuSee 2.5.3 的差异）

完整对照见 `../docs/DIFF-REPORT.md`。一句话版：
**「自动缩放 + 成片样式 + 导出」全链路可用；AI 字幕、音频增强、摄像头布局、
3D 动效、云分享、真实点击事件未实现**——原型用光标停留簇近似“点击”，
这一行为差异写在代码注释与差异报告 §4。
