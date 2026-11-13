# DSH Web 重启后免手贴 token（本机实施 + 存档）

2026-11-13。本目录是本机修复的存档（运行位置：`~/.dsh/bin/`），对应工单
「修复 DSH Web 重启后需手贴 token 链接的问题」。

## 问题

重启本机 DSH Web（`dsh --profile superagent`，GUI 在 `http://127.0.0.1:3082`）后，
浏览器沿用旧标签或重新打开时，可能只看到：

```
dsh web authentication required; reopen the URL printed by dsh web.
```

（HTTP 401 纯文本页。）此时必须到启动日志里找本次进程的 `?token=...` 链接手动粘贴。

## 根因（DSH 0.2.1-rc.5 源码 + 本机实测）

1. **启动 token 每次进程重启都变**：每个进程一个随机 launch token，只用于一次
   `GET /?token=` → 签名 cookie 的交换（`packages/client/connection/src/browser-auth.ts`；
   `.agents/notes/implemented/architecture/2026-08-24-browser-token-authentication.md`）。
   所以带 token 的启动链接不能当长期书签。
2. **浏览器会话本身可以跨重启**：会话 cookie 由持久化 HMAC 密钥签名，密钥在
   `$DSH_HOME/.credentials.yaml` 的 `client-connection/browser-session` 记录里；cookie
   默认 30 天，名称和签名载荷都绑定 `host:port`。**同一端口重启时，旧标签刷新/自动重连
   即可，不需要 token。**
3. **真正需要 token 的条件**：浏览器在该 `host:port` 上没有有效 cookie。例如新浏览器/
   隐身窗口、清过站点数据、cookie 过期、换了端口或主机名（如 3080↔3082、
   `127.0.0.1`↔`localhost`）、或签名密钥记录被删除。此时根路径直接 401，token 链接是
   唯一入口。本机 Chrome 里同时存在 3080、3082 两份 `dsh-auth-*` cookie；3082 那份是
   2026-11-13 02:01（本地时间）一次重启后才建立的，说明换 authority 就要重新登录一次。
4. **本机启动包装没有交接链接**：`super-restart.sh` 用 `--no-open` 启动，不自动开浏览器，
   也不把本次链接写到稳定位置，只留在日志里 → 第 3 条的情况只能手贴。
5. **CSP / trusted-host 不是原因**：Host/Origin 校验失败返回的是 403；本机 loopback
   实测返回 401（会话认证），响应没有 CSP 头，页面控制台也没有 CSP 拦截。
6. 旧标签的自动重连是正常的：测试实例上 kill 服务后页面显示 `Reconnecting…` 并重试，
   服务恢复后约 4 秒自动恢复（无需刷新、无需 token）。

## 修复内容（不改 DSH 本体、不改 token 安全模型）

- `super-restart.sh`：启动后等待就绪行，取出本次 `dsh web:` 链接：
  - 写入 `~/.dsh/state/web-url`（权限 600，含凭据）；
  - 默认用默认浏览器打开（`DSH_WEB_OPEN=0` 关闭自动打开）；
  - 启动进程提前退出时立即报错，不再干等 60 秒。
- 新增 `dsh-web-open`：随时取/打开当前登录链接。
  - `dsh-web-open` 直接打开；`--print` 只打印；`--copy` 复制到剪贴板；
    `--clean` 打开不带 token 的干净地址（依赖已存在的 30 天会话 cookie）。
  - 优先读 `~/.dsh/state/web-url`，失效时回退到启动日志，并用 `curl` 校验 token 链接
    仍返回 303（避免拿旧进程的链接骗自己）。
  - 安装：`~/.dsh/bin/dsh-web-open`，并软链到 `~/.local/bin/dsh-web-open`（PATH 内）。
- **书签用法**：浏览器已在该 `host:port` 登录过之后，直接收藏
  `http://127.0.0.1:3082/` 即可（cookie 30 天有效）；没有 cookie 时用自动打开或
  `dsh-web-open` 取一次 token 链接。

## 安全说明

- token 仍是一次性进程凭据，没有变成长效凭据；本方案不新增可长期使用的登录入口。
- `~/.dsh/state/web-url` 等价于启动日志里的凭据行，权限 600，不要提交/外传。
- 自动打开会调用本机默认浏览器（`open`），不涉及任何远端服务；`DSH_WEB_OPEN=0`
  可完全关闭自动打开。
- 未改 DSH 的 Host/Origin 校验、cookie 属性或 30 天有效期。

## 验证（2026-11-13，隔离测试实例 3998 + 临时 DSH_HOME，未动 3082 运行实例）

| 项 | 命令/操作 | 结果 |
|---|---|---|
| token 交换 | `curl -i 'http://127.0.0.1:3998/?token=...'` | 303 + `Set-Cookie: dsh-auth-...` |
| cookie 认证 | `curl -b jar http://127.0.0.1:3998/` | 200 |
| 旧 token + 有效 cookie | 重启后访问旧 `?token=` | 303 跳到干净 `./` |
| 重启后 cookie 仍在 | kill 进程 → 同端口重启 → 旧 cookie 访问 `/` | 200 |
| 旧标签自动恢复 | Playwright 打开页面 → kill → 重启 | 约 4 秒恢复，URL 仍干净 |
| 无 cookie 浏览器 | 新 context 打开 `/` | 401 纯文本（见 `evidence/before-401.png`） |
| 用链接登录 | 同一 context 打开 `dsh-web-open --print` 的链接 | 正常进入 GUI（见 `evidence/after-login.png`） |
| 新重启包装 | `PORT=3998 PROFILE=web DSH_HOME=/tmp/... super-restart.sh web` | 状态文件 600、打开命令收到新链接（见 `evidence/restart-after.txt`） |

说明：3082 的当前进程是改动前启动的，本工单没有重启它（会中断正在运行的会话）；
下次重启会走新逻辑。`evidence/restart-after.txt` 是隔离实例（3998）的实测输出，
路径与正式环境不同属预期。

## 本机安装 / 回滚

```sh
# 已安装
ls -l ~/.dsh/bin/super-restart.sh ~/.dsh/bin/dsh-web-open ~/.local/bin/dsh-web-open
dsh-web-open --print

# 回滚自动打开
DSH_WEB_OPEN=0 ~/.dsh/bin/super-restart.sh   # 单次
# 删除状态文件（下次重启会重建）
rm -f ~/.dsh/state/web-url
# 恢复旧版包装：用本目录存档前的版本（旧版只用日志打印链接）
```

## 文件

- `super-restart.sh`：本机运行版存档（`~/.dsh/bin/super-restart.sh`）。
- `dsh-web-open`：登录链接助手（`~/.dsh/bin/dsh-web-open` + `~/.local/bin` 软链）。
- `evidence/before-401.png`、`evidence/after-login.png`、`evidence/restart-after.txt`。

## 未采用 / 限制

- **token 书签**：token 是每进程随机的一次性凭据，要让它可长期收藏就必须变成长期凭据，
  会削弱现有的启动 token 安全模型，未采用；已有 cookie 时干净地址书签已够用。
- **持久会话**：DSH 已实现（cookie + 持久密钥），本工单验证其有效并把它作为旧标签恢复
  的主路径；无需改造。
- 自动打开每次重启都会在默认浏览器打开/复用一个标签；不需要时用 `DSH_WEB_OPEN=0`。
