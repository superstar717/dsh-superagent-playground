# motiontemplates/all 核查与可用性评估

- 工单：`c7607c4b27137c8e9ae323c6167bf9d4`
- 核查时间：2026-11-14 10:52–11:05（Asia/Shanghai）
- 触发消息：`@openclaw助手 视频里提到的下载地址是 github.com/motiontemplates/all，打开就能看到全部模板，选一个喜欢的开始创作就行。`
- 结论性质：独立核查。**未取得视频原片**，因此只核对消息里的地址、仓库实际内容和模板包可用性，不核对视频原话或视频推荐了哪个模板。

---

## 一句话结论

地址真实存在，是 MotionGit 的模板**目录**（100 个模板 + 12 个预上线 + 1 个预览项目，114 个 Demo）。但 GitHub 仓库里没有模板包本体：**只有 #385712 一个模板能从 GitHub 直接下载**，其余 99 个要跳转 motiongit.com 免费注册后下载，12 个预上线暂不开放下载。

我用 #385712 在本机 macOS 上端到端跑通（预览 + 8 秒 1920×1080@60fps H.264/AAC 成片，含原生音效），所以"能用"是真的；但"打开选一个就开做"只对 1 个模板成立，并且需要一个**能读文件、能执行本地命令的 AI 助手** + Node/Python/uv/FFmpeg/Chrome 环境。

---

## 1. 核实范围

**已核实**：

- 仓库存在性、归属、元数据、提交历史、License 状态。
- 仓库内容清点：模板/预上线/Demo 数量、分组、下载方式、媒体链接、引用的 38 个模板仓库。
- GitHub Pages 目录页与 motiongit.com 官网（首页、模板页抽样、prelaunch 页、法务页）。
- 唯一直下模板 #385712 的完整制作链：下载 → 解压 → 装依赖 → plan → prepare → preview → render → 音频混流 → ffprobe 校验。

**未核实**：

- 视频本身（未附链接）；视频里的原话、上下文和推荐理由。
- 99 个"官网下载"模板的真实下载包内容（未注册/未登录 motiongit.com，只在页面层核实"免费 + 需登录 + MIT"）。
- Windows/Linux 上的运行情况（本机只有 macOS）。
- 每个模板的实际成片质量、素材合同和商用素材许可（只抽查了包内 MIT 与第三方字体许可文件）。
- 官网 About 页自称的 133 个模板 / 91.7K 下载量（平台自报，未独立复核）。

---

## 2. 存在性与身份

| 项 | 实测值（2026-11-14 10:52 CST） |
| --- | --- |
| 仓库 | <https://github.com/motiontemplates/all>，公开仓库，非 fork |
| 归属 | `motiontemplates`，GitHub 账号类型为 **User**（不是 Organization） |
| 账号 | 创建于 2026-10-12T10:53:49Z；53 个公开仓库（51 个模板仓库 + 1 个格式规范仓库 + `all`）；142 followers |
| 仓库 | 创建于 2026-10-15T08:22:25Z；最后 push 2026-11-12T16:50:42Z；默认分支 `main` |
| 活跃度 | 972 stars / 100 forks / 4 watchers / 0 open issues |
| 提交历史 | **只有 1 个 commit**（`e46dbc2 Update MotionGit template collection and demos`，2026-11-12） |
| License | 仓库级 license 为 `null`（仓库没有 LICENSE 文件） |
| 主页 | <https://motiongit.com> |
| Pages | <https://motiontemplates.github.io/all/> HTTP 200，标题"MotionGit 模板合集" |

补充观察：

- 972 stars / 100 forks 集中在 `all` 一个仓库；其余 37 个被目录引用的模板仓库 star 数为 0–1（#385712 为 166），账号下 13 个更早的模板仓库也不在目录中。这更像"产品方集中推广目录仓"，不是社区自然增长的项目；不影响内容真实性，但不宜把 star 数当作质量背书。
- 账号同时维护 `motiontemplates/motion-spec`（.motion 格式规范，22 stars，无 License），说明"开放格式"不是空口说法。

---

## 3. 内容清点：目录数字与实测一致

