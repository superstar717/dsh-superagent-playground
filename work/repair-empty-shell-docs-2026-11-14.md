# 空壳文档重喂（增量索引）· 2026-11-14

> 对象：GraphMind 两库各 1 条「空壳 `processed`」记录（`content_length=0`、`chunks_count=0`，内容不在索引里）。
> 依据：`work/kb-audit-2026-11-14.md` §2.5（PR #29）给出的修复步骤；本工单只做这 2 篇的增量重喂，不做全量重建。
> 执行时间：2026-11-14 18:17–18:28 CST（约 11 分钟）。

## 1. 结论

两篇空壳文档已重喂成功，内容真正进入索引（chunk + 向量 + 实体/关系），检索可命中。

| 数据集 | 文件 | 修复前记录 | 修复后记录 | chunks | 实体 | 关系 |
| --- | --- | --- | --- | --- | --- | --- |
| 姜胡说 `jianghushu-methodology_b0607c` | `20200602_推荐大家参照以下几条线思考：种子用户 势能 裂变.txt` | `doc-5576f353…` processed / 0 字 / 0 块 | processed / **567 字 / 1 块**，hash `5576f353…` | 1972 → **1973** | 15,879 → **15,880** | 11,564 → **11,566** |
| 李公子 `ligongzi_9c54ca` | `20230622_地域优势，.txt` | `doc-3d2dc4b5…` processed / 0 字 / 0 块 | processed / **1,709 字 / 2 块**，hash `3d2dc4b5…` | 736 → **738** | 5,011 → **5,042** | 5,717 → **5,750** |

- 两库「processed 但 0 字/0 块」记录数：**0**（修复前各 1）。
- `.indexed_files.json` 条目已恢复：姜胡说 **938**、李公子 **371**。
- 增量扫描只处理了这 2 篇：姜胡说 `跳过 937`、李公子 `跳过 370`，两库索引状态 `completed, progress=100`。
- 记录总数 977→**974**、376→**374**：因为按 §2.5 连带删除了这两篇的 `dup-*` 记录（姜胡说 3 条、李公子 2 条）；`processed` 数 902/370 保持不变（空壳记录被真实记录替换，不是新增）。

## 2. 为什么按这个步骤做

`backend/app/services/indexing_service.py` 的扫描是两层 skip：

1. 先比 `data/<ds>/.indexed_files.json`（filename → sha256）——不删条目会在第一层就被跳过；
2. 再按 `doc_status` 的 basename 查——同文件名只要还有任意状态的记录就会命中。

而 LightRAG 1.5.4 的 `pipeline.py` 在入队时还有 filename 去重（`get_existing_doc_by_file_basename`，任意状态命中即拦）并写一条 `dup-*` failed 记录。所以：

- **只改名重喂不成立**：去重键是内容派生的 `doc_id`，改名不改 `doc_id`，仍会被拦成 `dup-*`；
- 必须删该文件名的**整组记录**（空壳 `doc-*` + 全部 `dup-*`），并删 `.indexed_files.json` 条目，才能让重扫把它当新文档处理。

## 3. 执行步骤（可复现）

脚本：`work/scripts/repair_empty_shell_docs.py`（默认 dry-run；`--apply` 要求 8777 端口已关闭；`--verify` 复核）。

```bash
# 0) 预检（只读）
python3 work/scripts/repair_empty_shell_docs.py

# 1) 停服务（launchd KeepAlive，必须 unload 而不是 stop）
launchctl bootout gui/$(id -u)/com.huweixing.graphmind
# 确认：lsof -nP -iTCP:8777 -sTCP:LISTEN 为空

# 2) 备份 + 删除 doc_status 记录与 .indexed_files 条目（脚本自动备份）
python3 work/scripts/repair_empty_shell_docs.py --apply

# 3) 重启服务
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.huweixing.graphmind.plist

# 4) 触发两库增量索引（只处理缺条目的这 2 篇）
curl -s -X POST -H 'Content-Type: application/json' -d '{}' \
  http://127.0.0.1:8777/api/datasets/jianghushu-methodology_b0607c/index
curl -s -X POST -H 'Content-Type: application/json' -d '{}' \
  http://127.0.0.1:8777/api/datasets/ligongzi_9c54ca/index

# 5) 复核
python3 work/scripts/repair_empty_shell_docs.py --verify
```

删除的记录（脚本输出）：

