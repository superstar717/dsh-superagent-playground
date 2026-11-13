# SCOPE

## 本工单做什么

实现防失联清单第③项：**工单结束（ended）后，其线程上收到人的新消息时，平台自动开单继续处理，免人工重发**。

落点在本机 dsh-superagent 宿主（`~/dsh-superagent-prototype`，以 link 方式被 superagent profile 使用）：

1. 人的消息续单时，新 Assignment 使用「人的消息」保留槽位（并发上限 +1），不再排在普通新任务后面等空位（本次事故 12:10→12:24 的 13.4 分钟延迟根因）。
2. 工单结束时，把它释放给 Eval 的未读消息从 worker Session 收件箱移除，避免工具已收回的僵尸 turn（工具全被 `Ticket ended; new work needs a new authorized ticket` 拦住）。
3. 补两条回归测试、文档同步、验证记录与复盘存档。

## 不做什么 / 边界

- **不新开一张 ticket id**：平台原本就以「同一 Mandate 续单」实现自动开单（`Tickets.wake`），人的新消息本身就是继续处理的授权依据。新开 ticket id 会重跑 prepare 命令、换 worktree/分支，丢失进行中的工作区与 GitHub PR 绑定（PR 绑定按分支末段 = ticket short name）。详见 `work/验证记录-工单结束后自动续单.md` §6。
- 不处理 ①整机睡眠、②keepawake 核对（清单其他项）。
- 不提交、不改动仓库里既有的在途改动（`src/app/mention-hint.ts`、`src/app/runtime.ts`、`docs/002-authorization.md`、`tests/mention-hint.spec.ts` 等）。
