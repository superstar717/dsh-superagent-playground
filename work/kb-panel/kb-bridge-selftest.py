#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""kb-bridge 数据集切换回归自测（无网络、无 LLM；本机语料缺失时相关项自动 SKIP）。

覆盖 2026-11-15 事故（工单 f277f89af4d0）：面板「梳理」的 /api/synth 与 /api/summary
不接收 ds 参数，固定搜姜胡说 kb_para + asr；选「李公子」时只有右侧图谱换了数据源，
左边梳理内容仍是姜胡说的。

防回归点：
1. resolve_ds 映射：空/未知 ds → 姜胡说（兼容旧链接）；ligongzi_9c54ca → 李公子，
   graph_first=True、无笔记库（不得混搜 kb_para）。
2. graph_query_expand / graph_parse：音译扩词、实体/关系/原文块解析与相关性过滤。
3. _synth 按数据集搜本地目录：李公子只出 asr_simplified_ligongzi / asr_ligongzi 来源，
   不得混入 kb_para；概念卡不显示姜胡说的 PARA 统计，改出说明文字。
4. _summary 图谱优先：李公子把图谱原文块并入材料池、要点出处带「图谱·」前缀、
   source_note 标注知识图谱；姜胡说不得触发图谱调用（行为不变）。
5. 面板 HTML：/api/synth 与 /api/summary 必须携带 ds；来源标注来自服务端 source_note。

用法：
    python3 kb-bridge-selftest.py        # 全过 exit 0；任一失败 exit 1

接入位置：仓库 CI（.github/workflows/kb-bridge-selftest.yml，无本机语料时跑纯逻辑项）；
本机部署改 ~/.local/bin/kb-bridge 或 ~/.local/share/kb-panel/kb-panel.html 前后各跑一次。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "kb-bridge"
PANEL = HERE / "kb-panel.html"

HOME = Path.home()
LOCAL_CORPUS_OK = all(
    (HOME / "姜胡说" / d).is_dir()
    for d in ("asr_simplified_ligongzi", "asr_ligongzi", "asr", "kb_para")
)


def load():
    loader = SourceFileLoader("kb_bridge_under_test", str(TARGET))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


m = load()
failures: list[str] = []
skips = 0


def check(name: str, got, want) -> None:
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "->", got, "want", want)
    if not ok:
        failures.append(name)


def skip(name: str, why: str) -> None:
    global skips
    skips += 1
    print("SKIP", name, f"（{why}）")


def handler():
    """不启 HTTP、不落盘的 handler 实例，只测方法逻辑。"""
    h = object.__new__(m.H)
    h._VAULT_CACHE = {}
    return h


# ── 1. 数据集映射 ───────────────────────────────────────────────────────────
check("空 ds → 姜胡说（兼容旧链接）", m.resolve_ds("")["id"], m.DEFAULT_DS)
check("未知 ds → 姜胡说", m.resolve_ds("nope_123")["id"], m.DEFAULT_DS)
lg = m.resolve_ds("ligongzi_9c54ca")
check("李公子 → graph_first", lg["graph_first"], True)
check("李公子 → 无笔记库（不混搜 kb_para）", lg["vault"], [])
check("李公子 → 本地 ASR 目录在注册表里", len(lg["asr_dirs"]) >= 1, True)
check("李公子 source_note 标注图谱来源", "知识图谱" in lg["source_note"], True)
jh = m.resolve_ds("jianghushu-methodology_b0607c")
check("姜胡说 → 非 graph_first（行为不变）", jh["graph_first"], False)
check("姜胡说 → 仍有笔记库", len(jh["vault"]) >= 1, True)

# ── 2. 图谱查询扩词与解析 ───────────────────────────────────────────────────
exp = m.graph_query_expand("PARA")
check("扩词含音译 pama", "pama" in exp, True)
check("扩词含中文上下文", "项目" in exp, True)
check("普通词不乱扩", m.graph_query_expand("捷径"), "捷径")

CTX = (
    '{"entity": "捷径", "type": "concept", "description": "人生有没有捷径可以走的讨论"}\n'
    '{"entity": "无关实体", "type": "thing", "description": "别的视频里的内容"}\n'
    '{"entity1": "捷径", "entity2": "方法", "description": "捷径是一种省力方法"}\n'
    "[1] 20220817_100万.txt [2] 20221014_先去做.txt\n"
    '{"reference_id": "1", "content": "人生有没有捷径可以走 当然有 我今天分享两个方法"}\n'
    '{"reference_id": "2", "content": "完全无关的内容块讲的是别的事"}\n'
)
p = m.graph_parse(CTX, "捷径", "捷径")
check("相关性过滤丢掉无关实体", [e["name"] for e in p["entities"]], ["捷径"])
check("相关性过滤丢掉无关关系", len(p["relations"]), 1)
check("相关性过滤丢掉无关原文块", [c["id"] for c in p["chunks"]], ["1"])
check("引用清单不受过滤影响", [r["name"] for r in p["refs"]][0], "20220817_100万.txt")
check("totals 记录过滤前总量", p["totals"], {"entities": 2, "relations": 1, "chunks": 2})

