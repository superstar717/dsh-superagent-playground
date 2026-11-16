# authority/ — 数字回原文核对用的权威语料

cite-check 需要"来源文件"才能把稿子里的数字逐条对上。本目录放三份**只读**语料，
`ship_d.sh` 每次发货都把稿子文本 dump 出来与它们比对。

| 文件 | 来源 | 权威性 |
|---|---|---|
| `guideline-OCR.md` | 交付目录 `01_儿童颅脑创伤诊治中国专家共识_全文OCR.md` 的副本（期刊全文 OCR） | 最高：所有指南/文献数字必须命中这里（OCR 误识除外，见 `../cite-allow.txt`） |
| `original-deck.txt` | 原始 25 页稿 `2026武威市神经外科诊疗技能大赛病例汇报-婴.pptx` 的文本 dump（含备注） | 高：病例事实的原始出处；**图片里的数字不在此文件** |
| `lab-reports.md` | 原稿检验报告截图（`work/report/media_check/p6_2.png`、`p6_4.png`、`p18_2.png`、`p18_4.png`）逐行转写 | 高：化验单数值与参考范围；转写规则见文件头 |

## 维护规则

1. **不手改** `guideline-OCR.md`：它是 01 原文副本；原文变了就整份替换并在 ship 报告里说明。
2. `original-deck.txt` 由 `python3 deck_text.py <原稿.pptx> > authority/original-deck.txt` 生成，
   重新生成后检查 diff（原稿更新才需要）。
3. `lab-reports.md` 只许按报告单原样转写；改数字必须同时核对截图并在报告里注明。
4. 三份文件的 sha256 会写进每次 ship 的 manifest；gate 只依赖文件内容，不依赖文件名。
5. **不进 GitHub**：本目录含病例数据，只留在本机项目目录（与交付目录同级的隐私级别）。
