#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""方法论工作台构建脚本（只读消费既有数据，不改任何源文件）。

数据源：
- 姜胡说:  ~/姜胡说/kb/{SYSTEM.md, INDEX.md, 0*.md}          （只读）
- 李公子:  ~/李公子/{框架体系汇总-详细版.md, 知识金字塔-详细梳理.md}  （只读）
- 图谱:    ~/graphmind-replica/data/{ligongzi_9c54ca, jianghushu-methodology_b0607c}/rag_storage/*/**.graphml （只读）

输出：~/methodology-workbench/index.html （自包含单文件，双击即开）
用法：python3 build.py
"""
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from pathlib import Path

HOME = Path.home()
KB_DIR = HOME / "姜胡说" / "kb"
ASR_DIR = HOME / "姜胡说" / "asr"
LG_DOC_DIR = HOME / "李公子"
GM_DATA = HOME / "graphmind-replica" / "data"
LG_INPUT = GM_DATA / "ligongzi_9c54ca" / "input"
JHS_INPUT = GM_DATA / "jianghushu-methodology_b0607c" / "input"
OUT_DIR = HOME / "methodology-workbench"
SRC_DIR = Path(__file__).resolve().parent / "src"
GRAPHMIND_URL = "http://localhost:8777"

# ---------------------------------------------------------------- md 渲染

def _inline(escaped: str) -> str:
    """行内格式：**粗体**、`代码`、[文本](链接)->文本。输入须已 html.escape。"""
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", escaped)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


def md_to_html(md_text: str) -> str:
    """极简 Markdown 渲染：标题/列表/引用/表格/围栏代码/粗体。够用即可，不追求完备。"""
    out: list[str] = []
    lines = md_text.split("\n")
    i, n = 0, len(lines)
    list_stack: list[str] = []  # 'ul' | 'ol'

    def close_list():
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    while i < n:
        raw = lines[i]
        line = raw.rstrip()

        if line.strip().startswith("```"):
            close_list()
            buf = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            out.append("<pre class='ascii'>" + html.escape("\n".join(buf)) + "</pre>")
            i += 1
            continue

        if line.startswith("#### "):
            close_list()
            out.append("<h5>" + _inline(html.escape(line[5:].strip())) + "</h5>")
            i += 1
            continue
        if line.startswith("### "):
            close_list()
            out.append("<h4>" + _inline(html.escape(line[4:].strip())) + "</h4>")
            i += 1
            continue
        if line.startswith("## "):
            close_list()
            out.append("<h3>" + _inline(html.escape(line[3:].strip())) + "</h3>")
            i += 1
            continue

        if line.lstrip().startswith("|") and line.count("|") >= 2:
            close_list()
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            if rows:
                head, body = rows[0], rows[1:]
                t = ["<table>", "<thead><tr>"]
                t += [f"<th>{_inline(html.escape(c))}</th>" for c in head]
                t.append("</tr></thead><tbody>")
                for r in body:
                    t.append("<tr>")
                    t += [f"<td>{_inline(html.escape(c))}</td>" for c in r]
                    t.append("</tr>")
                t.append("</tbody></table>")
                out.append("".join(t))
            continue

        if line.startswith("> ") or line == ">":
            close_list()
            buf = []
            while i < n and (lines[i].startswith("> ") or lines[i] == ">"):
                buf.append(lines[i][2:] if lines[i].startswith("> ") else "")
                i += 1
            body = "<br>".join(_inline(html.escape(b)) for b in buf if b is not None)
            out.append("<blockquote>" + body + "</blockquote>")
            continue

        m = re.match(r"^(\s*)[-*]\s+(.*)$", raw)
        if m and len(m.group(1)) < 4:
            if list_stack and list_stack[-1] != "ul":
                close_list()
            if not list_stack:
                list_stack.append("ul")
                out.append("<ul>")
            out.append("<li>" + _inline(html.escape(m.group(2).strip())) + "</li>")
            i += 1
            continue

        m = re.match(r"^(\s*)(\d+)[.、]\s*(.*)$", raw)
        if m and len(m.group(1)) < 4:
            if list_stack and list_stack[-1] != "ol":
                close_list()
            if not list_stack:
                list_stack.append("ol")
                out.append("<ol>")
            out.append("<li>" + _inline(html.escape(m.group(3).strip())) + "</li>")
            i += 1
            continue

        if re.fullmatch(r"-{3,}", line.strip()) or not line.strip():
            close_list()
            i += 1
            continue

        close_list()
        out.append("<p>" + _inline(html.escape(line.strip())) + "</p>")
        i += 1

    close_list()
    return "\n".join(out)


def strip_tags(html_text: str) -> str:
    txt = re.sub(r"<[^>]+>", " ", html_text)
    return re.sub(r"\s+", " ", html.unescape(txt)).strip()


# ---------------------------------------------------------------- 姜胡说 kb

def drop_h1(text: str) -> str:
    """去掉文件首个 H1 行（无论是否在文件开头）。"""
    return re.sub(r"(?m)^#[^\n]*\n", "", text, count=1)


def parse_system_sections() -> tuple[list[dict], str]:
    """SYSTEM.md 按 ## 拆条；跳过主题索引节（主题在九大主题组单独成卡）。"""
    body = drop_h1((KB_DIR / "SYSTEM.md").read_text(encoding="utf-8"))
    parts = re.split(r"\n## ", "\n" + body)
    intro = ""
    items = []
    for p in parts:
        if not p.strip():
            continue
        lines = p.split("\n")
        title = lines[0].strip()
        content = "\n".join(lines[1:]).strip()
        if not title:  # H1 与首个 ## 之间的文档引言
            intro = p.strip()
            continue
        m = re.match(r"(\d+)\.\s*(.+)", title)
        num, name = (m.group(1), m.group(2)) if m else ("", title)
        if "主题文章索引" in name:
            continue
        items.append({
            "id": f"j-core-{num or len(items)}",
            "title": f"{num} {name}".strip(),
            "badge": "",
            "html": md_to_html(content),
            "source": str(KB_DIR / "SYSTEM.md"),
        })
    return items, intro


def parse_theme(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    title = lines[0].lstrip("# ").strip()
    m = re.search(r"视频数：(\d+)", text)
    badge = f"{m.group(1)} 视频" if m else ""
    core = ""
    mc = re.search(r"核心：(.+)", text)
    if mc:
        core = mc.group(1).strip()
    body = "\n".join(lines[1:]).strip()
    return {
        "id": "j-theme-" + path.stem.split("-")[0],
        "title": title,
        "badge": badge,
        "core": core,
        "html": md_to_html(body),
        "source": str(path),
    }


# ---------------------------------------------------------------- 李公子

def parse_ligongzi_frameworks() -> tuple[list[dict], str]:
    body = drop_h1((LG_DOC_DIR / "框架体系汇总-详细版.md").read_text(encoding="utf-8"))
    parts = re.split(r"\n## ", "\n" + body)
    intro = ""
    items = []
    input_files = sorted(p.name for p in LG_INPUT.glob("*.txt")) if LG_INPUT.is_dir() else []

    for p in parts:
        if not p.strip():
            continue
        lines = p.split("\n")
        title = lines[0].strip()
        content = "\n".join(lines[1:]).strip()
        if title.startswith(">") or not title:
            intro = p.strip()  # 文档头部的依据/术语说明
            continue
            items.append({
                "id": "l-fw-meta",
                "title": "汇总口径",
                "badge": "口径",
                "html": md_to_html(content),
                "source": str(LG_DOC_DIR / "框架体系汇总-详细版.md"),
                "refs": [],
            })
            continue
        refs = extract_refs(content, input_files)
        items.append({
            "id": f"l-fw-{len(items)+1}",
            "title": re.sub(r"^[一二三四五六七八九]、\s*", "", title),
            "badge": f"框架{len(items)+1}",
            "html": md_to_html(content),
            "source": str(LG_DOC_DIR / "框架体系汇总-详细版.md"),
            "refs": refs,
        })
    return items, intro


def extract_refs(content: str, input_files: list[str]) -> list[dict]:
    """从文本抽取出处视频（日期《标题》或裸日期），映射到本机转写文件。

    裸日期若对应多个候选文件则视为歧义、不匹配，避免错误归因。
    """
    found: dict[str, str] = {}
    for date, t in re.findall(r"(\d{8})《([^》]+)》", content):
        found.setdefault(date, t)
    for date in re.findall(r"(?<!\d)(20\d{6})(?!\d)", content):
        found.setdefault(date, "")
    refs = []
    for date in sorted(found):
        title = found[date]
        cands = [f for f in input_files if f.startswith(date)]
        best = ""
        if title:
            tkey = re.sub(r"[《》。，！？：: ]", "", title)[:8]
            score = -1
            for f in cands:
                common = len(set(f) & set(tkey))
                if common > score:
                    best, score = f, common
        elif len(cands) == 1:
            best = cands[0]
        refs.append({
            "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
            "title": title,
            "file": best,
            "matched": bool(best),
        })
    return refs


def parse_pyramid_sections() -> tuple[list[dict], str]:
    body = drop_h1((LG_DOC_DIR / "知识金字塔-详细梳理.md").read_text(encoding="utf-8"))
    parts = re.split(r"\n## ", "\n" + body)
    intro = ""
    items = []
    for idx, p in enumerate(parts):
        if not p.strip():
            continue
        lines = p.split("\n")
        title = lines[0].strip()
        content = "\n".join(lines[1:]).strip()
        if not title or title.startswith(">"):
            intro = p.strip()
            continue
        items.append({
            "id": f"l-py-{len(items)}",
            "title": title,
            "badge": "",
            "html": md_to_html(content),
            "source": str(LG_DOC_DIR / "知识金字塔-详细梳理.md"),
        })
    return items, intro


# ---------------------------------------------------------------- 图谱

def graphml_to_json(path: Path, label: str, input_dir: Path) -> dict:
    tree = ET.parse(path)
    root = tree.getroot()
    m = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
    keymap = {k.get("id"): k.get("attr.name") or k.get("id") for k in root.findall(f"{m}key")}
    graph = root.find(f"{m}graph")

    def dataof(el):
        return {keymap.get(d.get("key"), d.get("key")): (d.text or "") for d in el.findall(f"{m}data")}

    nodes, edges = [], []
    deg = Counter()
    idmap = {}
    for nd in graph.findall(f"{m}node"):
        d = dataof(nd)
        name = d.get("entity_id") or next(iter(d.values()), "")
        etype = d.get("entity_type", "")
        desc = (d.get("description", "") or "").strip()
        files = [f for f in re.split(r"<SEP>", d.get("file_path", "") or "") if f][:3]
        idmap[nd.get("id")] = len(nodes)
        nodes.append({"n": name, "t": etype, "d": desc[:200], "f": files, "deg": 0})
    for e in graph.findall(f"{m}edge"):
        s, t = idmap.get(e.get("source")), idmap.get(e.get("target"))
        if s is None or t is None:
            continue
        d = dataof(e)
        deg[s] += 1
        deg[t] += 1
        edges.append([s, t, float(d.get("weight", 1) or 1), (d.get("keywords", "") or "")[:60], (d.get("description", "") or "").strip()[:140]])
    for i, c in deg.items():
        nodes[i]["deg"] = c

    # 轻量化：描述置空的边丢弃 keywords；按度数排序稳定输出
    order = sorted(range(len(nodes)), key=lambda i: -nodes[i]["deg"])
    remap = {old: new for new, old in enumerate(order)}
    nodes_sorted = [nodes[i] for i in order]
    edges_sorted = [[remap[s], remap[t], w, kw, de] for s, t, w, kw, de in edges]
    return {
        "label": label,
        "dataset": path.parent.name,
        "dir": str(input_dir),
        "nodes": nodes_sorted,
        "edges": edges_sorted,
    }


# ---------------------------------------------------------------- 主流程

def build() -> None:
    themes = [parse_theme(p) for p in sorted(KB_DIR.glob("0*.md"))]
    core, jhs_intro = parse_system_sections()
    index_text = (KB_DIR / "INDEX.md").read_text(encoding="utf-8")

    jhs_stats = [
        {"k": "视频", "v": "544 条"},
        {"k": "转写字数", "v": "≈190 万"},
        {"k": "主题", "v": "9 大板块"},
    ]
    lg_frameworks, lg_intro = parse_ligongzi_frameworks()
    pyramid, lg_py_intro = parse_pyramid_sections()
    lg_stats = [
        {"k": "转写", "v": "228 条"},
        {"k": "框架", "v": "9 个"},
        {"k": "含框架信号", "v": "165 条"},
    ]

    graph_jhs = graphml_to_json(
        GM_DATA / "jianghushu-methodology_b0607c" / "rag_storage" / "jianghushu-methodology_b0607c" / "graph_chunk_entity_relation.graphml",
        "姜胡说 · 方法论图谱", JHS_INPUT)
    graph_lg = graphml_to_json(
        GM_DATA / "ligongzi_9c54ca" / "rag_storage" / "ligongzi_9c54ca" / "graph_chunk_entity_relation.graphml",
        "李公子 · 图谱", LG_INPUT)
    jhs_stats.append({"k": "图谱", "v": f"{len(graph_jhs['nodes'])} 实体 · {len(graph_jhs['edges'])} 关系"})
    lg_stats.append({"k": "图谱", "v": f"{len(graph_lg['nodes'])} 实体 · {len(graph_lg['edges'])} 关系"})

    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "graphmind_url": GRAPHMIND_URL,
        "bloggers": [
            {
                "id": "jianghushu",
                "name": "姜胡说",
                "seal": "姜",
                "tagline": "每个人都有自己的江湖。活出你自己，你就是 IP。",
                "accent": "#A6402C",
                "intro": "从 544 个视频、约 190 万字转写中提炼的完整方法论体系：总框架 + 5 个核心公式 + 3 大底层思维 + 5 步方法论 + 9 大主题。",
                "doc_intro": md_to_html(jhs_intro),
                "stats": jhs_stats,
                "groups": [
                    {"id": "core", "title": "体系总览", "items": core},
                    {"id": "themes", "title": "九大主题", "items": themes},
                ],
            },
            {
                "id": "ligongzi",
                "name": "李公子",
                "seal": "李",
                "tagline": "先利他，钱是社会的奖励。",
                "accent": "#33616B",
                "intro": "9 个框架 + 知识金字塔详解；每条框架标注出处视频，可跳转本机转写原文。",
                "doc_intro": md_to_html((lg_intro + "\n\n" + lg_py_intro).strip()),
                "stats": lg_stats,
                "groups": [
                    {"id": "frameworks", "title": "九个框架", "items": lg_frameworks},
                    {"id": "pyramid", "title": "知识金字塔", "items": pyramid},
                ],
            },
        ],
        "graphs": {"jianghushu": graph_jhs, "ligongzi": graph_lg},
        "index_note": "统计口径以 kb/INDEX.md 为准（视频总数 544、ASR 完成 100%）。",
    }

    # 搜索索引
    for b in data["bloggers"]:
        for g in b["groups"]:
            for it in g["items"]:
                it["text"] = strip_tags(it["html"])[:6000]
                for r in it.get("refs", []):
                    if r.get("title"):
                        it["text"] += " " + r["title"]

    shell = (SRC_DIR / "shell.html").read_text(encoding="utf-8")
    css = (SRC_DIR / "style.css").read_text(encoding="utf-8")
    js = (SRC_DIR / "app.js").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # 防止内容里出现 </script> 提前闭合内联脚本（\/ 是 JSON 合法转义）
    payload = payload.replace("</", "<\\/")
    page = (shell
            .replace("/*__CSS__*/", css)
            .replace("\"__DATA__\"", payload)
            .replace("__GENERATED__", data["generated_at"]))
    # app.js 中数据由 shell 内联脚本提供，避免转义问题
    page = page.replace("/*__JS__*/", js)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "index.html"
    out.write_text(page, encoding="utf-8")
    size = out.stat().st_size / 1024 / 1024
    n_items = sum(len(g["items"]) for b in data["bloggers"] for g in b["groups"])
    refs_all = [r for b in data["bloggers"] for g in b["groups"] for it in g["items"] for r in it.get("refs", [])]
    matched = sum(1 for r in refs_all if r["matched"])
    print(f"OK -> {out}  ({size:.1f} MB)")
    print(f"items={n_items}  themes={len(themes)}  jhs_core={len(core)}  lg_fw={len(lg_frameworks)}  lg_py={len(pyramid)}")
    print(f"refs: {matched}/{len(refs_all)} matched")
    for r in refs_all:
        if not r["matched"]:
            print(f"  unmatched: {r['date']} {r['title']!r}")
    print(f"graphs: jhs {len(graph_jhs['nodes'])}n/{len(graph_jhs['edges'])}e  lg {len(graph_lg['nodes'])}n/{len(graph_lg['edges'])}e")


if __name__ == "__main__":
    sys.exit(build())
