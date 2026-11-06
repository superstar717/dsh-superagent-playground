# 项目现状（fetch-zhihu-article 工单）

> 本仓库为 dsh-superagent 值守的 playground；本文件仅存在于本工单分支，记录该工单结论，避免下个会话重新摸底。详细复盘见 `work/项目复盘.md`。

## 工单结论（2026-11-06，已完成交付）

- **任务**：抓取整理知乎专栏 https://zhuanlan.zhihu.com/p/2092727841804784619 正文
- **交付**：`zhihu-article/article.md`（整理稿）+ `zhihu-article/images/`（10 张原尺寸配图），提交 `0cb1aa0`，PR #5（分支 `agent/fetch-zhihu-article-867415173221`）
- **验证**：`refs/pull/5/head = 0cb1aa0`（git ls-remote 服务端确认）；图片均为有效 JPEG

## 硬约束 / 关键事实

1. **知乎抓取**：curl 直连 zhuanlan 返回 403（反爬拦截非浏览器指纹），非登录态问题；真实 Chrome 渲染即可公开读取。抓取路径：bb-browser 托管 Chrome（CDP 127.0.0.1:19825）+ Python Playwright `connect_over_cdp`。
2. **bb-browser 坑**：托管 Chrome 无标签页时 daemon/CLI 报 "No page target found"，先 `curl -X PUT http://127.0.0.1:19825/json/new?about:blank`；其 profile（`~/.bb-browser/browser/user-data`）独立于用户日常浏览器，**无知乎登录态**（详见 LESSONS E86）。
3. **本机 GitHub 网络**：api.github.com TLS 间歇被重置 → gh REST 不可用且会误报「账号被暂停/token 失效」；git 智能传输（github.com）始终正常。验证 GitHub 状态一律用 `git ls-remote` 交叉验证（详见 LESSONS E87）。相关教训：E85/E86/E87。
