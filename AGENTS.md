# 项目现状（fetch-zhihu-article 工单）

> 本仓库为 dsh-superagent 值守的 playground；本文件仅存在于本工单分支，记录该工单结论，避免下个会话重新摸底。详细复盘见 `work/项目复盘.md`。

## 工单结论（2026-11-06 交付；2026-11-07 二次更新）

- **任务**：抓取整理知乎专栏 https://zhuanlan.zhihu.com/p/2092727841804784619 正文
- **交付**：`zhihu-article/article.md`（整理稿）+ `zhihu-article/images/`（10 张原尺寸配图）+ `scripts/`（可复用抓取流水线）+ `work/项目复盘.md`；最新提交 `445589d`
- **PR**：原 PR #5 因 GitHub 账号删号重建事件被连带删除（API/网页均 404）；已用镜像分支重建为 **PR #7**（分支 `agent/fetch-zhihu-article-867415173221-pr`，提交与原分支一致），原分支名重建被 GitHub 内部守卫拦截（"already exists" vs 对象 404 的恢复残留矛盾）

## 硬约束 / 关键事实

1. **知乎抓取**：curl 直连 zhuanlan 返回 403（反爬拦截非浏览器指纹），非登录态问题；真实 Chrome 渲染即可公开读取。抓取路径：bb-browser 托管 Chrome（CDP 127.0.0.1:19825）+ Python Playwright `connect_over_cdp`。
2. **bb-browser 坑**：托管 Chrome 无标签页时 daemon/CLI 报 "No page target found"，先 `curl -X PUT http://127.0.0.1:19825/json/new?about:blank`；其 profile（`~/.bb-browser/browser/user-data`）独立于用户日常浏览器，**无知乎登录态**（详见 LESSONS E86）。
3. **GitHub 账号事件（已闭环）**：旧账号 648267586 被风控停用后**删号重建**为 xingzhe-agent（2026-11-07 12:04 注册）；停用窗口的 PR #2-#5 全部连带删除，PR #7 为重建版。教训：新号开 2FA+暖机、跨用户仓库用 classic+repo scope、REST 调用全局限速（详见 LESSONS E87/E88/E89）。
4. **本机网络**：api.github.com TLS 间歇被重置（EOF/超时），git 智能传输通道正常；GitHub 状态验证一律先 git 读通道交叉验证（LESSONS E87）。

## GraphMind 支持工作（2026-11-06/07，随本工单附带完成）

- **graphmind-replica**（本地仓库 /Users/huweixing/graphmind-replica）：三段模型全接免费/低价渠道（llm=glm-5.2 coding 端点（走智谱 Coding Plan）、vision=glm-4.1v-thinking-flash、embedding=百炼 v3），key 全落 `backend/config.local.yaml`（0600，gitignore）；QA 已加 `extra_params` 透传（thinking 关闭，naive 15.4s）；前端节点展示优化（9b784f2）与社区检测白屏修复（5ce0658）已提交 main
- **新账号纪律**：串行使用+早停机（E87/E88/E89）；「机器强制」宿主层限速已获用户批准并移交治理立项
