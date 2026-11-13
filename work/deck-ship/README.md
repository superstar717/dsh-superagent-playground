# deck-ship — PPT/演示文稿交付强制链

> 缘起：`deck-lint` / `cite-check` 建成后仍只是"建议"——没有 hook、build 也没调用，下一轮会话完全可以
> 手工 `cp` 把稿子放进交付目录。**检查自动化 ≠ 强制落地**（LESSONS E135–E137）。本目录把检查接到
> 交付的唯一路径上：跑不过门禁，交付目录一个字节都不会变。

## 组成

| 文件 | 作用 |
|---|---|
| `deck_ship.py` | 门禁式发货：`deck-lint` 0 FAIL + 字体白名单 + cite 门禁全过才复制，原子写入并产出 `*.ship-manifest.json`；被拦则退出码 1、目标目录不变 |
| `deck_lint.py` | 版式自检（页数/16:9/越界/文本框重叠/字体/字号/讲稿/包体积），`FAIL` 阻塞 |
| `cite_check.py` | 数字回原文：`--json` 给程序用，`--fail-on-missing` 可直接当门禁用；`FOUND` 只代表字符串存在，语义仍需人判断 |
| `deck_text.py` | 把 pptx 的正文/表格/备注 dump 成文本，作为 cite 门禁的 draft |
| `ship_d.sh` | 项目一条链：build → render → dump → gates → ship（F240ppt 实例，复制后改三处配置） |
| `selftest.py` | 13 项正/负自测；CI 跑同一份 |
| `../.github/workflows/deck-ship-selftest.yml` | 入库回归门禁（PR/推送触发） |

## 用法

```bash
# 只验不发货（先看门禁结果）
~/.local/bin/deck-ship "out/D版.pptx" /tmp/试发 \
  --expect 16 --min-notes 300 --allow-bleed --require-font 微软雅黑 \
  --cite-draft ship/deck-text.txt \
  --source authority/guideline-OCR.md --source authority/original-deck.txt \
  --source authority/lab-reports.md --cite-allow cite-allow.txt \
  --dry-run

# 正式发货（全部通过才复制；manifest 落在交付目录）
~/.local/bin/deck-ship "out/D版.pptx" "/交付目录" ... 

# 只核验交付目录里的文件是否仍与来源一致（并补写 manifest）
~/.local/bin/deck-ship "out/D版.pptx" "/交付目录" ... --verify-only

# 项目一条链
bash work/build/ship_d.sh --dest "/交付目录"
```

退出码：`0` SHIPPED/VERIFIED/WOULD-SHIP，`1` BLOCKED（交付目录不变），`2` 用法/IO 错误。

## 门禁语义（不要放宽）

1. **lint**：任一 `FAIL` 即 BLOCKED；WARN 放行但写进 manifest（例如"看起来相邻"的文本框重叠）。
2. **字体**：`--require-font` 是白名单**且**必须出现——它专门拦"把 QA 字体构建误当交付件"。
3. **cite**：草稿里每个"数字+单位"必须命中 `--source`，否则要进 `--cite-allow` 并写原因；
   没有原因的白名单行直接判 gate 错误（fail-closed）。stale 条目会列在 manifest 里，收尾清理。
4. **原子性**：先写同目录临时文件、校验 sha256、再 `os.replace`；被拦时不产生临时文件残留。
5. **manifest**：状态、文件哈希、lint 明细/统计、cite 计数与白名单理由、来源文件哈希、context。
6. **不许删门禁换速度**：`--no-build/--no-render` 只跳过上游工序，不跳过任何门禁。

## 本地安装与仓库副本的关系

- 运行时（唯一权威）：`~/.local/deck-ship/deck_ship.py` + `~/.local/bin/deck-ship` 软链；
  `~/.local/deck-lint/deck_lint.py`、`~/.local/cite-check/cite_check.py`。
- 本目录是**归档 + CI 副本**（工单目录会删，仓库留证）。改运行时后要同步到这里，否则 CI 测的是旧版。
- 归档副本不含任何病例/患者数据：authority 语料与 manifest 只留在本机项目目录。

## 测试

```bash
python3 work/deck-ship/selftest.py        # 13 项：正/负/白名单/字体/companion/verify-only/dry-run
```

F240ppt 项目另有 `work/build/ship_d_selftest.sh`（e2e：全链 SHIPPED + `--expect 17` BLOCKED 且目录为空 +
无源数字 BLOCKED + verify-only）。证据与限制见 [DEPLOY-NOTES.md](DEPLOY-NOTES.md)。

## 已知边界（如实）

- 本机制**不是宿主 hook**：它约束"走这条命令的发货"，不能物理阻止有人绕开命令手工 `cp`。
  约束力来自三处：build 脚本自带 lint、AGENTS 规定交付只走 ship、manifest 可核验。加 DSH hook 需要
  "判断这是不是 PPT 交付"的启发式且改 hooks.json 要重启宿主（LESSONS E127），收益低于误伤成本，故不做。
- cite 门禁是**字符串级**："FOUND" 不代表语义相同（E136 的 72h 陷阱）；`MISSING` 也可能是 OCR 误识
  （本项目 12h 即如此，白名单必须写原因并留待人工复核）。门禁把"写没写来源"变成必答题，不替代人读原文。
- `deck_lint` 的文本框重叠阈值（>0.12in² 且 >12%）是经验值，WARN 仍需人工看一眼。
