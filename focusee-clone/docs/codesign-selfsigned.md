# 自签证书签名：让 TCC 授权跨重打包稳定

## 为什么

macOS 的 TCC 授权（屏幕录制、摄像头、麦克风等）按「应用身份 = Bundle ID + 代码签名身份」记忆。
本应用从 Electron 壳打包而来，此前用 **ad-hoc 签名**（`codesign --sign -`）：

- ad-hoc 签名没有证书， designated requirement 退化为 **CDHash 绑定**；
- 每次重打包（哪怕只改一行 js）CDHash 都变 → macOS 视为全新应用 → **授权必掉**，
  需要用户再去系统设置里关→开重授一次。

改用**固定自签证书**签名后，designated requirement 锚定在证书上
（`certificate root = H"<证书哈希>"`），只要证书不变、Bundle ID 不变，重打包/就地更新
都不再掉授权。**证书只需创建+信任一次**（本机已于 2026-11-17 完成下述全部步骤）。

## 本机现状（已完成，无需重做）

| 项 | 值 |
|---|---|
| 签名身份 | `FocuSee Clone Dev`（SHA-1 `75ADE055E67561106A004EAF38E55EC89E8CD177`） |
| 位置 | login keychain，user 域信任 codeSign 用途 |
| 有效期 | 至 2036-11（3650 天） |
| 备份 | `~/.local/focusee-clone-codesign/`（key/cer/p12 + ext.cnf） |

`package-app.sh` 默认用此身份签名；身份不存在时脚本报错并给出指引，
可用 `CODESIGN_IDENTITY=-` 显式回退 ad-hoc（会丢授权，仅临时救急）。

## 重建步骤（keychain/备份丢失时）

```bash
cd ~/.local/focusee-clone-codesign

# 1) 重新生成（或直接用备份的 key/cer）
openssl genrsa -out focuseeclone-dev.key 2048
openssl req -new -x509 -key focuseeclone-dev.key -out focuseeclone-dev.cer \
  -days 3650 -subj "/CN=FocuSee Clone Dev/O=FocuSee Clone Project/C=CN" \
  -config ext.cnf -extensions v3_cs

# 2) 导入 login keychain（-T 预授权 /usr/bin/codesign 使用私钥）
security import focuseeclone-dev.key -k ~/Library/Keychains/login.keychain-db -T /usr/bin/codesign
security import focuseeclone-dev.cer

# 3) 信任（user 域、仅 codeSign 用途）
security add-trusted-cert -p codeSign focuseeclone-dev.cer

# 4) 验证
security find-identity -v -p codesigning   # 应列出 "FocuSee Clone Dev"

# 5) 第一次签名时若弹出「codesign 想要访问钥匙串密钥」对话框：
#    点【始终允许】(Always Allow) —— 一次性，之后所有 codesign 静默执行。
```

ext.cnf（已随备份保存）：

```ini
[req]
distinguished_name = dn
[dn]
[v3_cs]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature
extendedKeyUsage = codeSigning
subjectKeyIdentifier = hash
```

注意：OpenSSL 3 默认导出的 p12（AES/SHA-256 MAC）`security import` 会报
`MAC verification failed`，改导入 PEM key + cer 两件套即可（上面步骤 2 的写法）；
或用 `openssl pkcs12 -export -legacy` 重导出后再导入。

## 切换签名的一次性成本

已装的 `/Applications/FocuSee Clone.app` 从 ad-hoc 换成证书签名的**那一次**，
签名身份变了，屏幕录制/摄像头/麦克风会掉一次授权（系统会重新弹授权请求，
或到 系统设置 → 隐私与安全性 里把对应开关关→开）。**重授这一次之后，
以后无论怎么重打包都不再掉。**

## 验证方法

```bash
# 两次独立打包（或就地改一个 Resources 文件后重签），DR 应完全一致：
codesign -d -r- "/Applications/FocuSee Clone.app" | tail -1
# 期望：designated => identifier "com.focuseeclone.app" and certificate root = H"75ade055…"
# ad-hoc 时代这里是 cdhash H"…"，每次打包都变。
```