仓库根目录是**目录/索引**，不是模板文件仓库。核心文件：`README.md`（1619 行）、`CATALOG.md`（1596 行）、`catalog.json`（5635 行）、`index.html`、`en.html`、`assets/`，克隆后 2.1 MB。

| 声明（README / Pages / catalog.json） | 实测 | 结论 |
| --- | --- | --- |
| 100 个模板 | `listing.templateCount = 100`，`templates` 数组 100 条 | 一致 |
| 12 个预上线模板 | 12 条 `prelaunch` | 一致 |
| 1 个测试项目 | `3d-book`（`previewOnly: true`，coming soon） | 一致 |
| 114 个 Demo | 114 个 Demo URL，去重后仍 114 | 一致 |
| "100% 开源" | `openSource: true` 100/100；但 `githubSourceIncluded: true` **仅 1/100** | 只在"下载后的包内"成立；GitHub 上只有 #385712 有源码 |
| 模板仓库 | 38 个唯一仓库，逐个 `gh api` 全部存在 | 一致 |
| 仓库 License | 37 个无 GitHub license；#385712 为 MIT | 与"随包许可证"说法一致，但不能只看 GitHub |

分组与画幅：

| 维度 | 数量 |
| --- | --- |
| 分组 | innovation 52、talk 19、explainer 12、product 8、art 8、open 1 |
| 画幅 | 横屏 89、竖屏 11 |
| 下载方式 | `direct-package` 1 个（#385712）；`official-page` 99 个 |
| 可下载状态 | `download-available` 1 个；`check-official-page` 99 个；预上线 12 个；coming-soon 1 个 |

媒体资源：

- `catalog.json` 共 339 个 demo/preview/poster 字段；域名分布：`media.openaicut.com` 309、`motiongit.com` 24、`motiontemplates.github.io` 3、`raw.githubusercontent.com` 2、`github.com` 1。
- 全量链接检查：去重后 114 个 Demo URL、115 个封面/图片 URL、112 个模板/预览页面 URL，合计 341 个 URL 全部返回 200/206/302，0 失败；另外单独验证了 GitHub Pages 目录页（200）、两个公开包（200）和 3d-book 的 Release 资产（302 → 可下载）。
- `3d-book` 的 Demo 放在本仓库 GitHub Release（`demo-batch-two-2026-10-21`，4 个资产），可访问。
- Pages 目录页实际渲染 114 张卡片，与 `catalog.json` 一致。

结论：**"打开就能看到全部模板"基本属实**——目录、图片、Demo、下载地址都在，且数字自洽。但"全部模板"指的是 114 张目录卡片（100 个模板条目，其中 #385712 横竖各一条，共 101 条；加 12 个预上线 + 1 个测试项目 13 条），不是 114 个可下载文件——可直接下载的只有 1 个。

---

## 4. 端到端实测：#385712 确实能跑通

### 4.1 下载与包结构

| 项 | 值 |
| --- | --- |
| 下载地址 | <https://motiontemplates.github.io/385712/downloads/kinetic-tech-zh.motion>（英文版同路径 `kinetic-tech-en.motion`，均 HTTP 200） |
| 文件 | 17,596,250 bytes，ZIP（`.motion` 就是普通 ZIP） |
| SHA-256 | `472a95af35f8e0c09c0f7dc2ca0992b7c9a3405c5aa8063730c347fc4e015c21` |
| 解压 | 27 MB，331 个文件 |
| 包内入口 | `00-START-HERE.md`、`CREATION.md`、`motion.json`、`guide.json`、`adapter.py`、`render.mjs`、`mix.py`、`core/`、`licenses/` 等 |
| 许可 | `licenses/TEMPLATE-LICENSE.txt` = MIT；字体为 OFL（Anton / Geist / Noto Sans SC），第三方资源另有声明 |
| 包声明 | `permissions.network = false`（运行时不联网）；`coverageComplete: false`；plan 里 `platformManifestDigest = "not yet established by official packer"`（公开包未由官方 packer 建立摘要）；`motion.json` 自述"未发布…作者候选" |

### 4.2 环境与步骤

