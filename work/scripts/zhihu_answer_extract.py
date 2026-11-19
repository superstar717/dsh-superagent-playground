#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zhihu_answer_extract.py — 知乎回答的身份核验式精确提取.

解决 zhihu_reader.py 整页提取(trafilatura)的两类噪声: 页头登录角标 + 「更多回答」混入的其他答主内容.
原理: 知乎回答页内嵌 <script id="js-initialData"> JSON, 内含该回答的 author/content/excerpt;
按 answer id 精确定位, 只输出目标回答的正文, 天然免疫页面噪声.

用法:
    python3 zhihu_answer_extract.py <知乎回答URL> [--out 输出.md] [--json]
    # URL 形态: https://www.zhihu.com/question/{qid}/answer/{aid} 或 https://www.zhihu.com/answer/{aid}

输出 md 结构: 元信息(问题/作者/链接/抓取时间) + 正文纯文本.
依赖: DrissionPage; 登录态复用 ~/.zhihu_reader_dp(借 zhihu_reader.make_page).
退出码: 0 成功; 1 页面/数据问题; 2 浏览器启动失败.
"""
import argparse
import json
import re
import sys
from datetime import date
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path.home() / "bin"))
from zhihu_reader import make_page  # noqa: E402  复用建页逻辑(空闲端口+登录态)

USER_DATA = str(Path.home() / ".zhihu_reader_dp")


def answer_id_of(url: str) -> str:
    """从 URL 提取 answer id: 取路径最后一段数字."""
    seg = urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]
    if not seg.isdigit():
        raise ValueError(f"URL 中未找到回答 id: {url}")
    return seg


def find_answers(node, aid: str, hits: list) -> None:
    """递归找 JSON 里 id==aid 且带 content 的回答对象."""
    if isinstance(node, dict):
        if str(node.get("id")) == aid and "content" in node:
            hits.append(node)
        for v in node.values():
            find_answers(v, aid, hits)
    elif isinstance(node, list):
        for v in node:
            find_answers(v, aid, hits)


def html_to_text(html: str) -> str:
    """轻量 HTML→文本: 块级标签转换行, 去标签, 反转义实体."""
    s = re.sub(r"(?i)</(p|div|br|li|h\d|blockquote|pre)>", "\n", html)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    lines = [ln.strip() for ln in unescape(s).splitlines()]
    return "\n\n".join(ln for ln in lines if ln)


def extract(aid: str) -> dict:
    """启动登录态浏览器, 读 js-initialData, 返回目标回答的元信息与纯文本正文."""
    from DrissionPage import ChromiumPage

    page = make_page("new", USER_DATA, 9222, False)
    try:
        page.get(f"https://www.zhihu.com/answer/{aid}")
        page.wait.doc_loaded(timeout=30)
        ele = page.ele("css:script#js-initialData", timeout=10)
        if not ele:
            raise RuntimeError("页面未找到 js-initialData(可能被登录墙/验证拦截)")
        hits: list[dict] = []
        find_answers(json.loads(ele.inner_html), aid, hits)
        if not hits:
            raise RuntimeError(f"initialData 中未找到 answer id {aid}(回答可能不存在或被删除)")
        a = hits[0]
        question = ""
        try:
            q = page.ele("css:h1.QuestionHeader-title", timeout=5)
            question = (q.text or "").strip() if q else ""
        except Exception:
            pass
        return {
            "answer_id": aid,
            "author": (a.get("author") or {}).get("name", "未知作者"),
            "question": question,
            "url": f"https://www.zhihu.com/question/{a.get('question', {}).get('id', '')}/answer/{aid}",
            "excerpt": (a.get("excerpt") or "").strip(),
            "text": html_to_text(a.get("content") or ""),
        }
    finally:
        try:
            page.quit()
        except Exception:
            pass


def to_markdown(r: dict) -> str:
    """拼装落地 md: 元信息头 + 正文."""
    return (
        f"# {r['question'] or '(问题标题未取到)'}（知乎回答）\n\n"
        f"- 作者：{r['author']}\n"
        f"- 链接：{r['url']}\n"
        f"- 抓取：{date.today().isoformat()}，zhihu_answer_extract.py（js-initialData 按 answer id 精确提取，已核验身份）\n\n"
        f"## 正文\n\n{r['text']}\n"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="知乎回答身份核验式精确提取")
    p.add_argument("url", help="知乎回答 URL")
    p.add_argument("--out", default="", help="写入的 markdown 路径; 不传则打印 stdout")
    p.add_argument("--json", action="store_true", help="额外打印元信息 JSON(不含正文)")
    args = p.parse_args()
    try:
        aid = answer_id_of(args.url)
    except ValueError as e:
        print(f"[参数错误] {e}", file=sys.stderr)
        sys.exit(1)
    try:
        r = extract(aid)
    except Exception as e:
        print(f"[提取失败] {type(e).__name__}: {e}", file=sys.stderr)
        print("提示: 登录态目录 ~/.zhihu_reader_dp 被占用时, 先清理残留 Chrome 进程再试.", file=sys.stderr)
        sys.exit(1)
    if len(r["text"]) < 100:
        print(f"[警告] 正文仅 {len(r['text'])} 字符, 请人工确认是否为空回答/被折叠.", file=sys.stderr)
    md = to_markdown(r)
    if args.out:
        Path(args.out).write_text(md, encoding="utf-8")
        print(f"[已写入] {args.out} (正文 {len(r['text'])} 字符, 作者 {r['author']})")
    else:
        print(md)
    if args.json:
        meta = {k: v for k, v in r.items() if k != "text"}
        print(json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    main()
