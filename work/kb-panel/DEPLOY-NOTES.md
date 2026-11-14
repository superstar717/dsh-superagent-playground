# 部署说明：kb-bridge / kb-panel 数据集切换修复（2026-11-15，工单 f277f89af4d0）

## 事故（用户报告 + 代码核实）

面板里选「李公子」后点「梳理」，左边出的仍是姜胡说内容。原因具体：

- 「梳理」按钮走 `/api/synth` 与 `/api/summary`，两个接口**不接收 `ds` 参数**，
  检索目录写死 `~/姜胡说/kb_para`、`~/姜胡说/kb`、`~/姜胡说/asr`；
- 只有右侧「图谱」走 `/api/ctx` 时才真的带 `ds`。

修复前截图证据：`work/repro/evidence/before-ligongzi.png/.json`
（选了李公子，左边要点出处是 `asr/7542157131752033546.txt`、`kb_para/...` —— 都是姜胡说的；
右边图谱卡却是李公子的「人生有没有捷径可以走」原话；概念卡还在显示姜胡说 kb_para 的 PARA 统计）。

## 修了什么（`~/.local/bin/kb-bridge` + `~/.local/share/kb-panel/kb-panel.html`）

1. **数据集注册表 `DATASETS` + `resolve_ds()`**：一个数据集 = 本地检索目录 + 图谱数据集 id。
   - 姜胡说（`jianghushu-methodology_b0607c`）：kb_para + kb + asr/，行为不变；
   - 李公子（`ligongzi_9c54ca`）：本地只有 `asr_simplified_ligongzi` + `asr_ligongzi`（2026-11-14 实测各 10 篇，
     同名繁简两版，简体版优先匹配简体查询词），**无 Obsidian 笔记库**（kb_para/kb 属姜胡说，不混搜）；
   - 空/未知 ds → 姜胡说（兼容旧链接）。
2. **`/api/synth` 与 `/api/summary` 接收 `ds`**，按注册表取目录；`/api/ctx` 的图谱检索抽成
   `graph_fetch()/graph_parse()/graph_query_expand()` 共享（响应结构不变）。
3. **李公子 = 图谱优先梳理（graph_first）**：
   - `_summary` 把图谱 `/search/context` 的原文块（经相关性过滤）并入 AI 提炼材料池，
     要点出处带「图谱·<引用文件名>」前缀；
   - `_synth` 的 brief/概念卡如实说明「本地语料很少，完整语料在知识图谱」，不显示姜胡说的 PARA 统计；
   - 页面来源标注来自服务端 `source_note` 字段（`#srcnote`），不再固定写「规则分级」；
   - AI 提炼失败时，面板兜底用图谱原文块出「图谱要点」并标注来源；
   - 图谱检索失败时如实降级（source_note 写明「图谱检索失败…仅本地 ASR」），不假装检索过图谱。
4. **ASR 检索加繁简互转变体**（与 kgrep 同逻辑，opencc 可导入才生效；LESSONS E149：只搜字面必漏音译/繁简）。
5. 同名繁简文件按文件名去重（简体目录在前，先命中者得）。

## 为什么李公子是图谱优先（路由注记要求的核实结论）

- `~/姜胡说/asr_ligongzi`、`asr_simplified_ligongzi`：各 **10 篇**（dysub 2026-11-08 起的增量）；
- 李公子 371 篇全量逐字稿只存在于图谱输入目录 `~/graphmind-replica/data/ligongzi_9c54ca/input/`（按日期+标题命名），
  不在常规检索目录里；`creator_contents_ligongzi_20260830.jsonl` 等为采集元数据。
- 结论：本地目录可搜的只是一小角，图谱才是完整语料 → graph_first + 明确标注，而不是假装本地检索覆盖。

## 验证

- 自测：`python3 work/kb-panel/kb-bridge-selftest.py` —— 40 项全过（无网络无 LLM；
  本机语料缺失时语料项自动 SKIP，CI 只跑纯逻辑项）。CI：`.github/workflows/kb-bridge-selftest.yml`。
- 接口实测（本机 127.0.0.1:8790）：
  - `/api/synth?q=捷径&ds=ligongzi_9c54ca` → 来源 `asr_simplified_ligongzi/7667193545338400875.txt`（李公子视频原话），
    `source_note=来源：知识图谱 ligongzi_9c54ca（371 篇）+ 本地 ASR（仅 10 篇，图谱优先）`；
  - `/api/synth?q=捷径`（无 ds）→ 来源 `asr/…`、`kb_para/…`（姜胡说，回归通过）；
  - `/api/summary?q=捷径&ds=ligongzi_9c54ca` → 要点出处含「图谱·…」前缀（AI 提炼，走图谱材料池）。
- 端到端：`work/repro/shot_panel.py`（Playwright 选数据集 → 点梳理 → 截图 + 抓取左右栏证据），
  修复前 `before-ligongzi.*`，修复后 `after-ligongzi.*`。

## 部署状态（2026-11-15 06:05）

- launchd 服务 `com.huweixing.kb-bridge`（KeepAlive）已 bootout → bootstrap 干净重启，
  单实例 PID 93169 监听 127.0.0.1:8790。
- **已知环境噪声（与本修复无关，如实记录）**：验证期间本机处于严重 I/O 风暴
  （iostat 实测 2744 tps / 322 MB/s，系统级进程高速创建导致 PID 回绕），冷读爬满
  导致当时请求时延从正常 ~1s 膨胀到 15s+ 甚至超时；风暴期结束后恢复正常。
  对照证据：同代码用 `env -i`（等价 launchd 环境）另起实例，同一请求 1.0s 返回且结果正确。
- 机器磁盘风暴期间（6:00–6:1x），`ps`/`rg` 等一切冷 I/O 都慢，「kb-bridge 卡死」的表象
  与多实例假象（自己的诊断命令行匹配了 grep 模式）都已排除；launchd 日志确认单实例无重启循环。

## 回滚

```bash
# 1) 代码回滚：git revert 本 PR，把 work/kb-panel/ 两个文件拷回活体位置
cp work/kb-panel/orig/kb-bridge ~/.local/bin/kb-bridge
cp work/kb-panel/orig/kb-panel.html ~/.local/share/kb-panel/kb-panel.html
launchctl kickstart -k gui/$(id -u)/com.huweixing.kb-bridge
```

`work/kb-panel/orig/` 是修复前原文快照（由本会话对活体文件的精确逆向重建生成，
py_compile + 行为锚点校验通过），修复前所有行为（含写死姜胡说目录）都在里面。