本机环境：macOS 13.7.8、Node v24.15.0、npm 11.12.1、系统 Python 3.10.9、uv 0.8.5、FFmpeg N-124654、Chrome 157。包要求 Node 22+、Python 3.11+、uv、FFmpeg/ffprobe、Chrome；系统 Python 3.10.9 不满足，`uv` 自动解析到 3.12。

首次安装需要联网（运行时不联网）：

- `npm ci`：1 个包（`playwright-core@1.64.0`），约 3 秒。
- `uv run adapter.py`：12 个 Python 包；下载量约 50 MB（numpy 16.2 MiB、scipy 29.7 MiB、soundfile 1.1 MiB，其余为小包），装完后后续运行不再下载。

实际命令与耗时：

| 步骤 | 结果 | 耗时 |
| --- | --- | --- |
| `npm ci` | 成功，1 package，0 vulnerabilities | 3 s |
| `uv run adapter.py plan --input ../my-video/user.json --out ../my-video/plan.json` | 成功；8.0 s / 480 帧 / 1920×1080@60 | <1 s |
| `uv run adapter.py prepare --input ... --out ../my-video/instance` | 成功，生成 27 MB 实例目录 | 0.8 s |
| `uv run adapter.py preview --instance ... --out ../my-video/preview.png --time 2` | 成功；1920×1080 PNG（2.8 MB），画面为真实模板渲染（"创作 / 把你的想法 / 变成清晰的视觉故事"） | 35.7 s（含浏览器启动） |
| `uv run adapter.py render --instance ... --out ../my-video/silent.mp4` | 成功；`silent.mp4` 19,577,062 bytes；480 帧 / 8.000 s / 1920×1080 / 60 fps / H.264 yuv420p；`errors: []` | 3 min 22.8 s（含音频合成与混流） |
| 音频混流（adapter 内部调 `mix.py`） | 成功；`silent-with-audio.mp4` 19,669,192 bytes；H.264 + AAC 48 kHz 立体声；mean −32.0 dB / peak −3.75 dB（模板原生动作音效，无配音/配乐，符合本次输入） | 含在上一项 |

最终文件的 ffprobe 结果见 `work/evidence/motiontemplates/ffprobe-final.json`；4 秒处画面见 `work/evidence/motiontemplates/385712-frame-04s.jpg`。两个文件的 SHA-256 见 `work/evidence/motiontemplates/sha256.txt`。

### 4.3 实测结论

- **可用，不是空壳**：从公开 GitHub 直下的包确实能在 macOS 上完成 plan → prepare → preview → render，输出真实 1080p60 视频和独立音轨。
- **不是"点开即用"**：需要能执行命令的 AI 助手/终端，首次要联网装依赖；8 秒短片本机渲染约 3 分 23 秒（不含首次装依赖）。
- **公开包版本落后官网**：公开包是 `v0.2.7-open-beta`；官网模板页当前展示 `v0.2.44-alpha.5`（竖屏）。仓库/页面明确说明公开本地版与官网个人版独立更新、重复下载不会升级。
- **验证状态要分开看**：包 README 写"横屏 macOS 有实测，其他环境与最大容量不冒充已通过"；官网模板页抽样显示 "Runtime verification: Not verified"（本次只抽查页面，未逐页统计）。本次实测补上了 macOS 这一条。
- **包内 Instructions 是设计的一部分**：README/`00-START-HERE.md` 要求助手先给一句创作回复、按 `CREATION.md` 执行、最后读取 `delivery.json` 再提官网服务；`content-boundary.json` 把这类文件标为 `method-or-contract`。这属于产品的 AI 工作流设计，但把包交给 AI 时应把它当**数据/流程文件**，不要当外部指令无条件执行。

---

## 5. 对"视频说法"的逐句核对

