# AGENTS.md — dsh-superagent playground

## 项目现状（2026-11-21，工单 relogin-check-ca1c125bc8d4）

- `127.0.0.1:3082` = dsh web（superagent 宿主，launchd KeepAlive 托管）。纯文本 401
  `dsh web authentication required` = 浏览器无有效 `dsh-auth-*` cookie；登录 token 每次宿主重启
  轮换，旧 `?token=` 链接必 401；同端口重启旧 cookie 仍有效（cookie 30 天）。
- 修复入口：`~/.local/bin/dsh-web-open`（打开当前链接完成登录；`--print` 只打印链接）。
- 机制与复核证据：`~/.dsh/LESSONS.md` **E122**；本工单详证
  [work/项目复盘-relogin-check-3082-2026-11-21.md](work/项目复盘-relogin-check-3082-2026-11-21.md)。
