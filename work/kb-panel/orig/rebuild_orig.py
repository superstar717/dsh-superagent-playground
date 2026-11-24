#!/usr/bin/env python3
"""重建修复前的 kb-bridge / kb-panel.html 原文快照（回滚用）。

方法：对现行文件逐块逆向应用本会话的精确编辑对（new→old），然后机械校验：
- py_compile 通过、旧代码锚点在、新代码锚点不在、行数与原始读取一致。
任一校验失败即 exit 1，不产出快照。
"""
from pathlib import Path
import py_compile, sys, tempfile

BIN = Path.home() / ".local" / "bin" / "kb-bridge"
PANEL = Path.home() / ".local" / "share" / "kb-panel" / "kb-panel.html"
OUT = Path(__file__).resolve().parent

b = BIN.read_text(encoding="utf-8")

B_PAIRS = []
# 1 头部注册表块 → 原 INBOX 行
B_PAIRS.append((b[b.index('INBOX = HOME / "姜胡说" / "kb_para" / "00-Inbox"'):b.index('def run(cmd: list[str], timeout: int = 180) -> dict:')],
                'INBOX = HOME / "姜胡说" / "kb_para" / "00-Inbox"\n\n\n'))
# 2 三个 handler（summary/synth/ctx）→ 原版
new_handlers = b[b.index('        if u.path == "/api/summary":'):b.index('        if u.path == "/search":')]
old_handlers = '''        if u.path == "/api/summary":
            if not q:
                return self._send(400, ERR_Q, "application/json; charset=utf-8")
            return self._send(200, json.dumps(self._summary(q), ensure_ascii=False).encode(),
                              "application/json; charset=utf-8")
        if u.path == "/api/synth":
            if not q:
                return self._send(400, ERR_Q, "application/json; charset=utf-8")
            return self._send(200, json.dumps(self._synth(q), ensure_ascii=False).encode(),
                              "application/json; charset=utf-8")
        if u.path == "/api/ctx":
            if not q:
                return self._send(400, ERR_Q, "application/json; charset=utf-8")
            ALIAS = {"para": ["pama", "帕拉"], "obsidian": ["奥布斯林", "黑药石"], "notion": ["诺申"]}
            EXPAND = {"PARA": "项目 资产 资源 归档 目录",
                      "OBSIDIAN": "奥布斯林 笔记 工具 markdown",
                      "AI": "人工智能 知识库"}
            dsid = ds or "jianghushu-methodology_b0607c"
            try:
                exp = EXPAND.get(q.strip().upper(), "")
                q_eff = (q + " " + " ".join(ALIAS.get(q.strip().lower(), [])) + " " + exp).strip()
                body = json.dumps({"query": q_eff, "mode": "mix"}).encode()
                req = urllib.request.Request(f"http://127.0.0.1:8777/api/datasets/{dsid}/search/context",
                                             data=body, method="POST")
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=240) as resp:
                    raw = json.loads(resp.read().decode())
                c = raw.get("context") or ""
            except Exception as e:
                return self._send(502, json.dumps({"ok": False, "error": str(e)[:200]}, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            def grab(pat):
                return [{"a": a, "b": b, "c": c3} for a, b, c3 in re.findall(pat, c, re.S)]
            ents = [{"name": a, "type": b, "desc": d3} for a, b, d3 in
                    re.findall(r'\\{"entity": "(.*?)", "type": "(.*?)", "description": "(.*?)"\\}', c, re.S)]
            rels = [{"from": a, "to": b, "desc": d3} for a, b, d3 in
                    re.findall(r'\\{"entity1": "(.*?)", "entity2": "(.*?)", "description": "(.*?)"\\}', c, re.S)]
            refs = [{"id": a, "name": b.strip()} for a, b in re.findall(r"\\[(\\d+)\\]\\s*([^\\[\\]]*?\\.txt)", c)]
            chunks = [{"id": a, "text": b[:1200]} for a, b in
                      re.findall(r'\\{"reference_id": "(\\d+)", "content": "(.*?)"(?:,|\\})', c, re.S)]
            # 相关性过滤：查询词（含音译变体）出现在名称/描述/原文里才算命中
            qv = {q.lower()}
            for k, vs in ALIAS.items():
                if k in q.lower():
                    qv.update(v.lower() for v in vs)
            def rel(txt):
                s = (txt or "").lower()
                return any(v and v in s for v in qv)
            ent_rel = [e for e in ents if rel(e.get("name")) or rel(e.get("desc"))]
            rel_rel = [r for r in rels if rel(r.get("from") + r.get("to") + r.get("desc"))]
            ch_rel = [c for c in chunks if rel(c.get("text"))]
            return self._send(200, json.dumps({"ok": True, "dataset": dsid, "query": q,
                                               "entities": ent_rel, "relations": rel_rel, "refs": refs,
                                               "chunks": ch_rel, "raw_len": len(c),
                                               "totals": {"entities": len(ents), "relations": len(rels),
                                                          "chunks": len(chunks)},
                                               "variants": sorted(qv), "query_effective": q_eff}, ensure_ascii=False).encode(),
                              "application/json; charset=utf-8")
'''
B_PAIRS.append((new_handlers, old_handlers))
# 3 _vault 头
B_PAIRS.append(('''    _VAULT_CACHE = {}

    def _vault(self, q, limit=25, dirs=None):
        """在指定 Obsidian 库目录里搜，返回 文件 / 所在标题 / 命中行。dirs 为空=该数据集无笔记库。"""
        if dirs is None:
            dirs = [HOME / "姜胡说" / "kb_para", HOME / "姜胡说" / "kb"]
        key = tuple(str(d) for d in dirs)
        if key not in self._VAULT_CACHE:
            self._VAULT_CACHE[key] = [d for d in dirs if d.is_dir()]
        dirs = self._VAULT_CACHE[key]
        hits = []
        import subprocess as sp
        for d in dirs:''',
'''    VAULT_DIRS = None

    def _vault(self, q, limit=25):
        """在 Obsidian 库里搜（kb_para + kb），返回 文件 / 所在标题 / 命中行。"""
        if self.VAULT_DIRS is None:
            cand = [HOME / "姜胡说" / "kb_para", HOME / "姜胡说" / "kb"]
            type(self).VAULT_DIRS = [d for d in cand if d.is_dir()]
        hits = []
        import subprocess as sp
        for d in self.VAULT_DIRS:'''))
