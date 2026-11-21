# DEPLOY-NOTES — deck-ship 交付强制链（工单 deck-ship-enforce-860f53caf540）

日期：2026-11-14（Asia/Shanghai）
结论：**已落地并验证**。`deck-lint` / `cite-check` 不再靠"记得跑"——交付目录只能经
`deck-ship` 写入，项目一条链 `work/build/ship_d.sh` 的退出码就是"能不能发货"，交付目录带
`*.ship-manifest.json` 可核验；正/负路径都有实测证据。

---

## 1. 落地了什么

| 组件 | 路径 | 作用 |
|---|---|---|
| 发货门禁 | `~/.local/deck-ship/deck_ship.py`（入口 `~/.local/bin/deck-ship`） | lint 0 FAIL + 字体白名单 + cite 门禁全过才原子复制；manifest 记录哈希/gate 计数/来源哈希；被拦 exit 1 且目录不变 |
| 版式检查 | `~/.local/deck-lint/deck_lint.py` | 页数/16:9/越界/重叠/字体/字号/讲稿/包体积；`--json` 供门禁消费 |
| 引用检查 | `~/.local/cite-check/cite_check.py` | 新增 `--json`、`--fail-on-missing`；MISSING 可被门禁阻塞 |
| 项目一条链 | `~/src/ppt-recon-876f22c1685a/work/build/ship_d.sh` | build → render → dump → lint/cite → ship |
| 构建期门禁 | `work/build/build_d.py` 末尾 | 保存后自动 deck-lint（`--expect 16 --min-notes 300`），FAIL 则构建失败 |
| 引用语料 | `work/build/authority/` | 期刊 OCR + 原稿文本 dump + 化验单截图转写表（三源） |
| 白名单 | `work/build/cite-allow.txt` | 5 条派生值/日期/OCR 误识，每条带原因；无原因 fail-closed |
| 自测 | `~/.local/deck-ship/selftest.py`（13 项）+ 项目 `ship_d_selftest.sh` | 正/负路径 + blocked-means-empty + verify-only |

## 2. 验证证据

### 2.1 工具自测（13/13，2026-11-14）

```
PASS  positive: good deck is SHIPPED with manifest and matching hash
PASS  negative: wrong --expect is BLOCKED and dest stays empty
PASS  negative: short notes is BLOCKED and dest stays empty
PASS  negative: wrong font is BLOCKED (catches shipping the QA build)
PASS  negative: unsourced number is BLOCKED and dest stays empty
PASS  positive: sourced number passes cite gate
PASS  positive: allowlisted missing claim passes and is recorded
PASS  negative: allowlist without reason is BLOCKED
PASS  companion: renamed companion lands in dest and manifest
PASS  verify-only: deck-only verify keeps recorded companion, tamper is BLOCKED
PASS  verify-only: adopts identical file, rejects tampered file
PASS  dry-run: gates run, nothing copied, no manifest
PASS  overlap: WARN is shipped+recorded (blocking is reserved for FAIL)
13 passed, 0 failed
```

### 2.2 全链 e2e（build → render → lint/cite → ship）

对真实 D 版跑到 `/tmp/ship-e2e-ok`（交付目录未动）：

```
deck-ship: SHIPPED — 2 file(s) at /tmp/ship-e2e-ok
  deck      copied   …-D版.pptx  19.53 MB
  companion copied   …-D版.pdf   18.21 MB
  lint: 0 fail / 2 warn  (16 slides)
  fonts: ['微软雅黑'] (required ['微软雅黑'])
  cite: 98 claims, 5 allowed, 0 blocking
  manifest: /tmp/ship-e2e-ok/…-D版.ship-manifest.json
```
- 重建产物与用户已验收的 D 版**内容逐项一致**（124 个 zip entry 的 sha256 全部相同，仅 zip 时间戳不同）。
- 交付 PDF 16 页 / 13.33×7.5in。
- manifest 记录：`status/at/source sha256/files/lint 明细/stats/fonts/cite 计数+白名单理由/来源文件 sha256/context`。

### 2.3 负路径（"该拦时真拦"）

