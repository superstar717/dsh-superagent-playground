This is by an automated agent, not a human.

## 工单：实现工单结束后消息自动开新授权单的机制（`37c0c8a0a4dfb980433f2ff624afba69`）

### 结论

平台对「ended 工单收到人的新消息」本来就会自动续单（同一 Mandate 下新建 Assignment，**无需人工重发**）。本单修的是这次为什么看起来被挡住：**续单被当普通新任务排队 13.4 分钟**，以及**结束时被释放的消息仍在 worker 收件箱里起被拦的 turn**。修复在本机宿主 `~/dsh-superagent-prototype`（`dsh-superagent` 以 link 方式装进 superagent profile），源码 patch 与验证记录见 `work/`。

### 现场证据（2026-11-13，事故工单 `76ca2db8…`）

| 事实 | 证据 |
|---|---|
| 12:10:34 人的消息到达，同秒续单创建 assignment 4 | trigger `.at=04:10:34.015Z`；assignment `createdAt=04:10:34.356Z` |
| assignment 4 到 12:23:59 才 `startedAt`（13.4 分钟） | assignment `startedAt=04:23:59.077Z`；worker turn 11 `turn/start=04:23:59Z` |
| 同窗口 3 个普通 worker 的 turn 占满 `maxWorkers=3` | `f4020a3b` 12:03:41→12:29:04；`628a6d3d` 12:08:00→12:34:46；`3be269fb` 12:09:45→12:24:16（worker transcript turn 时间） |
| 11:18–11:21 七个 turn 的全部工具被 `Ticket ended; new work needs a new authorized ticket` 拦住 | worker transcript turn 4–10；消息为 end 前已投递、未读的旧 trigger（ticket inputs `readAt=null`） |

根因：① `Tickets.wake()` 以普通 `launch` 入队，普通 launch 上限 = `maxWorkers - 正在跑`；文档 003 已承诺「人的消息有保留槽位」，续单路径没走。② `end()` 已把未读消息释放给 Eval，但 `DshExecutor.stop()` 在 worker 自己结束 turn 时保留收件箱，释放消息仍起 turn，而工具已收回。

### 改动（9 个文件，patch 261 行）

1. `src/app/effects.ts` + `src/executor/dsh.ts`：新增 `resume` effect kind 与 `WorkerSlots.resumed()`；`Executor.start(ticket, assignment, resumed?)` 仅 `Tickets.wake()` 传 `true`，续单以 `'person'` 预留槽位启动（并发上限 +1），不再排队等普通槽位。
2. `src/executor/dsh.ts`：`stop()` 在 `ticket.ended` 时移除该 ticket 各 Input 在 worker Session 收件箱里的待处理消息（它们已由 end 释放给 Eval），避免工具已收回的空转 turn。
3. `src/client/locales.ts`：`health.resume` 文案。
4. `docs/003-execution.md`、`docs/007-architecture.md`：契约同步。
5. `tests/runtime-concurrency.spec.ts`：2 条回归测试；`tests/locales.spec.ts`：健康条目覆盖。

### 验证

- `pnpm typecheck` 通过；`pnpm build` 通过（`lib` 已重建，含 `resume` handler）。
- 新增 2 条测试：**未打补丁的 src 上 2 failed → 打补丁后 58/58 passed**（先红后绿）。
- 全量 `pnpm test`（干净环境，避免 worker 继承 `GIT_CONFIG_GLOBAL`/`PATH` 造成假失败）：
  - 打补丁：1199 passed / 3 failed；
  - 基线（回退本单 src、保留仓库在途改动）：1199 passed / 1 failed；
  - 差异的 2 条复跑均通过（飞书事件消费者、service-script，环境/时序 flaky）；`tests/environment.spec.ts` 基线与本轮同样失败。
- 无 UI 视觉变化（服务端行为 + 一条健康文案），不涉及 Before/After 截图。

### 部署与边界

- link 安装，`lib` 已重建；**需人工重启 `dsh --profile superagent` 后生效**——本工单内未重启，否则会中断本工单自身 worker 会话（参考 LESSONS E106）。
- **没有新建 ticket id**：平台既有语义是同一 Mandate 续单，人的消息本身就是授权依据；新建 ticket 会重跑 prepare、换 worktree/分支，并断开 GitHub PR 绑定（PR 绑定按分支末段 = ticket short name）。若确实要「每条消息新建 ticket id」，需另行设计 worktree 复用、订阅转移与防重复触发，详见 `work/验证记录-工单结束后自动续单.md` §6。
- 未提交仓库里既有的在途改动（`mention-hint` 相关文件），patch 已剔除其 hunk。

### 附件

- `work/dsh-superagent-auto-continue.patch`
- `work/验证记录-工单结束后自动续单.md`
- `work/项目复盘.md`
- `work/SCOPE.md`
