# 知乎专栏抓取流水线（2026-11-06 实战固化）

## 用法（两步）

```bash
# 1) 经本机 bb-browser 托管 Chrome 渲染抓 HTML（curl 直连知乎会 403，属反爬非登录态问题）
python3 scripts/zhihu_fetch_cdp.py "https://zhuanlan.zhihu.com/p/xxxx" /tmp/zhihu.html

# 2) HTML → 整理 Markdown + 配图本地化
python3 scripts/zhihu_html_to_md.py /tmp/zhihu.html zhihu-article
```

## 前提检查（LESSONS E86）

```bash
# bb-browser 托管 Chrome 必须有至少一个标签页，否则全部报 "No page target found"
curl -s http://127.0.0.1:19825/json/list | grep -c '"type": "page"'   # 为 0 时先建:
curl -X PUT "http://127.0.0.1:19825/json/new?about:blank"
```

- 托管实例 profile（`~/.bb-browser/browser/user-data`）**独立于用户日常浏览器**，未必有目标站登录态；公开页面无需登录即可抓。
- 依赖：`python3 -c "import playwright"`（CDP 连接）与 `beautifulsoup4 + lxml`（解析）。

## 已验证

2026-11-06 在 zhuanlan.zhihu.com/p/2092727841804784619 全流程跑通：正文完整、2 张表格还原、10 张原尺寸配图本地化（2559×1494）、zhida 词条链接剔除。产物见 `zhihu-article/`（PR #5）。