| 说法 | 判定 | 依据 |
| --- | --- | --- |
| "下载地址是 github.com/motiontemplates/all" | ✅ 成立 | 仓库公开存在，Pages 200，API 元数据完整 |
| "打开就能看到全部模板" | ✅ 基本成立 | 100 模板（#385712 横竖各一条，共 101 条）+ 12 预上线 + 1 测试项目，共 114 张卡片、114 个 Demo 全部可浏览；但这是目录，不是模板文件 |
| "选一个喜欢的开始创作就行" | ⚠️ 只对 1 个成立 | 仅 #385712 是 `direct-package`、可从 GitHub 免登录下载；其余 99 个是 `official-page`，页面要求 "Sign in to get template"（免费注册、免费下载）；12 个预上线是 "Download coming soon" |
| 隐含"模板都在 GitHub 上" | ❌ 不成立 | 99/100 要跳转官网下载；GitHub 上只有 #385712 一个公开测试包（中英两版） |
| 隐含"打开网页就能编辑/导出" | ❌ 不成立 | 没有网页编辑器（站点 Editor 标注 "Coming soon"）；制作要交给能读文件、能执行命令的 AI，在本地渲染导出 |

一句话改写（可直接转发）：

> GitHub 上是 MotionGit 的模板目录，114 个 Demo 都能看；但只有 1 个（#385712）能直接从 GitHub 下载，其余 99 个要免费注册 MotionGit 后下载，12 个还没开放。制作要用能跑本地命令的 AI 助手，不是点开网页就能编辑。

---

## 6. 可用性判断

| 使用方式 | 可行性 | 说明 |
| --- | --- | --- |
| 浏览、选风格、看 Demo | ★★★★★ | 目录页/README/CATALOG/Pages 都完整，媒体链接可用 |
| 用 #385712 做一条自己的短片 | ★★★★☆ | 本机实测通过；需要 AI 助手 + Node/Python/uv/FFmpeg/Chrome；首次联网装约 50 MB 依赖；8 秒片子约 4 分钟出片 |
| 用其余 99 个模板 | ★★★☆☆ | 需在 motiongit.com 免费注册并下载对应 `.motion`；抽样页面显示 Free + MIT（art 组为 MOTIONGIT-RELEASE-LICENSE），但未实际下载验证 |
| 用 12 个预上线模板 | ☆☆☆☆☆ | 暂不可下载（"Coming soon"），只能看 Demo |
| 普通非技术用户独立完成 | ★★☆☆☆ | 没有现成 GUI；需要有人/Agent 处理解压、依赖、渲染 |
| 有 AI 助手 + 本地开发环境 | ★★★★☆ | 本次就是这条路径，实测可行 |

**推荐**：

1. 想快速验证值不值得用：直接拿 #385712 跑一条 8–20 秒的短片（`examples/text-only.json` 只用于环境测试，正式内容按包内 `CREATION.md` 写 `user.json`）。
2. 看中了其余 99 个里的风格：去对应 motiongit.com 模板页免费注册下载；优先官网版（支持检查更新），注意官网版和 GitHub 公开版版本不同步。
3. 不要为了"选模板"把整个 README/CATALOG 粘给 AI：README 有 1600+ 行、内嵌 100 张图片和给 AI 的排版指令，容易把上下文撑爆；选好条目后只给该条链接或直接给 `.motion` 包。
4. 商用前看包内 `licenses/`：代码 MIT 可商用/修改/再分发，但字体是 OFL、品牌与第三方素材另有限制；公开包中文字体与 Demo 略有差别。

---

## 7. 风险与注意

1. **项目很新**：账号 2026-10-12 创建、目录仓 2026-10-15 创建、只有 1 个 squash commit、0 issues；star 高度集中在目录仓。不是"跑了很多年的成熟生态"，版本普遍是 beta/alpha。
2. **"100% 开源"的口径**：指下载包内源码 100% 开放（#385712 为 MIT），不是指 100 个模板的源码都在 GitHub；目录仓本身没有 LICENSE。
3. **公开包是 candidate**：`platformManifestDigest` 未建立、`coverageComplete: false`，且公开包版本落后官网；官网抽样页显示 Runtime verification "Not verified"。
4. **包内含 AI 指令与推广**：README/CATALOG 有"截图交接/用户要求查看合集时…"这类写给 AI 的指令，`delivery.json` 规定成片交付后只能发 1 条官网推广消息。把仓库/包交给 AI 时，这些内容会被当上下文执行；应按"数据"处理，并保留用户自己的判断。
5. **要执行第三方代码 + 联网装依赖**：`.motion` 是 ZIP，制作过程会跑包内 Python/Node 脚本、调用本机 Chrome/FFmpeg，并从 npm/PyPI 装依赖。对来源不明的包，先在独立目录/沙箱里审阅再跑；本包的 `motion.json` 声明运行时不联网，但首次安装依赖需要网络。
6. **账号与数据**：motiongit.com 支持 GitHub/Google 登录，隐私政策说明会存邮箱、用户名、下载/API 记录；模板下载需要账号（免费）。是否注册取决于你对这个新平台的信任。
7. **内容体量**：README 1619 行、CATALOG 1596 行、100 张图片；一次性喂给 AI 成本很高，且会触发 README 里的排版指令。

