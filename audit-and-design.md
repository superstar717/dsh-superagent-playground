# 记忆框架优化：单一事实源、写入前查重、定期合并清理

工单：`optimize-memory-frame-37a79150ca0b`（2026-11-06）
来源：Feishu 讨论「当前的记忆框架是否还需要优化」→ 结论「需要优化，但不必重做」，最小改法三条：
**定单一事实源、写入前查重、定期做合并清理**。

设计约束（LESSONS E79，2026-11-06）：宿主已有执行+治理能力时自研平行"第二执行大脑"边际价值为负。
因此本工单**零新系统**：全部复用既有机制（dsh-memory-evolve 插件的 memory 工具/待办/合并技能、
LESSONS 检索惯例、AGENTS.md 全局注入），改动落在约定层与既有配置。

---

## 一、三处重叠与冲突点（动手前盘点，实据）

### 发现 1：LESSONS.md 存在第二个副本，且已双向漂移

| 文件 | 角色 | 现状 |
|---|---|---|
| `~/.dsh/LESSONS.md` | 运行版（收尾追加目标） | 82 条（E00–E81），1235 行 |
| `~/.dsh/assets/reusable/LESSONS.md` | "可分发详版快照" | 79 条，1273 行，**含运行版没有的「实战案例补充」节**（E33/E52 案例、测度分解成功案例，2026-10-29） |

- 快照头部自己声明了正确方向："运行版日志（新条目先落此）：`~/.dsh/LESSONS.md`；本文件为其可分发详版快照，项目收尾时同步"——但同步从未执行。
- `reusable/README.md` 的容灾指引 `cp LESSONS.md ~/.dsh/LESSONS.md`（仅限目标不存在时）若被误用会**用 79 条覆盖 82 条**。
- README 目录注释「当前 17 条」已严重过期；「新项目初始化三步」（`cp -r reusable/` 进项目）描述的是 E41 已废弃的拷贝分发制，与 newproj 现行「只读引用全局库」实现（`~/.dsh/bin/newproj` 第 29–30 行）直接矛盾。

### 发现 2：同一教训多处复述（双写模式实锤）

- E44（拦截机制两条铁律）：全文在 LESSONS.md；全局 memory（MEMORY.md）第 1 条复述并加指针；AGENTS.md 第六节蒸馏为政策。三处各有一部分增量，但复述度过高。
- E46（插件源管理）：LESSONS.md + MEMORY.md 第 2 条复述。
- AGENTS.md 第五节「遇错先 grep LESSONS」被抄进项目 key（`projects/f19b11405071/KEY.md`）。
- f19b11405071/KEY.md 的资产位置结论（`~/project/deepseek-haness-test/reusable/`）与 37a9b993ceee/KEY.md 的新约定（`~/.dsh/assets/reusable`，2026-10-28 E41 修复）**互相冲突**——旧结论无过期机制，会继续被注入。

### 发现 3：插件内已有的机制与真正的缺口

dsh-memory-evolve 已内置：五轨分工、全局轨确认制、回合内审查查重（默认关）、`list filter` 查询、
SuggestionQueue 字面去重（hits 计数）、memory-consolidate 技能（scan_memory.mjs 预扫+归档可逆）。
**缺口**：LESSONS.md / AGENTS.md / reusable 快照不在任何轨道治理范围内——没有单一事实源宣告、
没有写入前查重规则、没有定期清理触发器。本次会话实测：`scan_memory.mjs` 对 `~/.dsh/memories`
扫出 **410 条在轨条目、8 个候选簇**（supersede=1 / duplicate=1 / similar=6，详见
[memory-consolidate-report.json](<memory-consolidate-report.json>)），均为项目轨内部簇，
按技能边界应在各项目自己的会话里裁决。

> 诚实备注：来源讨论中「今晚的 E75 就是（双写）」一例未能在记忆文件中复现——E75 仅存在于
> LESSONS.md，其项目无 KEY.md。双写模式以发现 2 的 E44/E46 实据为准。

## 二、落地改动（全部可回滚）

### 1. 单一事实源（`~/.dsh/AGENTS.md` 第四节修订 + 新增第七节）

四类权威源，一类内容只落一处，其余位置只放一行指针：

| 内容类型 | 唯一权威源 | 他处只允许 |
|---|---|---|
| 跨项目错误/坑 | `~/.dsh/LESSONS.md`（运行版） | 指针 `LESSONS Exxx：关键词` |
| 常驻规则/全局约定 | `~/.dsh/AGENTS.md` | 引用节号 |
| 跨项目事实/环境事实/速查 | memory 全局轨（确认制） | 与前两类重复的不写 |
| 项目长期事实 | memory target=key（按项目/分支） | 教训→LESSONS 指针；规则→节号 |