- 姜胡说：`doc-5576f353f25d22fe1b1b3dee7198051b`（空壳）+ `dup-829ffecf…`、`dup-9efcce7b…`、`dup-2c8f8102…`；
- 李公子：`doc-3d2dc4b5eddbd458cade1b0b10cd2f53`（空壳）+ `dup-0097408a…`、`dup-43266968…`。

备份：`~/graphmind-replica/backups/empty-shell-repair-20261114-181826/`（两库的 `kv_store_doc_status.json` 与 `.indexed_files.json`，共 4 个文件）。

## 4. 复核证据

### 4.1 `--verify` 全部 PASS

```
== verify: jianghushu-methodology_b0607c / 20200602_推荐大家参照以下几条线思考：种子用户 势能 裂变.txt
   [PASS] exactly 1 record for file (got 1)
   [PASS] no empty processed record (got [])
   [PASS] 1 real processed record (got ['doc-5576f353f25d22fe1b1b3dee7198051b'])
   [PASS] text chunks present (got 1)
   [PASS] vector rows present (got 1)
   [PASS] re-indexed file is back in .indexed_files.json
   record: doc-5576f353f25d22fe1b1b3dee7198051b len=567 chunks=1 hash=5576f353f25d22fe1b1b3dee7198051b

== verify: ligongzi_9c54ca / 20230622_地域优势，.txt
   [PASS] exactly 1 record for file (got 1)
   [PASS] no empty processed record (got [])
   [PASS] 1 real processed record (got ['doc-3d2dc4b5eddbd458cade1b0b10cd2f53'])
   [PASS] text chunks present (got 2)
   [PASS] vector rows present (got 2)
   [PASS] re-indexed file is back in .indexed_files.json
   record: doc-3d2dc4b5eddbd458cade1b0b10cd2f53 len=1709 chunks=2 hash=3d2dc4b5eddbd458cade1b0b10cd2f53
```

### 4.2 检索抽查（`/search/context`，`mode=naive`，免生成）

- 姜胡说 query `1000名铁杆粉丝 抖音 粉丝`：返回内容包含该篇原文（"真正属于我的粉丝，大概只有1000人…"）与文件名 `20200602_推荐大家参照以下几条线…`。
- 李公子 query `地域优势 流量密码 人货场`：返回内容包含该篇原文（"恰恰那个地方就是流量密码…"）与文件名 `20230622_地域优势，.txt`。

### 4.3 索引收敛

- 姜胡说：`INDEXING START 18:19:41` → `completed 18:21:34`，`[938/938]`，`跳过 937 个已索引文件`。
- 李公子：`INDEXING START 18:21:45` → `completed 18:26:38`，`[371/371]`，`跳过 370 个已索引文件`。
- 两库全量统计（18:28）：姜胡说 974 条（902 processed / 72 failed）、1,973 chunks、15,880 实体向量、11,566 关系向量、339MB；李公子 374 条（370 / 4）、738 chunks、5,042 / 5,750、137MB。

## 5. 回滚

停服务 → 把备份目录里的 4 个文件按原名复制回：

- `data/jianghushu-methodology_b0607c/rag_storage/jianghushu-methodology_b0607c/kv_store_doc_status.json`
- `data/jianghushu-methodology_b0607c/.indexed_files.json`
- `data/ligongzi_9c54ca/rag_storage/ligongzi_9c54ca/kv_store_doc_status.json`
- `data/ligongzi_9c54ca/.indexed_files.json`

→ 重启服务。注意：回滚只恢复「修复前」状态（含 2 条空壳），本次新增的 chunk/向量/实体需另按索引删除流程清理；生产上只有在重喂失败且要立刻回到旧状态时才需要回滚。

## 6. 未解决 / 风险

- **空壳成因未定位**：本次修复只删除这两篇的旧记录并重喂；LightRAG 在「同文件多轮扫描 + dup 拦截」路径上为何把原 processed 记录清成空壳（日志只有 `Preserving failed document entries`），仍无代码级证据。若再次出现，先跑 `--verify` 识别，再跑 `--apply` + 重索引。
- **上游 LLM 波动**：重喂李公子时其中一个 chunk 的 `glm-4-flash` 抽取请求一次 120s 超时，OpenAI SDK 自动重试后成功（日志 `2 retries left` → 后续 `Merging stage`/`Completed processing`）。不影响结果，但说明索引吞吐会受上游影响。
- **vdb/kv chunk 差 9 条**：姜胡说 `vdb_chunks` 1,964 vs `kv_store_text_chunks` 1,973，是 12:01 两次落盘时点差（vdb 早于 kv），不是本次造成；本次新增 chunk 在两个存储里都有。
