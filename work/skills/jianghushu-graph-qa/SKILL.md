---
name: jianghushu-graph-qa
description: 用本机 GraphMind 知识图谱回答姜胡说/李公子内容与方法论问题。当问题涉及姜胡说、李公子、他们的视频逐字稿、知识库内容、框架/体系/方法论，或需要「他们讲过什么 / 怎么说的 / 出处」时使用；回答要带图谱检索标注与依据。
---

# 姜胡说 × 李公子 图谱问答（superagent 工单内）

飞书群的「图谱问答」已统一交给 superagent 工单（2026-11-13 起，工单 c568a58a9d7e）。
worker 收到这类问题：先查本机 GraphMind 知识图谱，再作答；不凭记忆、不编造。
图谱服务是**本机只读检索**，没有联网能力——不要向它要实时/网络信息。

## 何时用

- 问题关于姜胡说 / 李公子讲过什么、怎么说的、原话出处、方法论的组成部分。
- 问题可以用「他们的逐字稿内容」回答（例如「姜胡说怎么看待副业」「李公子的框架有哪几层」）。
- 用户要求「原文 / 依据 / 出处」且主题属于上述两位。

不适用：通用时事、网页调研、软件安装排障、GitHub/工单状态——这些走常规工具。

## 数据集

| 主题 | dataset id | 说明 |
| --- | --- | --- |
| 姜胡说 | `jianghushu-methodology_b0607c` | 逐字稿方法论图谱（约 1.9k 实体 / 2.3k 关系） |
| 李公子 | `ligongzi_9c54ca` | 李公子内容图谱（小数据集） |
| 其他 | `curl -s --max-time 60 http://127.0.0.1:8777/api/datasets` | 列出全部数据集，按 name 匹配后再用 |

## 查询（两条路，择一）

1. 工具列表里若有 `kg_search`（graphmind-bridge 插件）：
   `kg_search(query="…", dataset="jianghushu-methodology_b0607c", mode="mix")`
2. 否则用 bash + curl（当前 worker 的基础工具即可）：

```bash
curl -s --max-time 120 -X POST \
  -H 'Content-Type: application/json' \
  -d '{"query":"姜胡说怎么看待副业？","mode":"mix"}' \
  http://127.0.0.1:8777/api/datasets/jianghushu-methodology_b0607c/search \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("answer","")); print("---context---"); print((d.get("context") or "")[:800])'
```

要点：
- GraphMind 建索引期间 `/api/datasets` 可能要 10–30s、`/search` 60–90s。用 `--max-time 120`；
  长查询放后台 job（`run_in_background`）再读结果，别在前台干等。
- `mode` 可选 `local`（实体聚焦）/ `global`（关系宏观）/ `hybrid` / `mix`（最全面）/ `naive`；
  默认用 `mix`，结论太散时换 `local` 收敛。
- 一次问题查一次；拆成子问题时分次查，别把整段长文当 query。

## 回答要求

- 用 `[图谱检索]` 标注来源，给结论 + 2–4 条依据（答案里的要点或检索片段中的原话）。
- 图谱没有就明说「图谱未收录」，区分「没查到」与「不存在」；不要用常识补全成他们的观点。
- 时效信息（价格、版本、活动）注明日期；图谱里的历史内容不要说成实时事实。
- 只读：不把问题、答案或任何内容写回图谱。

## 失败处理

- 连接被拒 / 超时：如实说「图谱服务暂不可用」，再退回 `~/姜胡说/embed_env/bin/kb retrieve "<关键词>"`
  （段落库 kb_para）或网络检索；两条都没有就说明没有证据。
- 不要因为图谱不可用就凭记忆编答案。