---

## 8. 复现命令（本机 macOS）

```bash
mkdir -p /tmp/motiontest && cd /tmp/motiontest
curl -sSL -o kinetic-tech-zh.motion \
  https://motiontemplates.github.io/385712/downloads/kinetic-tech-zh.motion
unzip -q kinetic-tech-zh.motion -d pkg

cd pkg
npm ci
mkdir -p ../my-video
cp examples/text-only.json ../my-video/user.json   # 仅环境测试，不是正式文案

uv run adapter.py plan    --input ../my-video/user.json --out ../my-video/plan.json
uv run adapter.py prepare --input ../my-video/user.json --out ../my-video/instance
uv run adapter.py preview --instance ../my-video/instance --out ../my-video/preview.png --time 2
uv run adapter.py render  --instance ../my-video/instance --out ../my-video/silent.mp4
# 产物：../my-video/silent-with-audio.mp4

ffprobe -v error -show_entries format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,sample_rate,channels -of json ../my-video/silent-with-audio.mp4
```

说明：`examples/text-only.json` 是包内环境测试输入（README 明确说"只供明确选择的环境测试，不是本期文案"）；正式制作按 `CREATION.md` 用用户自己的主题/素材生成 `user.json`。

---

## 9. 证据索引

| 证据 | 位置/值 |
| --- | --- |
| 仓库 API 元数据 | `gh api /repos/motiontemplates/all`：972 stars、100 forks、0 issues、license null、created 2026-10-15、pushed 2026-11-12 |
| 账号信息 | `gh api /users/motiontemplates`：User、53 repos、created 2026-10-12、142 followers |
| 目录数字 | `catalog.json`：templateCount 100 / previewCount 13 / demoCount 114 / prelaunchCount 12 |
| 下载方式分布 | 1 个 `direct-package`、99 个 `official-page`；`githubDirectTemplateIds: ["385712"]` |
| 38 个仓库存在性 | 逐个 `gh api /repos/motiontemplates/<id>`，0 个缺失 |
| 媒体全量 | 114 Demo + 115 封面/图片 + 112 模板/预览页面，共 341 个 URL 全部可达，0 失败 |
| 模板页抽样 | talk 336980、explainer 257987、product 128610、art 381814、innovation 404937：Free / MIT（art 为 MOTIONGIT-RELEASE-LICENSE）/ "Sign in to get template" / "Not verified" |
| prelaunch 页 | "Coming soon / Collecting feedback / Download coming soon" |
| 公开包 | 17,596,250 bytes；SHA-256 `472a95af...`；331 files；27 MB |
| 预览 | `work/evidence/motiontemplates/385712-frame-04s.jpg`（1920×1080，4 s 帧） |
| 成片 | 19,669,192 bytes；480 帧；8.000 s；1920×1080@60；H.264 + AAC 48 kHz stereo |
| ffprobe | `work/evidence/motiontemplates/ffprobe-final.json` |
| 哈希 | `work/evidence/motiontemplates/sha256.txt` |

**时效性说明**：以上 GitHub / 网站数据为 2026-11-14 10:52–11:05 CST 的快照；star、版本、页面状态会变化，引用前重新核对。所有"数字"均来自本次实测或 API 返回值，未使用平台宣传数字代替实测。
