#!/usr/bin/env python3
"""知乎专栏 HTML → 整理 Markdown（含表格还原、配图本地化、zhida 噪声剔除）。

用法: python3 zhihu_html_to_md.py <saved_html> <out_dir>
产出: <out_dir>/article.md 与 <out_dir>/images/*.jpg
依赖: pip install beautifulsoup4 lxml
要点（本次实战结论）:
  - 表格必须用 <table> 结构还原为 Markdown 表格，直接 get_text 会挤成一坨
  - 图片优先 data-actualsrc（原图 _r.jpg，2559px），其次 data-original/src（1440w）
  - zhida.zhihu.com 词条链接是纯噪声（含 500+ 字符 JWT），一律拍平为纯文本
  - 元信息: h1.Post-Title / .AuthorInfo-name / .AuthorInfo-badgeText / .ContentItem-time
    / meta[itemprop=datePublished] / "voteupCount" / "column" JSON
"""
import hashlib, json, os, re, subprocess, sys
from bs4 import BeautifulSoup, NavigableString, Tag

SRC = sys.argv[1] if len(sys.argv) > 1 else ""
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else ""
if not SRC or not OUT_DIR:
    sys.exit("usage: zhihu_html_to_md.py <saved_html> <out_dir>")
IMG_DIR = os.path.join(OUT_DIR, "images")
os.makedirs(IMG_DIR, exist_ok=True)

html = open(SRC, encoding="utf-8").read()
soup = BeautifulSoup(html, "lxml")

title_el = soup.select_one("h1.Post-Title") or soup.select_one("h1")
title = title_el.get_text(strip=True)
author_el = soup.select_one(".AuthorInfo-name") or soup.select_one(".Post-Author")
author_name = author_el.get_text(strip=True) if author_el else ""
badge_el = soup.select_one(".AuthorInfo-badgeText")
badge = badge_el.get_text(strip=True) if badge_el else ""
time_el = soup.select_one(".ContentItem-time")
time_txt = time_el.get_text(strip=True) if time_el else ""
meta_date = soup.select_one('meta[itemprop="datePublished"]')
date_pub = meta_date.get("content") if meta_date else ""
m_vote = re.search(r'"voteupCount":\s*(\d+)', html)
voteup = int(m_vote.group(1)) if m_vote else None
m_col = re.search(r'"column":\s*\{[^}]*?"(?:title|name)":"([^"]+)"', html)
column = m_col.group(1) if m_col else ""
url_match = re.search(r'<meta itemprop="url" content="([^"]+)"', html) or re.search(
    r'<link rel="canonical" href="([^"]+)"', html)
source_url = url_match.group(1) if url_match else ""

body = (soup.select_one("div.Post-RichTextContainer > div")
        or soup.select_one("div.Post-RichTextContainer")
        or soup.select_one(".RichText"))

downloaded = {}

def download_image(url: str) -> str:
    key = url.split("?")[0]
    if key in downloaded:
        return downloaded[key]
    name = hashlib.md5(key.encode()).hexdigest()[:12] + "-" + key.rsplit("/", 1)[-1]
    dest = os.path.join(IMG_DIR, name)
    ok = os.path.exists(dest) and os.path.getsize(dest) > 1000  # 幂等：已有则不重下
    for _ in range(2):  # CDN 偶发失败，重试一次
        if ok:
            break
        r = subprocess.run(["curl", "-sL", "--max-time", "30", "-A",
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
                            "-o", dest, url], capture_output=True)
        ok = r.returncode == 0 and os.path.exists(dest) and os.path.getsize(dest) > 1000
    if ok:
        downloaded[key] = f"images/{name}"
        return downloaded[key]
    downloaded[key] = url
    return url

def render(node):
    if isinstance(node, NavigableString):
        return str(node)
    if not isinstance(node, Tag):
        return ""
    name = node.name
    if name in ("script", "style"):
        return ""
    if name == "img":
        src = (node.get("data-actualsrc") or node.get("data-original") or node.get("src") or "").strip()
        if not src:
            return ""
        return f'![{(node.get("alt") or "").strip()}]({download_image(src)})'
    if name == "br":
        return "\n"
    inner = "".join(render(c) for c in node.children)
    if name in ("h1", "h2"):
        return f"\n\n## {inner.strip()}\n\n"
    if name == "h3":
        return f"\n\n### {inner.strip()}\n\n"
    if name in ("b", "strong"):
        return f" **{inner.strip()}** " if inner.strip() else ""
    if name in ("i", "em"):
        return f" *{inner.strip()}* " if inner.strip() else ""
    if name == "a":
        href = node.get("href") or ""
        if href.startswith("/"):
            href = "https://zhuanlan.zhihu.com" + href
        t = inner.strip()
        if not t:
            return ""
        if "zhida.zhihu.com" in href:
            return t  # 词条链接=噪声，拍平
        return f"[{t}]({href})" if href.startswith("http") else t
    if name == "blockquote":
        return "\n\n" + "\n".join("> " + ln for ln in inner.strip().split("\n")) + "\n\n"
    if name == "table":
        rows = []
        for tr in node.select("tr"):
            cells = [" ".join(render(c).split()) for c in tr.select("th,td")]
            if cells:
                rows.append(cells)
        if not rows:
            return ""
        out = ["\n", "| " + " | ".join(rows[0]) + " |",
               "|" + "|".join([" --- " for _ in rows[0]]) + "|"]
        for r in rows[1:]:
            r = r + [""] * (len(rows[0]) - len(r))
            out.append("| " + " | ".join(r[: len(rows[0])]) + " |")
        return "\n".join(out) + "\n\n"
    if name in ("ul", "ol"):
        return "\n\n" + inner + "\n\n"
    if name == "li":
        return "- " + inner.strip() + "\n"
    if name == "p":
        return "\n\n" + inner.strip() + "\n\n" if inner.strip() else "\n\n"
    if name == "figure":
        return "\n\n" + inner.strip() + "\n\n"
    if name == "hr":
        return "\n\n---\n\n"
    return inner

md_body = re.sub(r"\n{3,}", "\n\n", render(body)).strip()

md = [f"# {title}\n"]
if source_url:
    md.append(f"> 来源：[{title}]({source_url})\n>")
md.append(f"> 作者：{author_name}" + (f"（{badge}）" if badge else ""))
if column:
    md.append(f"> 收录于专栏：{column}")
if date_pub:
    md.append(f"> 发布：{date_pub[:10]}" + (f" ｜ 最后编辑：{time_txt}" if time_txt else ""))
if voteup is not None:
    md.append(f"> 数据：{voteup} 人赞同")
md += ["", "---\n", md_body, "", "---\n",
       "*本文由自动化代理自知乎专栏抓取整理，正文内容与图片版权归原作者所有。*\n"]

with open(os.path.join(OUT_DIR, "article.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(md))

print(json.dumps({
    "title": title, "author": author_name, "column": column,
    "md_chars": len(md_body), "images": len(downloaded),
    "local_ok": sum(1 for v in downloaded.values() if v.startswith("images/")),
}, ensure_ascii=False, indent=2))
