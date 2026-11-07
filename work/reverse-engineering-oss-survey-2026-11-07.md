# 逆向工程开源项目调研报告

> 调研日期：2026-11-07。数据来源：GitHub API（star/许可/最新提交/最新 Release，当日快照）＋各项目官方 README/文档的通用功能描述。
> 约定：查不到官方信息处明确标注"未核实"，不做推测；未逐一实机复测各工具功能。
> 前情：本 thread 上一轮已调研 [craft-anything](https://github.com/storytold/craft-anything)（应用级"看懂并复刻"引擎），本报告覆盖**其余主流逆向方向**的开源项目。

## 一、分类地图

| 方向 | 代表开源项目 |
|---|---|
| 综合平台 / 反编译 | Ghidra、radare2 / rizin / Cutter、Vivisect、RetDec |
| 动态调试 / 插桩 | x64dbg、Frida、pwndbg / GEF（GDB 增强） |
| 二进制分析框架 / 库 | angr、capstone、Unicorn、Qiling、LIEF |
| 移动端 | jadx、Apktool、MobSF |
| 固件 / IoT | binwalk、FirmAE |
| 协议 / 流量 / 格式 | Wireshark、mitmproxy、Kaitai Struct、webcrack |
| 文件识别 | DIE (Detect It Easy) |
| AI 逆向 Agent（新兴层） | **REA（头部）**、**reverse-skill（技能路由，44.3k★）**、Integuru、ctf-skills、jshookmcp、Seep-Reverse-Lab、cheatengine-mcp-bridge、open-reverselab、Rikugan、android-reverse-engineering-skill |

闭源对照（仅说明生态位，非开源，不列数据）：IDA Pro（Hex-Rays）、Binary Ninja。

## 二、逐项说明（功能 / 优点 / 缺点 / 适用场景 / 成熟度与许可）

### 1. Ghidra —— 综合逆向平台的事实标准
[NSA/Ghidra](https://github.com/NationalSecurityAgency/Ghidra)
- **功能**：反汇编 + 反编译（生成类 C 伪码）、多架构（x86/ARM/MIPS/PowerPC/RISC-V 等）、脚本扩展（Java/Python）、版本跟踪、协作 server、扩展插件生态。
- **优点**：功能最全的免费平台；NSA 官方维护、持续发版；社区插件多；Apache-2.0 允许商用。
- **缺点**：上手门槛高；Java 体系内存占用大；对加固/混淆样本常需插件与手工配合。
- **适用**：恶意软件分析、CTF、固件逆向、通用二进制审计。
- **成熟度/许可**：98,491★；Apache-2.0；最新 Ghidra_12.2_build（2026-10-22）；当日仍有提交。2019-03 开源至今。

### 2. radare2 —— 命令行逆向全家桶
[radareorg/radare2](https://github.com/radareorg/radare2)
- **功能**：CLI 下的反汇编、调试、十六进制编辑、补丁、diff、脚本化（r2pipe 支持多语言）。
- **优点**：极轻量、覆盖面广、天然适合自动化流水线；更新极勤（当日仍有提交，6.2.6 发布于 2026-11-05）。
- **缺点**：学习曲线陡、文档零散、UX 粗糙。
- **适用**：熟练用户的日常逆向、嵌入式、批处理自动化。
- **成熟度/许可**：25,350★；2012 年至今；许可为自定义文件（GitHub 未识别出标准 SPDX，未核实具体条款）。

### 3. rizin / Cutter —— r2 的社区重构与官方 GUI
[rizinorg/rizin](https://github.com/rizinorg/rizin)（4,148★，LGPL-3.0，v0.9.1 2026-06-29）、[rizinorg/cutter](https://github.com/rizinorg/cutter)（20,174★，GPL-3.0，v2.5.0 2026-06-30）
- **功能**：rizin 是 radare2 的重构分支（更整洁的 API 与工程结构）；Cutter 是其官方图形前端（Qt）。
- **优点**：Cutter 对新手友好，可视化分析体验好；两者都活跃（当周内有提交）。
- **缺点**：rizin 生态与插件数量仍小于 r2；深度功能常需回到 CLI。
- **适用**：想要图形界面的二进制分析者；恶意软件分析；教学。

### 4. Vivisect —— 可编程的 Python 静态分析工作台
[vivisect/vivisect](https://github.com/vivisect/vivisect)
- **功能**：Python 实现的静态分析/反汇编平台，可完全脚本化批处理。
- **优点**：代码可读、可编程性强，恶意软件分析圈常用。
- **缺点**：小众（1,002★）、UI 简陋、文档少。
- **适用**：需要把分析逻辑写成代码的团队；批量样本处理。
- **成熟度/许可**：Apache-2.0；2014 年至今仍维护（2026-10-21 有提交）。

### 5. RetDec —— LLVM 基础的机器码反编译器
[avast/retdec](https://github.com/avast/retdec)
- **功能**：把多架构机器码反编译为可读 C 伪码，基于 LLVM，可作为库集成。
- **优点**：MIT 许可、可集成到自研流水线；Avast（Gen Digital）开源。
- **缺点**：**活跃度明显下降**（最后提交 2026-05-26）；输出质量与维护度不及 Ghidra 生态。
- **适用**：批量反编译研究、构建自定义反编译工具链。

### 6. x64dbg —— Windows 用户态调试器
[x64dbg/x64dbg](https://github.com/x64dbg/x64dbg)
- **功能**：Windows 用户态开源调试器，图形界面，脚本、插件生态丰富。
- **优点**：Windows 软件分析的事实开源标准（50,233★）；界面友好；社区插件多。
- **缺点**：仅 Windows 用户态（不覆盖内核态/其他平台）；许可为自定义文件（未识别 SPDX，未核实条款）。
- **适用**：Windows 软件破解与调试、游戏逆向、协议定位。
- **成熟度**：按日期发版，最新 2026.05.27（2026-05-27）；2026-10-28 有提交。

### 7. Frida —— 跨平台动态插桩框架
[frida/frida](https://github.com/frida/frida)
- **功能**：把 JavaScript 脚本注入运行中的进程，hook 函数、追踪调用、改行为；覆盖 iOS/Android/Windows/macOS/Linux。
- **优点**：跨平台动态分析事实标准（22,688★）；脚本即插即用；发版极勤（17.26.1，2026-11-06）。
- **缺点**：对抗高版本系统加固需要经验；注入有性能开销与被检测风险；许可为自定义文件（未识别 SPDX，未核实条款）。
- **适用**：移动 App 协议与逻辑分析、游戏逆向、运行时去混淆、安全测试。

### 8. pwndbg / GEF —— GDB 增强（CTF/pwn 标配）
[pwndbg/pwndbg](https://github.com/pwndbg/pwndbg)（11,164★，MIT，当日有提交）、[hugsy/gef](https://github.com/hugsy/gef)（8,425★，MIT，2026-08-20 有提交）
- **功能**：为 GDB 提供上下文展示、堆分析、常用 pwn 辅助命令。
- **优点**：免费、轻量、二选一即可大幅提升调试效率；pwndbg 已扩展支持 LLDB。
- **缺点**：仅覆盖 *nix 调试场景（配合 GDB/LLDB）；两者功能重叠，选一个即可。
- **适用**：CTF、漏洞研究、*nix 二进制调试。

### 9. angr —— 符号执行与二进制分析平台
[angr/angr](https://github.com/angr/angr)
- **功能**：Python 二进制分析平台：符号执行、控制流/调用图恢复、约束求解，可全自动探索路径。
- **优点**：学术与工业界符号执行事实库（9,337★）；BSD-2-Clause；当日仍有提交。
- **缺点**：学习成本高；大规模符号执行速度受限；**GitHub 上没有标记为 latest 的正式 release**（按主分支/pip 安装使用）。
- **适用**：CTF 自动化解题、漏洞挖掘研究、协议状态机探索。

### 10. capstone / Unicorn / Qiling —— 自动化三件套（库形态）
[capstone-engine/capstone](https://github.com/capstone-engine/capstone)（9,171★）、[unicorn-engine/unicorn](https://github.com/unicorn-engine/unicorn)（9,544★，GPL-2.0）、[qilingframework/qiling](https://github.com/qilingframework/qiling)（6,167★，GPL-2.0，v1.4.11 2026-09-06）
- **功能**：capstone=多架构反汇编引擎；Unicorn=基于 QEMU 的轻量 CPU 仿真框架；Qiling=基于 Unicorn 的全系统仿真（含 rootfs、syscall 拦截）。
- **优点**：三者都是被大量逆向工具/安全产品集成的基础库；都活跃（当周内有提交）。
- **缺点**：是库不是成品工具，需要开发能力；capstone 主仓 GitHub 未识别出 SPDX 许可（未核实条款）；Unicorn/Qiling 为 GPL-2.0（商用集成注意传染性）。
- **适用**：自研分析工具、去混淆（模拟执行）、CTF、恶意样本沙箱化执行。

### 11. LIEF —— 可执行格式解析与改写库
[lief-project/LIEF](https://github.com/lief-project/LIEF)
- **功能**：解析并**改写** ELF/PE/Mach-O/Android（DEX、OAT）/DWARF/V8 字节码，提供 C++/Python/Rust API。
- **优点**：格式覆盖广、API 现代（Apache-2.0）；当日仍有提交，v1.0.0（2026-07-12）。
- **缺点**：只管格式层，不做反汇编/反编译。
- **适用**：加壳/脱壳工程、补丁注入、格式级研究与自动化。

### 12. jadx / Apktool / MobSF —— Android 三件套
[skylot/jadx](https://github.com/skylot/jadx)（51,659★，Apache-2.0，v1.5.6 2026-07-10）、[iBotPeaches/Apktool](https://github.com/iBotPeaches/Apktool)（27,063★，Apache-2.0，v3.0.3 2026-07-20）、[MobSF/Mobile-Security-Framework-MobSF](https://github.com/MobSF/Mobile-Security-Framework-MobSF)（22,158★，GPL-3.0）
- **功能**：jadx=dex→Java 反编译（带 GUI）；Apktool=APK 资源解包/重打包（smali 层）；MobSF=移动 App 静态+动态自动化分析平台（Android/iOS）。
- **优点**：三者都是 Android 逆向/安全评估的标配；全部活跃（当日或本周有提交）；jadx/Apktool 为 Apache-2.0。
- **缺点**：对加固/混淆样本还原度有限（需结合 Frida 动态分析）；MobSF 为 GPL-3.0（商用集成注意）。
- **适用**：App 安全评估、协议分析（配合 Frida/mitmproxy）、教学。

### 13. binwalk / FirmAE —— 固件与 IoT
[ReFirmLabs/binwalk](https://github.com/ReFirmLabs/binwalk)（14,628★，MIT）、[pr0v3rbs/FirmAE](https://github.com/pr0v3rbs/FirmAE)（962★，MIT）
- **功能**：binwalk=固件镜像签名扫描与文件提取（v3 已用 Rust 重写）；FirmAE=大规模 IoT 固件全系统仿真与动态分析。
- **优点**：固件分析工作流的头两步（提取→仿真）都有开源标准答案；均 MIT。
- **缺点**：binwalk 最新 release v3.1.0 距今约两年（2024-10-31），主分支仍在更新；FirmAE 部署复杂、依赖环境多；前代 firmadyne（2,122★，MIT）已约两年未更新（2024-07-21），建议直接用 FirmAE。
- **适用**：路由器/摄像头等 IoT 设备安全研究、固件后门排查。

### 14. Wireshark / mitmproxy / Kaitai / webcrack —— 协议、流量与格式
[wireshark/wireshark](https://github.com/wireshark/wireshark)（GitHub 镜像 10,166★，GPL-2.0，官方主仓在 GitLab）、[mitmproxy/mitmproxy](https://github.com/mitmproxy/mitmproxy)（46,699★，MIT，v12.3.1 2026-10-25）、[kaitai-io/kaitai_struct](https://github.com/kaitai-io/kaitai_struct)（4,729★）、[j4k0xb/webcrack](https://github.com/j4k0xb/webcrack)（3,027★，MIT）
- **功能**：Wireshark=抓包与协议解析事实标准；mitmproxy=可脚本化的 TLS 中间人代理；Kaitai Struct=声明式二进制格式描述语言，生成多语言解析器；webcrack=JS 反混淆 + webpack 等打包产物还原。
- **优点**：把"网络侧逆向"与"格式逆向成果固化"都覆盖了；全部活跃（当日或近月有提交）。
- **缺点**：Wireshark 解析新协议需手写 dissector；**Kaitai 主仓无 SPDX 许可标识**（各编译器/运行时子仓各自带许可，商用前需按组件核对）；webcrack 只覆盖 JS/打包器场景。
- **适用**：App/前端 API 协议逆向、私有协议研究、文件格式逆向成果工程化、小程序/前端逆向。

### 15. DIE (Detect It Easy) —— 文件/编译器/壳识别
[horsicq/DIE-engine](https://github.com/horsicq/DIE-engine)
- **功能**：识别文件类型、编译器与链接器版本、壳与加密算法，带 GUI 与 CLI。
- **优点**：识别库更新勤（4.0.0 发布于 2026-11-05，当日有提交）；MIT。
- **缺点**：只做"识别"，不做深入分析。
- **适用**：任何逆向工作的第一步（先搞清目标是什么）。

### 16. AI 逆向 Agent（2025–2026 新兴层，2026-11-07 追问补充）

**先回答"reverse-engineering-agent 这个开源项目"**：GitHub 精确名检索（含大小写变体、in:name）**没有发现一个有影响力的同名项目**。命中的同名仓库全部是小项目：最高的 [The-Arabi/Reverse-engineering-agent](https://github.com/The-Arabi/Reverse-engineering-agent) 仅 38★（无描述、无许可声明、2026-08-04 后无提交），其余多为 0★ 个人实验（如 sojiang75-byte 版"解 crackmes 的小 agent（WIP）"、若干韩语/葡语/LangChain 练手仓）。若你指的是其中某一个，请给链接再核实；你更可能想问的是下面这批"AI agent + 逆向"的新兴项目（元数据已核实，2026-11-07）：

| 项目 | ★ / 许可 | 定位（据官方 README） | 活跃度 |
|---|---|---|---|
| [Integuru](https://github.com/Integuru-AI/Integuru) | 4,792 / AGPL-3.0 | "第一个通过逆向平台内部 API 构建无许可集成的 AI agent"：分析浏览器网络请求（HAR）→ 生成调用平台内部端点的可运行 Python 代码。**开源仓只是 v0 快照，新版已转商业站 integuru.com** | 2026-06 后停更 |
| [android-reverse-engineering-skill](https://github.com/SimoneAvogadro/android-reverse-engineering-skill) | 8,673 / Apache-2.0 | Android App 逆向的 Claude Code skill（agent 执行层，非传统工具） | 2026-10-12 有提交 |
| [ctf-skills](https://github.com/ljagiello/ctf-skills) | 3,641 / MIT | 解 CTF 的 agent skills（web / pwn / crypto / 逆向） | 当周有提交 |
| [jshookmcp](https://github.com/vmoranv/jshookmcp) | 2,102 / AGPL-3.0 | "面向 AI agent 的搜索优先逆向工作区"（MCP）：hook 页面、抓网络、反混淆 bundle、反汇编 WASM、插桩进程 | 当周有提交 |
| [Seep-Reverse-Lab](https://github.com/angusdevgo/Seep-Reverse-Lab) | 2,091 / GPL-3.0 | Agent-native 多平台逆向 + CWE-602 客户端授权审计工作台（中英文档） | 2026-11-04 有提交 |
| [cheatengine-mcp-bridge](https://github.com/miscusi-peek/cheatengine-mcp-bridge) | 1,756 / MIT | 把 AI agent 经 MCP 直连 Cheat Engine，自动化逆向/找指针 | 2026-08 有提交 |
| [open-reverselab](https://github.com/LING71671/open-reverselab) | 1,346 / GPL-3.0 | "AI 逆向 Agent & MCP 实验室"：100+ MCP 工具，面向 Claude Code/Codex/OpenCode 等 agent，覆盖 Ghidra/Frida/x64dbg/Rizin、PE/APK/恶意样本/CTF；Sentry 赞助；有中文文档 | 2026-10-21 有提交 |
| [Rikugan（六眼）](https://github.com/buzzer-re/Rikugan) | 707 / MIT | IDA Pro + Binary Ninja 内直接集成多 provider LLM 的逆向 agent | 2026-11-04 有提交 |
| [reverse-engineering-assistant](https://github.com/cyberkaida/reverse-engineering-assistant) | 950 / Apache-2.0 | Ghidra 的 MCP server，把逆向任务交给 agent | 2026-11-03 有提交 |
| 早期/小体量：[era-agent](https://github.com/dav1dngy/era-agent)（49★/MIT，"Evolve & Reverse Engineer Anything"）、[blackbox-re-agent](https://github.com/maosasagawa/blackbox-re-agent)（34★/Apache-2.0，pi coding agent 上的对话式黑盒逆向，支持 apk/.o/.hex/exe）、[Shiyou-Qi/QNX-Agent](https://github.com/Shiyou-Qi/QNX-Agent)（20★/无许可，**DeepSeek Harness 专用**逆向 agents）、ghidra-skill-for-dsh（11★，DSH 的 Ghidra headless 技能） | | | |

名字相近的学习资源（非工具）：mytechnotalent/Reverse-Engineering（15,125★，免费系统教程，覆盖 x86/x64/ARM 等）、wtsxDev/reverse-engineering（10,767★，资源清单）、0xZ0F/Z0FCourse_ReverseEngineering（5,996★，x64 Windows）、alphaSeclab/awesome-reverse-engineering（5,195★）。

**定性**：这是报告主体（传统工具/库）之上的新兴层——把 LLM agent 接到逆向工具（Ghidra/IDA/Binary Ninja/Cheat Engine/Frida），或直接逆向平台内部 API。成熟度普遍低于主体工具：多为 2026 年才创建、单作者或小团队、部分无许可声明（QNX-Agent、The-Arabi 版），且多数依赖 Claude Code 等 agent 平台。选型建议当"效率外挂"而非替代品；AGPL/GPL 系（Integuru、jshookmcp、open-reverselab、Seep）商用集成注意传染性。

### 17. REA（Reverse Engineer Anything）—— 新兴层的头部项目（2026-11-07 追问核实）

[morluto/rea](https://github.com/morluto/rea)：**439,531★ / 108,852 forks**（GitHub 历史最高梯队）、MIT、TypeScript；2026-04-14 创建、当日仍有提交；最新 release `rea-agents-6.8.0`（2026-10-25）。

- **定位**（官方 README 原话）："One MCP for reverse engineering across binaries, applications, and runtime behavior —— See a feature you like. Understand how it works, down to the binary level."：把 agent 接到逆向检查工具链的 **MCP 层**，覆盖原生二进制、JavaScript/Electron 应用、.NET 程序集、网站；207 个 MCP 工具；可调用已装的 Hopper/Ghidra/IDA/Kuna（setup 可经批准代装 Hopper）；分析在本地执行，结论附证据与局限。
- **安装**：`npx rea-agents setup`（npm 包 `rea-agents`）；官网 [rea.tools](https://rea.tools/)（含 Guides/Showcases）；README 有 21 种语言（含简体中文）。
- **官方防伪声明**：README 明确警告"相似仓库名或抄袭的 README 不代表官方下载源"。检索中确实存在描述与官方一字不差的第三方仓（NabilRFG12/Reverse-Engineer-anything，1,222★，GitHub 无 fork 关系），其与官方的关系未核实，建议只从 morluto/rea、rea.tools 或 npm 官方包获取。
- **生态**：leanrea（4,062★，"8KB SKILL.md 替代 REA"——去 MCP 层让 agent 直接跑 asar/otool/nm/jadx/Ghidra/binwalk 等原生工具，附对 REA 6.5.0 的耗时/成本/得分基准）；ERA（era-agent，49★，在 REA 引擎上加工作流层：分析模式/Studio/多 agent/自我改进实验）；REA-Prompts（3,729★）；awesome-reverse-engineer-anything（522★ 与 294★ 两份精选）；Fanqi89/dsh-rea（152★，REA 的 DSH MCP 桥接插件，与 dsh-craft-anything 同一作者）；中文深度调研仓 rea-research（95★）；GUI 前端 rea-ui 等周边。
- **与 craft-anything 的对照**：口号几乎同题（"看懂任意软件，再造一个自己的"）。形态不同：REA 是 TypeScript 编写的 MCP 工具链（不自研反汇编引擎，接现有工具），craft-anything 是纯 Rust 自研引擎的桌面应用+CLI+MCP；DSH 生态中两者由同一作者提供了桥接插件。功能重叠度高、属同一赛道（此为基于双方公开描述的对照，非任何官方说法）。
- **首轮报告为何没收录**：首轮按传统工具类别（反汇编器/调试器/框架名）检索，"rea" 名称过短未进入结果，本次经用户提示定向核实补录。

### 18. reverse-skill 与"逆向技能包"层（2026-11-07 追问核实）

[zhaoxuya520/reverse-skill](https://github.com/zhaoxuya520/reverse-skill)：**44,268★ / 6,588 forks**、MIT、PowerShell；2026-05-13 创建，最新提交 2026-09-22，最新 release v1.0.1（2026-08-08）。

- **定位**（官方 README）："Cybersecurity Skills Router · 逆向技能路由包"——当 AI agent（Claude Code/Codex/Cursor/OpenCode 等）遇到 APK、二进制、前端 JS 加密、CTF 或授权渗透目标时，把它**路由到正确方法论、检查可用工具、执行可复现工作流**（任务 → RULES.md → 路由 → 执行），而不是让 agent 猜命令。README 专门提供 README_AI.md 供 agent 自读；中文文档齐全，另有项目网站与在线教程。
- **性质**：与 REA（§17，工具链 MCP）不同——它是"方法论路由包"（SKILL/RULES 集合），本身不提供逆向引擎，而是指挥 agent 用现有工具按规范流程干活；定位为授权渗透测试/安全研究，MIT。
- **同类技能包生态**（已核实元数据）：P4nda0s/reverse-skills（2,349★，Claude Code 逆向技能插件，**无许可声明**，2026-05-06 后停更）、WhiteNightShadow/hello_js_reverse_skill（1,403★，JS 逆向全链路）、dhicoc/dsh-reverse-skill（332★，**88 个 SKILL.md 打包成 DeepSeek Harness Cordis 插件**）、cellebrite-labs/ghidra-rpc（397★，Cellebrite 出品的 Ghidra agentic skill）、r0crawl_skills（364★，web/Android/iOS/Frida 技能库）、android-reverse-engineering-skill（8.7k★，见§16）。
- **定性**：AI 逆向生态的第三层——"技能/方法论层"（SKILL.md 路由包），介于传统工具（第一层）与 REA 类工具链（第二层）之间，本层更新快、以中文社区为重要策源地。选型提示：reverse-skill 为 MIT 可直接采用；无许可声明的技能包商用前需向作者确认授权。

## 三、场景选型速查

| 场景 | 推荐组合 |
|---|---|
| Windows 软件/游戏逆向 | DIE → x64dbg（动态）+ Ghidra（静态） |
| 恶意软件分析 | Ghidra + Cutter/Vivisect + capstone |
| Android App 逆向 | jadx + Apktool + Frida；批量评估用 MobSF |
| iOS App 逆向 | Frida + LIEF |
| 固件 / IoT | binwalk（提取）→ FirmAE（仿真）→ Ghidra（分析） |
| 协议 / API 逆向 | mitmproxy + Wireshark，格式固化用 Kaitai |
| CTF / pwn | pwndbg 或 GEF + Ghidra + angr |
| 自研自动化/大规模分析 | capstone + Unicorn/Qiling + LIEF（+ angr 做符号执行） |
| 前端 / 小程序 JS | webcrack + mitmproxy |
| AI/agent 辅助逆向 | **REA**（`npx rea-agents setup`，MCP 工具链）或 **reverse-skill**（44.3k★，方法论路由包）；Rikugan / open-reverselab（接 Ghidra/IDA）+ jshookmcp（网页/WASM）；平台内部 API 集成用 Integuru |
| 应用级"复刻一个自己的" | craft-anything（见上一轮报告） |

## 四、与 craft-anything 的关系

上述工具是**二进制/协议/格式级**逆向（看清代码与数据）；craft-anything 是**应用级**逆向（看清整个软件如何工作并让 agent 复刻）。二者互补：craft-anything 的 Deep 模式自带反汇编/反编译引擎，并可调用已安装的 Ghidra——即它与 Ghidra 是上下游集成关系，不是替代关系。另外，DSH 生态也已出现专用逆向 agent（QNX-Agent、ghidra-skill-for-dsh，见第 16 节）。

## 五、总体观察

1. **最成熟、最万能**：Ghidra（几乎任何静态逆向场景的默认答案）+ Frida（动态默认答案）。
2. **最活跃**（当日仍有提交）：Ghidra、radare2、angr、LIEF、DIE、pwndbg、Wireshark、MobSF、jadx、Apktool。
3. **活跃度下降需留意**：RetDec（2026-05 后无提交）、binwalk（新 release 停在 2024-10，主分支有更新）、GEF（2026-08）、webcrack（2026-07）、FirmAE（2026-06）。
4. **许可注意**：Ghidra/jadx/Apktool/LIEF/Vivisect/FirmAE/binwalk/DIE/webcrack/mitmproxy/pwndbg/GEF/angr 为 MIT/Apache/BSD 系，商用友好；Unicorn/Qiling/Wireshark/MobSF/rizin/Cutter 为 GPL/LGPL 系，**集成时注意传染性**；radare2/x64dbg/Frida 为自定义许可文件（GitHub 未识别 SPDX，具体条款未核实）；capstone 主仓许可未识别。

## 六、未查到 / 未核实的信息

1. radare2、x64dbg、Frida 的许可为自定义文件，GitHub 未映射标准 SPDX，具体条款本次未核实。
2. capstone 主仓 GitHub 许可字段为空、LICENSE 内容本次未获取成功；Kaitai 主仓无 SPDX（子组件各自许可）。
3. angr 在 GitHub 上无标记为 latest 的正式 release（/releases/latest 返回 404）。
4. "objection"（Frida 的移动端封装）未能核实其官方仓库，未收录。
4a. **"reverse-engineering-agent" 同名核实（2026-11-07 追问）**：精确名检索未发现有影响力的同名项目；同名仓库均为小项目（最高 38★、多数 0★、部分无许可/无描述），详见第 16 节。
4b. **REA 核实（2026-11-07 追问）**：morluto/rea 439,531★/MIT 已核实（第 17 节）；NabilRFG12/Reverse-Engineer-anything 与官方无 fork 关系、是否官方拷贝未核实（官方 README 自带防伪警告）；leanrea 对 REA 的基准数据为其官方 README 自述，未独立复测。
5. 各工具功能描述来自官方文档的通用说法，未逐一实机复测；star 数等为 2026-11-07 GitHub API 快照。
6. 闭源商业工具（IDA Pro、Binary Ninja）按"非开源"排除，不提供其数据对比。

## 七、证据文件

`work/re-survey/meta.tsv`（24 个仓库的 GitHub API 元数据快照），Release 信息见各项目 Releases 页（本报告正文已标注版本与日期）。
