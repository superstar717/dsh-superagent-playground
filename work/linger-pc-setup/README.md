# Linger PC 准备工作（RTX 3060 12G / 16→64GB / E:HDD + F:SSD）

> 工单：`zhihu-replicate-check-889907b3861a`（2026-11-21）
> 触发：「我有一台PC机 显卡是3060 12G显存 内存现在是16G 过两天我会升级到64G 先做准备工作吧 你应该可以通过tailscale直接连接控制吧 先把准备工作做好 PC机的E盘是一块机械硬盘 F盘是一块固态硬盘」

## 现状（我这边已核实）

| 项 | 结果 | 来源 |
|---|---|---|
| Tailscale 互通 | PC 节点 `pc-20230915xmxx` = `100.80.147.68`，`tailscale ping` 38ms | 本机实测 2026-11-21 |
| PC 的 22 端口 | **OpenSSH_for_Windows_9.5 已开**，但只接受 publickey/password，我没有凭据 | 本机实测 |
| PC 的 3389 / 5985 | 关闭（RDP、WinRM 不可用） | 本机实测 |
| Tailscale SSH | 未启用（22 端口是原生 OpenSSH 的 banner，不是 tailscaled 的 SSH 服务） | 本机实测 |
| 目标硬件对照 | PolyStrata 官方：Qwen3.8-Flash-Next 需 **NVIDIA RTX 20–50 系、12GB+ 显存、32GB+ 内存（64GB 可跑全部尺寸）、约 80GB 磁盘**，Windows/Linux | [PolyStrata README](https://github.com/simplexai-labs/PolyStrata) |
| 当前瓶颈 | 16GB 内存不足以跑 125B（需 ≥32GB）；64GB 到位后可用 | 同上 |

## 现在需要你做的一步（30 秒）

> 若上面的 `setup.ps1` 是在**非管理员**窗口跑的（普通用户文件写了、但 Administrators 组的 `C:\ProgramData\ssh\administrators_authorized_keys` 没写），SSH 会一直 Permission denied。补救只需一条（会自动请求 UAC，点「是」即可）：
>
> ```powershell
> irm http://100.66.36.4:8000/fix.ps1 | iex
> ```
>
> `fix.ps1` 提权后写 `administrators_authorized_keys`、修 ACL，并把诊断 JSON POST 回本机暂存服务（我据此判断 sshd 配置是否还要改）。

在 PC 上用**管理员** PowerShell 跑：

```powershell
irm http://100.66.36.4:8000/setup.ps1 | iex
```

它会做三件事（脚本全文见本目录 `setup-access.ps1`，可先看）：把本机公钥写进
`%USERPROFILE%\.ssh\authorized_keys`（管理员账户同时写
`C:\ProgramData\ssh\administrators_authorized_keys`）、修 ACL、打印 `whoami`。
之后我就能用 SSH 接管，不需要密码。

> 两个备选入口（任一可用即可）：
> 1. GitHub raw（不依赖我这台 Mac 在线）：
>    `irm https://raw.githubusercontent.com/superstar717/dsh-superagent-playground/51bae352459be77ee5a031ef6d3b735ea1d7ab22/work/linger-pc-setup/setup-access.ps1 | iex`
> 2. 直接把下面这段粘进管理员 PowerShell：
>
> ```powershell
> $k='ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIB6VFxQwzU/oa+5OazDXuGEQViGarvVhXN53uJClq+SP pc-agent@macbook-pro-3'
> $u="$env:USERPROFILE\.ssh"; New-Item -ItemType Directory -Force $u|Out-Null
> Add-Content "$u\authorized_keys" $k -Encoding ascii
> icacls "$u\authorized_keys" /inheritance:r /grant:r "$($env:USERNAME):F" /grant:r "SYSTEM:F"|Out-Null
> if (([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
>   $a="$env:ProgramData\ssh\administrators_authorized_keys"
>   Add-Content $a $k -Encoding ascii
>   icacls $a /inheritance:r /grant:r "SYSTEM:F" /grant:r "Administrators:F"|Out-Null
> }
> whoami
> ```

## 准备工作分阶段（我做，需你在场时配合重启/授权）

| 阶段 | 内容 | 需要谁 | 验收 |
|---|---|---|---|
| P0 访问 | 装公钥、SSH 接管、`prep.ps1` 体检（系统/驱动/磁盘/电源/长路径） | 你跑一条命令 | 我能 `ssh` 登录并读到 `prep.json` |
| P1 底座 | 电源改高性能、AC 不休眠、长路径开启、建 `F:\AI\{models,logs}` 与 `E:\AI\backup`；确认 **NVIDIA 驱动 ≥580**（PolyStrata 官方要求） | 我 | 报告全绿；F: 剩余 ≥90GB |
| P2 推理 | 装 PolyStrata（Windows 免编译 zip），选 Qwen3.8-Flash-Next **最小量化**（Q2_0，约 39–70GB，按磁盘挑），模型放 **F: SSD**；起 OpenAI 兼容 API（默认 `127.0.0.1:8080`，`GET /v1/status` 可查状态）。国内下载慢时先 `set HF_ENDPOINT=https://hf-mirror.com`（官方 INSTALL.md 给的镜像） | 我（下载 39–70GB，可能要数小时） | `http://127.0.0.1:8080` 可聊天；实测 tok/s、首 token 时间 |
| P3 Linger | 装 Linger Desktop 0.1.6（Windows x64，自带 server/PG，无需 Docker）；Local model 或 **BYOK 指向 P2 的本地 API** | 我 + 你首次授权 | 能读本机邮件/日历（飞书需另配），夜间 Wiki 生成 |
| P4 基准 | 对照原文 45.5 tok/s（12GB 3060 + 64GB）：同模型同量化跑 3 次短提示 + 1 次长上下文 | 我 | 有本机实测数字，写进报告 |

**顺序理由**：先把"本地 125B"这条最不确定的链路跑通（P2），再装 Linger（P3）。这样即使 Linger 的 Windows 安装器有坑（已知 issue #394：CUDA 检测/安装目录权限），也不影响验证原文核心卖点；Linger 也可以用 BYOK 直接吃 PolyStrata 的本地 API，绕开它自带模型安装器。

## 磁盘规划（按你给的 E/F 盘）

| 盘 | 用途 | 说明 |
|---|---|---|
| **F: SSD** | `F:\AI\models`（GGUF 权重）、`F:\AI\logs` | PolyStrata/Strata 会从模型文件按需分页读取专家，放 SSD 明显影响首 token 与长上下文速度；40–80GB 空间 |
| **E: HDD** | `E:\AI\backup`（安装包、旧量化、日志归档） | 顺序读写够用，不放运行中的权重 |
| C: | 系统 + Linger 应用（约 1–2GB） | 安装路径建议短路径，避免 issue #394 的权限问题 |

## 已在本机备好的安装包（Tailscale 内网直取，避免 GitHub 慢）

| 文件 | 大小 | 地址 |
|---|---|---|
| Linger Desktop 0.1.6（Windows x64 setup） | 459MB | `http://100.66.36.4:8000/Linger-0.1.6-windows-x64-setup.exe` |
| PolyStrata 0.1.45-poly.10（Windows x64 zip） | 170MB | `http://100.66.36.4:8000/strata-poly-windows-x64-3a95fb8cdef41631.zip` |
| 体检脚本 | — | `http://100.66.36.4:8000/prep.ps1` |
| 装公钥脚本 | — | `http://100.66.36.4:8000/setup.ps1` |

> 服务只绑定本机 Tailscale IP（`100.66.36.4:8000`），不暴露到局域网/公网；本机防火墙当前关闭，仅 tailnet 内可达。

## 风险与已知坑

1. **NVIDIA 驱动必须 ≥580**（PolyStrata 官方门槛），P1 会先查；低于 580 需要先更新驱动（可能要重启）。
2. **16GB 现在跑不了 125B**：PolyStrata 要求 ≥32GB，64GB 才"跑全部尺寸"；现在只做下载与配置，等内存到位再跑。
3. **首次 token 慢**：官方自述 12GB+32GB 档 "first token after about 3 minutes"；SSD 上预热后才有稳态 tok/s。
4. **Windows 安装器坑**：Linger issue #394（CUDA 检测、安装目录权限）；对策：短路径、管理员运行、先装 NVIDIA 驱动、必要时用便携版 zip。
5. **Defender 实时扫描**会拖慢 39–70GB 权重的读取；是否给 `F:\AI` 加排除由你拍板（默认不动安全设置）。
6. **电源/休眠**：长下载/长生成会被睡眠打断，P1 会改成 AC 不休眠。
7. **Cua 桌面控制**在 Windows 上需要额外授权（屏幕/输入），P3 再开。

## 脚本说明

- `setup-access.ps1`：只装公钥 + 打印身份，可重复执行；不做其它改动。
- `prep.ps1`：默认**只体检**；加 `-Apply` 才改电源/长路径/建目录（管理员运行）。输出 `F:\AI\logs\prep-<时间>.json` 供我读取。
- `bench.ps1`：装好模型后量端到端 tok/s（短提示 3 次 + 8k token 长提示 1 次），报告写 `F:\AI\logs\bench-*.json`。
- `pc-bootstrap.sh`（Mac 侧）：`./pc-bootstrap.sh -u <Windows用户名> --apply`，一条命令完成 SSH 连通检查、上传脚本、只读体检、UAC 提权跑底座、拉回 JSON。
