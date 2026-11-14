#!/usr/bin/env python3
"""面板取证：选数据集 → 输入关键词 → 点「梳理」→ 截图 + 抓取左右栏证据。

用法: python3 shot_panel.py <输出前缀> [--ds ligongzi_9c54ca] [--q 捷径] [--ds-label 李公子]
产物: <前缀>.png（全页截图） + <前缀>.json（左右栏文本证据）
"""
import argparse, json, sys, time
from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("prefix")
ap.add_argument("--ds", default="ligongzi_9c54ca")
ap.add_argument("--ds-label", default="李公子")
ap.add_argument("--q", default="捷径")
ap.add_argument("--max-wait", type=int, default=150, help="等待 AI 提炼 + 图谱的最长秒数")
a = ap.parse_args()

evid = {"ds": a.ds, "q": a.q, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 950})
    pg.goto("http://127.0.0.1:8790/", wait_until="domcontentloaded", timeout=20000)
    pg.click("#mode")  # 面板默认「阅读视图」，main 隐藏；切到工具视图才有检索控件
    pg.wait_for_selector("#ds", state="visible", timeout=10000)
    pg.select_option("#ds", a.ds)
    pg.fill("#q", a.q)
    pg.click("#go")
    # 等 AI 提炼落地（#srcnote 变为 AI 提炼）或超时
    t0 = time.time()
    while time.time() - t0 < min(60, a.max_wait):
        sn = pg.text_content("#srcnote") or ""
        if "AI 提炼" in sn or "来源" in sn:
            break
        time.sleep(1)
    # 再等图谱卡出结果（实体 pill 或 warnbox）或超时
    t1 = time.time()
    while time.time() - t1 < a.max_wait:
        g = (pg.text_content("#graph") or "").strip()
        if g and "检索中" not in g:
            break
        time.sleep(2)
    time.sleep(1)
    evid["srcnote"] = (pg.text_content("#srcnote") or "").strip()
    evid["brief"] = (pg.text_content("#brief") or "").strip()
    evid["stat"] = (pg.text_content("#stat") or "").strip()
    evid["points_sources"] = pg.eval_on_selector_all(".point .src", "els=>els.map(e=>e.textContent.trim())")
    evid["evidence_files"] = pg.eval_on_selector_all("#evid .row .p", "els=>els.map(e=>e.textContent.trim())")
    evid["graph_card"] = (pg.text_content("#graph") or "").strip()
    evid["concepts"] = (pg.text_content("#concepts") or "").strip()
    pg.screenshot(path=a.prefix + ".png", full_page=True)
    b.close()

json.dump(evid, open(a.prefix + ".json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(evid, ensure_ascii=False, indent=1))