# 4 _vault 返回 dirs 行
B_PAIRS.append(('                "dirs": [str(d.relative_to(HOME / "姜胡说")) for d in dirs],',
                '                "dirs": [str(d.relative_to(HOME / "姜胡说")) for d in (self.VAULT_DIRS or [])],'))
# 5 _synth 头 + asr 循环 → 原版
new_synth_head = b[b.index('    def _synth(self, q, ds="", use_llm=False):'):b.index('        def clean(s):')]
old_synth_head = '''    def _synth(self, q, use_llm=False):
        """检索 + 取舍：把命中按价值分级，给出 一句话 / 要点 / 证据 / 概念 / 下一步。"""
        v = self._vault(q, limit=200)
        hits = v.get("hits", [])
        # 原话层：ASR 语料里也搜一遍（含音译变体）。rg 对超长行只回 [Omitted]，所以先定位文件再读原文截取
        import subprocess as sp
        variants = [q]
        for k, vs in {"para": ["pama", "帕拉"], "obsidian": ["奥布斯林", "黑药石"]}.items():
            if k in q.lower():
                variants += vs
        asr_dir = HOME / "姜胡说" / "asr"
        asr_added = set()
        if asr_dir.is_dir():
            for vv in variants:
                try:
                    r = sp.run(["rg", "-l", "--color", "never", "-m", "1", "--", vv, str(asr_dir)],
                               capture_output=True, text=True, timeout=20)
                except Exception:
                    continue
                for fp in (r.stdout or "").splitlines()[:1]:
                    if fp in asr_added:
                        continue
                    try:
                        body = pathlib.Path(fp).read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    i = body.find(vv)
                    if i < 0:
                        continue
                    snippet = body[max(0, i - 60): i + 120].replace("\\n", " ").strip()
                    asr_added.add(fp)
                    # 只靠音译命中时，再用上下文词判定是否真相关（如 PARA 的 项目/资产/资源/归档）
                    alias_hit = vv.lower() != q.lower()
                    ctx_terms = [x for x in {"PARA": ["项目", "资产", "资源", "归档", "目录"],
                                             "OBSIDIAN": ["笔记", "工具", "马克当"]}.get(q.strip().upper(), [])]
                    if alias_hit and ctx_terms and any(x in snippet for x in ctx_terms):
                        alias_hit = False
                    hits.append({"file": "asr/" + pathlib.Path(fp).name, "heading": "原话",
                                 "line": 0, "text": snippet, "more": 0,
                                 "alias_only": alias_hit})

'''
B_PAIRS.append((new_synth_head, old_synth_head))
# 6 weight asr 前缀
B_PAIRS.append(('''        def weight(path, text):
            w = 5
            if path.startswith("asr"):  # asr/ 与 asr_simplified_ligongzi/ 等各数据集 ASR 目录同权
                w = 10''',
'''        def weight(path, text):
            w = 5
            if path.startswith("asr/"): w = 10'''))