reusable/LESSONS.md 明确为**只读快照**：只许从运行版单向刷新，禁止反向覆盖；
刷新前必须先把快照独有内容并回运行版（本次盘点实测快照有运行版没有的内容，直接刷新=丢数据）。

### 2. 写入前查重（第七节，四类写操作通用）

写 LESSONS/AGENTS/memory key/全局建议前：`grep "<症状关键词>" ~/.dsh/LESSONS.md` +
memory 工具 `list filter=<关键词>`；命中→在既有条目内更新（不新增）；未命中→按归类写唯一权威源。

### 3. 定期合并清理（第七节 + 第一节收尾第 5 项 + dtodo 触发器）

- 每月一次 + 项目收尾时：① memory 轨跑 memory-consolidate 技能；② 跨源审计（互查重复、过期状态清理、快照单向同步）；
- 到期提醒 = dtodo work 轨任务「记忆合并清理」（id `09cc685c`，due 2026-12-06，完成后 due 改下月自续期）；
- 首次预扫已完成（410 条/8 簇），各项目轨的裁决留到各自会话的首次到期执行（技能的 cwd 隔离边界）。

### 4. reusable/README.md 修正（[reusable-README.diff](<reusable-README.diff>)）

- 目录注释去掉过期条数，标注快照只读+单向刷新；
- 废弃的「拷贝 reusable/ 进项目」初始化三步改为现行 newproj 引用式流程（E41 约定）；
- 容灾 `cp` 指令加「仅当目标不存在；已存在禁止覆盖」警告。

## 三、验证（E44 铁律：当场用真实目标验证机制在运行）

| # | 验证 | 结果 |
|---|---|---|
| 1 | AGENTS.md 修改后全局注入管道拿到变更 | ✅ 宿主对每次编辑即时回报 Updated instructions（本会话三次收到重注入） |
| 2 | 查重 grep 流程对真实目标命中 | ✅ 假设新增「esttab 中位数」条目 → 命中 E78（不新增，条目内更新） |
| 3 | memory 轨查重查询路径 | ✅ 经插件 `MemoryStore.entriesOf` 真实代码：`事实源` 命中 E46 条、`查重` 零命中 |
| 4 | dtodo 到期触发器 | ✅ 经插件 `TodoStore.addTodo` 写入 work 轨（id 09cc685c，due 2026-12-06），格式经真实解析器校验 |
| 5 | 定期清理预扫 | ✅ `scan_memory.mjs` 真实运行：410 条 / 8 簇 / 报告落盘 |
| 6 | 备份可回滚 | ✅ `~/.dsh/backup/memory-frame-20261106T0945/`（AGENTS/LESSONS/快照/README + SHA256 清单，`shasum -c` 全 OK） |

未做（留待首次到期清理，防信息丢失）：快照独有「实战案例补充」并回运行版、8 个候选簇裁决、
全局 memory 两条复述条目的指针化——均需用户在场逐条拍板，符合 memory-consolidate「信息损失风险→宁可不合并只标记」标准。

## 四、回滚

```bash
BK=~/.dsh/backup/memory-frame-20261106T0945
shasum -a 256 -c "$BK/SHA256SUMS.manifest"   # 先验完整性
cp "$BK/AGENTS.md"             ~/.dsh/AGENTS.md
cp "$BK/reusable-README.md"    ~/.dsh/assets/reusable/README.md
# LESSONS.md 本工单未改动（备份仅防意外）；dtodo 任务可经 dtodo remove 09cc685c 撤销
```

dtodo 任务 id：`09cc685c`；memory 轨本工单零直写（后续进展走插件 store 正常写入）。

## 五、改动文件清单

- `~/.dsh/AGENTS.md` — 第四节修订、第一节第 5 项、新增第七节（[AGENTS.md.diff](<AGENTS.md.diff>)）
- `~/.dsh/assets/reusable/README.md` — 四处修正（[reusable-README.diff](<reusable-README.diff>)）
- `~/.dsh/memories/TODOS-work.md` — 新增月度清理任务（插件 TodoStore 写入）
- `memory-consolidate-report.json` — 首次预扫报告（本仓库）
- `scripts/memory_ops.mjs` — 经插件官方实现类操作记忆/待办的验证工具（本仓库）
