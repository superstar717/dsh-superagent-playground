# 项目复盘：换自签证书签名稳定 TCC 授权（工单 ba87a0f03e18，2026-11-17）

源触发：飞书群「换自签证书签名」（2026-11-17 02:58，消息 om_x100b60816a9430a0b4f750f603bae7f）。

## 一、最终事实（验证状态：全部实证）

**问题根因**：`/Applications/FocuSee Clone.app` 一直是 ad-hoc 签名，TCC 授权
（屏幕录制等）绑定在 `designated => cdhash H"2919b71643a7c106fde5d2815afe8bba85a2bfaf"`。
ad-hoc 没有稳定身份，每次重打包 CDHash 必变 → macOS 视为全新应用 → 授权必掉。
此前只能靠「就地更新、不重签」绕过（LESSONS 已记录的权宜之计）。

**本次改动**（均已验证）：

| 项 | 结果 |
|---|---|
| 自签证书 | `FocuSee Clone Dev`（SHA-1 `75ADE055E67561106A004EAF38E55EC89E8CD177`），Code Signing EKU，有效期至 2036-11 |
| Keychain 信任 | login keychain，user 域 trustRoot + codeSign 用途；`security find-identity -v -p codesigning` = 1 valid |
| 备份 | `~/.local/focusee-clone-codesign/`（key/cer/p12/ext.cnf，重建步骤见 `focusee-clone/docs/codesign-selfsigned.md`） |
| 打包脚本 | `package-app.sh` 默认用证书签名；身份缺失报错+指引；`CODESIGN_IDENTITY=-` 显式回退 ad-hoc；签名后 `--verify --deep --strict` 自检 |
| 已装包切换 | `/Applications/FocuSee Clone.app` 已就地重签为证书签名（内容未动，strict verify 过） |

**核心证据（DR 三包一致 = 授权跨重打包稳定）**：

```
BEFORE（ad-hoc 时代）: designated => cdhash H"2919b716…"（每包都变）
AFTER 三个不同来源的包 DR 完全一致（逐字）：
  全新打包 build/FocuSee Clone.app   → identifier "com.focuseeclone.app" and certificate root = H"75ade055…"
  改内容+重签的副本（模拟就地更新）  → 同上
  /Applications 切换后的已装包       → 同上
codesign --verify --deep --strict 三者全过；旧实例（adhoc 身份）quit 正常退出。
```

**剩余一次性成本（人的动作，做完就是永久）**：
1. 下次启动应用时，屏幕录制/摄像头授权会重新要一次（屏幕录制：系统设置→隐私与安全性→
   屏幕录制，关→开+重启应用；摄像头：直接点允许）。**重授这一次之后，重打包永远不再掉。**
2. 钥匙串每次签名还会弹「codesign 想要访问钥匙串密钥」——点一次**【始终允许】**即根治
   （今晚点的都是「允许」，仅当次有效，所以每包都弹）。

## 二、做得对的

1. 开工先检索 LESSONS，直接命中「ad-hoc 重打包掉 TCC 授权」既有教训，根因一步到位；
2. 证书材料落常驻路径 `~/.local/focusee-clone-codesign/` 并附重建步骤，工单目录可删经验不丢；
3. 打包脚本保留 ad-hoc 显式回退通道（`CODESIGN_IDENTITY=-`），默认路径失败报错+指路，不静默降级；
4. 验证设计最小化弹窗次数：改内容重签 + 已装包切换合并进一次 codesign 调用。

## 三、犯过的错 / 摩擦

1. OpenSSL 3 默认 p12（AES/SHA-256 MAC）`security import` 报 MAC verification failed（密码正确也报）
   → 绕路 PEM key+cer 两件套解决（LESSONS E174）；
2. 误信 `security import -T /usr/bin/codesign` 能免弹窗——实际每个新 codesign 进程仍弹
   （LESSONS E175），一次挂起 2m33s；
3. 测试性 quit 关掉了用户开着的旧实例（属预期：旧实例是 adhoc 身份，重开才走新签名），
   但事先未说明；下次先讲再做；
4. 空密码试探 `set-key-partition-list` 白试一次（无害，可凭「登录钥匙串必有密码」直接跳过）。

## 四、如果重来会怎么做

1. 第一条消息就告知用户「会弹 N 次钥匙串授权框，请每次点【始终允许】」；
2. 证书导入直接走 PEM 两件套，不走 p12；
3. 弹窗等待期只做无签名依赖的工作（本次实际已如此，保持）。

## 五、仍未解决

1. **弹窗根治**：等用户点一次「始终允许」（未来 CI 场景可配钥匙串密码跑
   `security set-key-partition-list -S apple-tool:,apple:`）；
2. `ship-gate.sh`（在未合入 main 的分支）落地时确认走 `package-app.sh` 打包即可自动继承
   证书签名；若它自行打包需对齐同一身份；
3. OpenSSL 3 与 macOS p12 兼容性根因未深究（导入层已绕过，不影响使用）。