# 7 brief/概念块
new_brief = b[b.index('        brief = ""'):b.index('        nxt = []')]
old_brief = '''        brief = ""
        if scored:
            top = scored[0]
            brief = ("「%s」在你的库里有 %d 篇笔记提到；最相关的是 %s%s。"
                     % (q, len(notes), top["file"].replace("kb_para/", ""),
                        ("（" + top["heading"] + "）") if top.get("heading") else ""))
            if high:
                brief += " 其中 " + str(len(high)) + " 条是方法论/结论级的内容，其余多为目录与模板样板。"
        else:
            brief = "库里没有命中「%s」。换个说法，或用它的英文/音译写法再试。" % q

        para = []
        for d, label in (("10-Projects", "项目 Projects"), ("20-Areas", "领域/资产 Areas"),
                         ("30-Resources", "资源 Resources"), ("40-Archives", "归档 Archives")):
            n = len(list((HOME / "姜胡说" / "kb_para" / d).rglob("*.md"))) if (HOME / "姜胡说" / "kb_para" / d).is_dir() else 0
            para.append({"k": label, "v": str(n) + " 篇"})

'''
B_PAIRS.append((new_brief, old_brief))
# 8 返回块
B_PAIRS.append(('''        return {"ok": True, "llm": llm_used, "query": q, "brief": brief,
                "dataset": dsc["id"], "dataset_label": dsc["label"],
                "source_note": dsc["source_note"], "graph_first": dsc["graph_first"],
                "stats": {"hits": len(scored), "notes": len(notes), "high": len(high),
                          "mid": len(mid), "low": len(low)},
                "points": points,
                "evidence": {"high": [{"text": clean(x["text"]), "file": x["file"], "heading": x["heading"]} for x in (high + mid)[:12]],
                             "low": [{"text": clean(x["text"]), "file": x["file"]} for x in low[:40]],
                             "low_count": len(low)},
                "concepts": para, "concepts_note": concepts_note,
                "next": nxt, "dirs": v.get("dirs", [])}''',
'''        return {"ok": True, "llm": llm_used, "query": q, "brief": brief,
                "stats": {"hits": len(scored), "notes": len(notes), "high": len(high),
                          "mid": len(mid), "low": len(low)},
                "points": points,
                "evidence": {"high": [{"text": clean(x["text"]), "file": x["file"], "heading": x["heading"]} for x in (high + mid)[:12]],
                             "low": [{"text": clean(x["text"]), "file": x["file"]} for x in low[:40]],
                             "low_count": len(low)},
                "concepts": para, "next": nxt, "dirs": v.get("dirs", [])}'''))