```
$ bash work/build/ship_d.sh --dest /tmp/negative --no-build --no-render --expect 17
deck-ship: BLOCKED
  lint: 1 fail / 3 warn  (16 slides)
    FAIL -      slide-count    expected 17 slides, got 16
  cite: 98 claims, 5 MISSING (5 allowlisted, 0 blocking)
  destination unchanged: /tmp/negative
== RESULT: BLOCKED (deck-ship exit 1) — delivery directory untouched
$ echo $?        # 1
$ ls -A /tmp/negative | wc -l    # 0
```
- 无源数字（草稿含 97.3%，三源无此数）→ exit 1、交付目录 0 文件。
- 字体白名单：把 Heiti SC QA 构建当交付件 → BLOCKED。
- 白名单缺原因 → 判 gate 错误（fail-closed），不是静默放行。

### 2.4 既有交付核验（含一次真实内容修订的发货）

- 对 `~/project/F240ppt` 的 D 版跑 `--verify-only`：`VERIFIED`；lint 0 fail / 2 warn；
  cite 98 claims / 5 allowlisted / 0 blocking；manifest 写入交付目录。
- **真实二次发货（01:34，另一会话完成用户的内容修订后）**：同一门禁对修订版（多图，20.19 MB）
  执行全链 → `SHIPPED`，2 文件（pptx + pdf）哈希与 manifest 记录一致，lint 0 fail / 2 warn，
  字体仅微软雅黑，cite 98 claims / 5 allowlisted / 0 blocking，PDF 16 页 13.33×7.5in。
  这是"机制不是摆设"的直接证据：内容变了，门禁照跑、manifest 照写。

## 3. 并发覆盖事故（如实记录）

本工单落地期间，**另一会话（ppt-recon 工单，处理用户后续的内容修订）**同时在本机操作，
一度自建同名 shell 版 `deck-ship` 并 `ln -sf` 覆盖了本工单入口，还用简化版覆盖了
`work/build/ship_d.sh`，导致本工单 01:21 的 full e2e 假失败（rc=0 但无 manifest/PDF）。
对方随后把链接指回 `~/.local/deck-ship/deck_ship.py`、删除自建 wrapper，并按本工单的
selftest 接口重建 `ship_d.sh`；复跑 `ship_d_selftest.sh --fast` = 5/5 PASS，对真实交付目录
全链 SHIPPED + `--verify-only` = VERIFIED。

**教训**：共享入口（`~/.local/bin/*`、项目 ship 脚本）在并发工单下会被互相覆盖——动手前查
`readlink`/mtime/日志，覆盖后必须复跑对方验收。已录入 `~/.dsh/LESSONS.md` **E138**。
本工单最终以"运行时工具 + 项目链 + 回归自测"三者一致为准，不依赖任何单次日志。

## 4. 边界与未解决

1. **不是宿主 hook**：约束"走这条命令的发货"，不能物理阻止手工 `cp`。约束力 = build 期 lint +
   AGENTS 规则 + manifest 可核验。加 DSH hook 需"是否 PPT 交付"的启发式且要重启宿主（E127），
   收益低于误伤成本，故不做。
2. **cite 是字符串级**：FOUND ≠ 语义相同（E136 的 72h）；MISSING 也可能是 OCR 误识——本项目
   `12h` 在原文被 OCR 成 `6~)121`，已进白名单并注明**待人工按 PDF 核对**。
3. **重叠检测是 WARN 阈值**（>0.12in² 且 >12% 较小框），仍需人工抽看改过坐标的页。
4. **字体策略**：交付 pptx 仅微软雅黑；PDF 由 Heiti SC QA 构建渲染（macOS LibreOffice 缺微软雅黑），
   字体声明不同属历史做法。
5. 另一会话正在做内容修订，交付目录的最终 manifest 以它最后一次 ship/verify 为准；
   本机制对修订后的稿子仍然生效（gate 在发货时重跑）。

## 5. 回滚

- 运行时：`rm ~/.local/bin/deck-ship`（保留源码目录即可，不删除历史）；项目把 `ship_d.sh` 挪走
  即回到手工流程（不推荐；AGENTS 会指回来）。
- 仓库：revert 对应 PR 即可；工具本身无外部依赖（python-pptx 已有）。
