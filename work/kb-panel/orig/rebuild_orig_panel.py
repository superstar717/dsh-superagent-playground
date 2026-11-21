#!/usr/bin/env python3
"""重建修复前的 kb-panel.html 原文快照（回滚用）。方法与校验同 rebuild_orig.py。"""
from pathlib import Path
import sys

PANEL = Path.home() / ".local" / "share" / "kb-panel" / "kb-panel.html"
OUT = Path(__file__).resolve().parent

h = PANEL.read_text(encoding="utf-8")
P = []
# 1 run() 的 ds 传参
P.append(("""  var ds=$('#ds').value;
  // 分别渲染：知识库/原话很快出，图谱慢，不互相等；梳理/AI 提炼与图谱用同一个数据集（ds）
  fetch('/api/synth?q='+encodeURIComponent(q)+'&ds='+encodeURIComponent(ds)).then(function(r){return r.json()}).then(function(s){
    st.synth=s; renderSynth(s,q);
    if(MODE==='reading'){ document.getElementById('rd-lead').textContent = (s.brief||'')+'（AI 正在提炼…）'; }
    fetchSummary(q,ds);""",
"""  var ds=$('#ds').value;
  // 分别渲染：知识库/原话很快出，图谱慢，不互相等
  fetch('/api/synth?q='+encodeURIComponent(q)).then(function(r){return r.json()}).then(function(s){
    st.synth=s; renderSynth(s,q);
    if(MODE==='reading'){ document.getElementById('rd-lead').textContent = (s.brief||'')+'（AI 正在提炼…）'; }
    fetchSummary(q);"""))
# 2 fetchSummary 头
P.append(("""function fetchSummary(q,ds){
  fetch('/api/summary?q='+encodeURIComponent(q)+(ds?'&ds='+encodeURIComponent(ds):'')).then(function(r){return r.json()}).then(function(d){
    if(!d.ok || !d.points || !d.points.length){ graphPointsFallback(); return; }
    if(st.q !== q) return;                      // 已被新的检索取代
    st.summary = d;
    $('#brief').textContent = d.summary || ($('#brief').textContent);
    $('#srcnote').textContent = d.source_note || 'AI 提炼 · 来源限于检索结果';""",
"""function fetchSummary(q){
  fetch('/api/summary?q='+encodeURIComponent(q)).then(function(r){return r.json()}).then(function(d){
    if(!d.ok || !d.points || !d.points.length) return;
    if(st.q !== q) return;                      // 已被新的检索取代
    st.summary = d;
    $('#brief').textContent = d.summary || ($('#brief').textContent);
    $('#srcnote').textContent = 'AI 提炼 · 来源限于检索结果';"""))
# 3 图谱兜底块 → 原样
P.append(("""    toast('AI 提炼完成（'+d.points.length+' 条要点）', true);
  }).catch(function(){ graphPointsFallback(); });
}
// AI 提炼失败时的兜底：图谱优先的数据集（李公子）直接用图谱原文块出要点，并明确标注来源
function graphPointsFallback(){
  if(st.q !== (document.getElementById('q').value||'').trim()) return;
  if(!(st.synth&&st.synth.graph_first)) return;          // 本地语料充足的数据集保持原样
  var chs=(st.ctx&&st.ctx.chunks)||[];
  if(!chs.length) return;
  var h='';
  chs.slice(0,5).forEach(function(x,i){
    h+='<div class="point"><div class="n">'+String(i+1).padStart(2,'0')+'<span class="tag mid">图谱要点</span></div>'
      +'<div class="claim">'+hl(claimify(x.text),st.q)+'</div>'
      +'<div class="src">出处：知识图谱 '+esc((st.ctx&&st.ctx.dataset)||'')+' · 原文块</div></div>';
  });
  if(h){ $('#points').innerHTML=h;
    $('#srcnote').textContent='AI 提炼失败，展示图谱原文要点（来源：知识图谱）';
    toast('AI 提炼失败，已用图谱原文块兜底', false); }
}""",
"""    toast('AI 提炼完成（'+d.points.length+' 条要点）', true);
  }).catch(function(){});
}"""))
# 4 renderSynth srcnote
P.append(("""  $('#srcnote').textContent=s.source_note || '规则分级，非 LLM 改写';""",
"""  $('#srcnote').textContent='规则分级，非 LLM 改写';"""))
# 5 概念卡
P.append(("""  if(!(s.concepts||[]).length && s.concepts_note){cf='<div class="note">'+esc(s.concepts_note)+'</div>'}
  else cf+='<div class="note">目录规模来自本数据集笔记库实际统计；定义正文在左侧要点里，两边不重复。</div>';""",
"""  cf+='<div class="note">目录规模来自 kb_para 实际统计；定义正文在左侧要点里，两边不重复。</div>';"""))
# 6 首页说明文案
P.append(("""      <div class="brief" id="brief">输入关键词 → 按上方所选数据集，在 <b>本地库/ASR</b> 与 <b>知识图谱</b> 里找，按价值分级排版；来源随数据集标注。</div>""",
"""      <div class="brief" id="brief">输入关键词 → 同时在 <b>Obsidian 库</b>、<b>ASR 原话</b>、<b>知识图谱</b> 里找，然后按价值分级排版。</div>"""))
# 7 saveMain
P.append(("""function saveMain(){if(!st.synth)return toast('先检索',false);
  post(st.q+' · 知识库梳理（'+((st.synth.dataset_label)||'')+'）','来源标注：'+($('#srcnote').textContent||'')+'\\n\\n'+($('#brief').innerText||'')+'\\n\\n'+($('#points').innerText||''),'','synth')}""",
"""function saveMain(){if(!st.synth)return toast('先检索',false);
  post(st.q+' · 知识库梳理',($('#brief').innerText||'')+'\\n\\n'+($('#points').innerText||''),'','synth')}"""))

for i, (new, old) in enumerate(P, 1):
    if new not in h:
        print(f"FAIL: 面板第{i}块的「新代码」没找到")
        sys.exit(1)
    h = h.replace(new, old)

assert "graphPointsFallback" not in h, "兜底代码残留"
for gone in ("source_note", "concepts_note", "graph_first",
             "'/api/synth?q='+encodeURIComponent(q)+'&ds='",
             "'/api/summary?q='+encodeURIComponent(q)+(ds?", "fetchSummary(q,ds)"):
    assert gone not in h, f"新代码残留: {gone}"
assert "'/api/synth?q='+encodeURIComponent(q)).then" in h, "旧 synth fetch 缺失"
assert "'/api/summary?q='+encodeURIComponent(q)).then" in h, "旧 summary fetch 缺失"
assert "fetch('/api/ctx?q='+encodeURIComponent(q)+'&ds='+encodeURIComponent(ds))" in h, "ctx 的 ds 传参应保留"
n_lines = h.count("\n")
print(f"kb-panel.html 原文重建 OK：{n_lines} 行（原始读取为 328 行）")
assert n_lines == 328, f"行数不符：{n_lines} != 328"
(OUT / "kb-panel.html").write_text(h, encoding="utf-8")
print("written:", OUT / "kb-panel.html")