# 9 _script_variants + _summary 签名
B_PAIRS.append(('''    @staticmethod
    def _script_variants(q):
        """繁简互转变体（与 kgrep 同一逻辑）；opencc 不可导入就不加，不影响主流程。"""
        out = []
        try:
            import sys as _sys
            _sys.path.insert(0, str(HOME / ".local" / "lib" / "opencc_pkg"))
            from opencc import OpenCC
            for v in (OpenCC("t2s").convert(q), OpenCC("s2t").convert(q)):
                if v and v != q and v not in out:
                    out.append(v)
        except Exception:
            pass
        return out

    def _summary(self, q, ds=""):''', '    def _summary(self, q):'))
# 10 _summary docstring + 材料池
new_pool = b[b.index('        """把检索结果交给本机模型提炼'):b.index('        lines = []')]
old_pool = '''        """把检索结果交给本机模型提炼成「一句话 + 要点」，来源限定在检索到的文件里。"""
        base = self._synth(q)
        pool = (base.get("evidence", {}).get("high") or [])[:10]
        if len(pool) < 2:
            return {"ok": False, "error": "可用材料不足", "llm": False}
'''
B_PAIRS.append((new_pool, old_pool))
# 11 _summary 解析失败返回
B_PAIRS.append(('''            return {"ok": False, "error": "模型输出无法解析", "llm": False, "raw_len": len(raw or ""),
                    "dataset": dsc["id"], "dataset_label": dsc["label"],
                    "source_note": dsc["source_note"] + graph_note}''',
'''            return {"ok": False, "error": "模型输出无法解析", "llm": False, "raw_len": len(raw or "")}'''))
# 12 _summary 成功返回
B_PAIRS.append(('''        tb = got.get("table") or {}
        fl = got.get("flow") or {}
        if dsc["graph_first"] and graph_chunks_used:
            note = "AI 提炼 · 来源：知识图谱 %s（图谱优先）+ 本地 ASR%s" % (dsc["graph"], graph_note)
        elif dsc["graph_first"]:
            note = "AI 提炼 · 图谱没有相关原文块，本次要点仅来自本地 ASR（%s本地语料很少）%s" % (dsc["label"], graph_note)
        else:
            note = "AI 提炼 · 来源限于本地检索结果"
        return {"ok": True, "llm": True, "query": q,
                "dataset": dsc["id"], "dataset_label": dsc["label"], "source_note": note,
                "summary": str(got.get("summary") or "")[:400], "points": pts,''',
'''        tb = got.get("table") or {}
        fl = got.get("flow") or {}
        return {"ok": True, "llm": True, "query": q,
                "summary": str(got.get("summary") or "")[:400], "points": pts,'''))

for i, (new, old) in enumerate(B_PAIRS, 1):
    if new not in b:
        print(f"FAIL: 第{i}块的「新代码」没在现行文件里找到（写错了逆向对）")
        sys.exit(1)
    b = b.replace(new, old)

# 校验
with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
    tf.write(b); tmp = tf.name
py_compile.compile(tmp, doraise=True)
assert "VAULT_DIRS = None" in b, "旧锚点缺失"
for gone in ("DATASETS = {", "def resolve_ds", "def graph_fetch", "_script_variants", "source_note"):
    assert gone not in b, f"新代码残留: {gone}"
n_lines = b.count("\n")
print(f"kb-bridge 原文重建 OK：{n_lines} 行（原始读取为 576 行）")
assert n_lines == 576, f"行数不符：{n_lines} != 576"
(OUT / "kb-bridge").write_text(b, encoding="utf-8")
print("written:", OUT / "kb-bridge")
