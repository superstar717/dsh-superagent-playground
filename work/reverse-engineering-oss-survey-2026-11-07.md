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
| 应用级"复刻一个自己的" | craft-anything（见上一轮报告） |

## 四、与 craft-anything 的关系

上述工具是**二进制/协议/格式级**逆向（看清代码与数据）；craft-anything 是**应用级**逆向（看清整个软件如何工作并让 agent 复刻）。二者互补：craft-anything 的 Deep 模式自带反汇编/反编译引擎，并可调用已安装的 Ghidra——即它与 Ghidra 是上下游集成关系，不是替代关系。

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
5. 各工具功能描述来自官方文档的通用说法，未逐一实机复测；star 数等为 2026-11-07 GitHub API 快照。
6. 闭源商业工具（IDA Pro、Binary Ninja）按"非开源"排除，不提供其数据对比。

## 七、证据文件

`work/re-survey/meta.tsv`（24 个仓库的 GitHub API 元数据快照），Release 信息见各项目 Releases 页（本报告正文已标注版本与日期）。
