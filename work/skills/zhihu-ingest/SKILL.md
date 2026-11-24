---
name: zhihu-ingest
description: 知乎链接（回答/专栏文章）提取与知识库入库的可复用链路。当用户给知乎 URL 并要求「提取/入库/调研原文/存进知识库」时使用；含登录态检查、身份核验式精确提取、噪声剔除、para_route/para_save 入库衔接与已知坑。
---

# 知乎提取入库链路（zhihu-ingest）

知乎页面反爬拦 curl（403），公开页对真实浏览器可读；**登录态用独立 Chrome profile `~/.zhihu_reader_dp`**（含 `z_c0` 登录凭证）。本 skill 固化 2026-11-06 至 2026-11-19 四个工单验证过的工具链，收到知乎链接直接走下面步骤，不再重新探路。

## 工具链（入口都在 ~/bin，git 版本管理）

| 工具 | 用途 | 何时用 |
|---|---|---|
| `~/bin/zhihu_reader.py <URL>` | 通用提取：回答+专栏（`zhuanlan.zhihu.com/p/{pid}`），单页/`--batch` 批量；trafilatura 整页 + `.RichText` 降级双路 | 专栏文章、批量收集、想看整页 |
| `~/bin/zhihu_answer_extract.py <回答URL> [--out x.md] [--json]` | **回答专用精确提取**：读页面 `js-initialData` JSON 按 answer id 定位，只输出目标回答正文（免疫「更多回答」混入与页头登录角标），带身份核验 | 单条回答入库首选 |
| `~/bin/zhihu_discover.py` | URL 发现：搜索/问题下全部回答/作者主页 → 输出 URL 清单 | 批量收集前先发现 |

环境：系统 python3（3.10）+ DrissionPage + trafilatura，已装即用。

## 标准链路（单条回答）

```bash
# 1. 登录态检查（E86 预防：不臆断"电脑已登录"=工具 profile 已登录）
sqlite3 "file:$HOME/.zhihu_reader_dp/Default/Cookies?immutable=1" \
  "SELECT name FROM cookies WHERE name='z_c0';"   # 有行=已登录；空=先弹浏览器手动登录一次

# 2. 精确提取（自动核验 answer id 与作者）
python3 ~/bin/zhihu_answer_extract.py "<回答URL>" --out /tmp/zhihu-<aid>.md

# 3. 入库：para_route 判目录查重 → para_save（03-Resources 必带 source）
#    文件名惯例：作者-主题-知乎回答-<answer_id>.md
# 4. 二次提炼按库内「资料处理SOP」：逐条查重 → 02-Areas 候选卡（candidate:true）→ kb-commit --push
```

专栏文章把第 2 步换成 `zhihu_reader.py`；批量把第 2 步换成 `--batch urls.txt --out-dir <目录>`。

## 已知坑（全部实测过）

1. **整页提取噪声**：`zhihu_reader.py` 在问题页用 trafilatura 会把页头登录角标和「更多回答」里其他答主的内容混进正文——回答入库要么用 `zhihu_answer_extract.py`，要么事后按 `#### 更多回答` 截断并在原文卡标注噪声处理方式。
2. **答案身份核验**：入库前确认抓到的正文确实是目标回答（answer id ↔ 作者 ↔ 首段比对）；`zhihu_answer_extract.py` 自带此核验。
3. **残留 Chrome 占登录态目录**（LESSONS E183）：先 `pgrep -fl zhihu_reader_dp`，有残留按主进程 PID kill 再跑；DrissionPage 自建 ChromiumOptions 时勿用 `set_local_port(0)`。
4. **假成功兜底**（zhihu_reader 已内置）：不存在的回答会重定向首页或渲染「荒原」页，工具会抛异常而非输出空文。
5. **入库纪律**：原文照录、观点归属原作者（KB 治理：AI 提炼不得冒充用户认知）；提取内容含营销腔时如实标注，方法论部分单独看。

## 版本管理

`~/bin` 是 git 仓库（白名单 .gitignore 只管 zhihu 工具三件），改工具后 commit；工具行为变更要跑一次真实 URL e2e 再提交。
