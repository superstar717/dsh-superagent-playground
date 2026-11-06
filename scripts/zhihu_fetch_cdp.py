#!/usr/bin/env python3
"""抓取知乎专栏文章（渲染后的 HTML），经本机 bb-browser 托管 Chrome（CDP）。

用法: python3 zhihu_fetch_cdp.py <article_url> <out_html_path>
依赖: python3 -c "import playwright" ；bb-browser 托管 Chrome 运行于 127.0.0.1:19825
要点（LESSONS E86）:
  - Chrome 无标签页时先建: curl -X PUT "http://127.0.0.1:19825/json/new?about:blank"
  - curl 直连知乎 403 = 反爬（TLS/指纹），非登录态问题；公开页真实浏览器渲染即可读
"""
import json, sys
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else ""
OUT_HTML = sys.argv[2] if len(sys.argv) > 2 else "/tmp/zhihu_article.html"
if not URL:
    sys.exit("usage: zhihu_fetch_cdp.py <article_url> [out_html]")

CDP = "http://127.0.0.1:19825"
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(45000)
    try:
        resp = page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        status = resp.status if resp else None
    except Exception as e:
        status = f"goto-error: {e}"
    page.wait_for_timeout(4000)  # SPA 渲染
    html = page.content()
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    body = page.query_selector("div.Post-RichTextContainer") or page.query_selector(".RichText")
    print(json.dumps({
        "url": page.url, "http_status": status, "title": page.title(),
        "html_bytes": len(html), "body_found": bool(body),
        "body_chars": len(body.inner_text()) if body else 0,
    }, ensure_ascii=False))
    page.close()