# ── 3. _synth 按数据集搜本地 ─────────────────────────────────────────────────
h = handler()
if LOCAL_CORPUS_OK:
    s = h._synth("捷径", "ligongzi_9c54ca")
    srcs = [x["file"] for x in s["evidence"]["high"]] + [pt["source"] for pt in s["points"]]
    check("李公子 _synth 标注数据集", s["dataset_label"], "李公子")
    check("李公子 _synth graph_first", s["graph_first"], True)
    check("李公子来源全是本地 ASR 目录（不混 kb_para/姜胡说 asr）",
          bool(srcs) and all(x.startswith("asr_") for x in srcs), True)
    check("李公子无 PARA 概念卡", s["concepts"], [])
    check("李公子概念卡给说明文字", "知识图谱" in (s["concepts_note"] or ""), True)
    check("李公子 brief 说明图谱为主", "知识图谱" in s["brief"], True)

    s2 = h._synth("捷径", "")
    check("姜胡说 _synth 标注数据集", s2["dataset_label"], "姜胡说")
    check("姜胡说 _synth graph_first 不变", s2["graph_first"], False)
    check("姜胡说仍有 PARA 概念卡", len(s2["concepts"]), 4)
    jh_srcs = {pt["source"] for pt in s2["points"]} | {x["file"] for x in s2["evidence"]["high"]}
    check("姜胡说来源不混入李公子目录",
          all(not x.startswith("asr_simplified_ligongzi") and not x.startswith("asr_ligongzi")
              for x in jh_srcs), True)
else:
    skip("_synth 双数据集实测", "本机缺少姜胡说/李公子语料目录（CI 环境）")

# ── 4. _summary 图谱优先（材料池打桩，不依赖语料与 LLM）────────────────────
POOL_SYNTH = {"ok": True, "evidence": {"high": [
    {"text": "人生有没有捷径可以走当然有我今天分享两个方法", "file": "asr_simplified_ligongzi/7667193545338400875.txt", "heading": "原话"},
    {"text": "很多人卡在努力却没有结果的点上", "file": "asr_ligongzi/7668685722542951158.txt", "heading": "原话"},
]}}
LLM_OUT = json.dumps({
    "summary": "捷径是李公子讲的赚钱路径话题",
    "points": [
        {"claim": "人生有没有捷径可以走他说有", "why": "开场原话", "source": "图谱·20220817_100万.txt"},
        {"claim": "他分享了两个方法", "why": "同一句原话", "source": "asr_simplified_ligongzi/7667193545338400875.txt"},
    ],
}, ensure_ascii=False)

h2 = handler()
graph_calls = []
m.graph_fetch = lambda q, dsid, timeout=240: (graph_calls.append((q, dsid)) or CTX)
h2._synth = lambda q, ds="", use_llm=False: dict(POOL_SYNTH)
h2._llm = lambda prompt, timeout=90: LLM_OUT
d = h2._summary("捷径", "ligongzi_9c54ca")
check("李公子 _summary 成功", d["ok"], True)
check("李公子 _summary 调用了图谱", [(c[1]) for c in graph_calls], ["ligongzi_9c54ca"])
check("李公子要点出处带图谱前缀",
      any(pt["source"].startswith("图谱·") for pt in d["points"]), True)
check("李公子 source_note 标注知识图谱", "知识图谱" in d["source_note"], True)
check("李公子 source_note 标注本地 ASR", "本地 ASR" in d["source_note"], True)

h3 = handler()
graph_calls2 = []
m.graph_fetch = lambda q, dsid, timeout=240: graph_calls2.append((q, dsid)) or CTX
h3._synth = lambda q, ds="", use_llm=False: dict(POOL_SYNTH)
h3._llm = lambda prompt, timeout=90: LLM_OUT
d2 = h3._summary("捷径", "")
check("姜胡说 _summary 成功", d2["ok"], True)
check("姜胡说 _summary 未触发图谱", graph_calls2, [])
check("姜胡说 source_note 保持本地口径", d2["source_note"], "AI 提炼 · 来源限于本地检索结果")

# 图谱失败 → 如实降级标注，不假装检索过
h4 = handler()
def _boom(q, dsid, timeout=240):
    raise RuntimeError("connect refused")
m.graph_fetch = _boom
h4._synth = lambda q, ds="", use_llm=False: dict(POOL_SYNTH)
h4._llm = lambda prompt, timeout=90: LLM_OUT
d3 = h4._summary("捷径", "ligongzi_9c54ca")
check("图谱失败时 _summary 仍成功（降级本地）", d3["ok"], True)
check("图谱失败标注写进 source_note", "图谱检索失败" in d3["source_note"], True)

# ── 5. 面板 HTML 回归 ───────────────────────────────────────────────────────
html = PANEL.read_text(encoding="utf-8")
check("面板 /api/synth 携带 ds", "'/api/synth?q='+encodeURIComponent(q)+'&ds='+encodeURIComponent(ds)" in html, True)
check("面板 /api/summary 携带 ds", "encodeURIComponent(ds)" in html.split("/api/summary")[1][:200], True)
check("面板显示服务端来源标注", "s.source_note" in html and "d.source_note" in html, True)
check("面板图谱兜底要点标注来源", "图谱要点" in html, True)

print()
if failures:
    print(f"FAILED {len(failures)} 项：{failures}")
    sys.exit(1)
print(f"ALL PASS（SKIP {skips}）")
