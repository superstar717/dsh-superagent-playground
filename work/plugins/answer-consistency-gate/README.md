# answer-consistency-gate — 同题作答一致性门禁

把 `~/.dsh/AGENTS.md` 第十一节（LESSONS E104）的三条规则做成 DSH 插件：
回答「X 是不是 Y / 什么关系 / 为什么两次回答不同」类比对性问题前，强制（低成本地）先检索存量结论。

## 机制

**工具描述即常驻规则 + 一次调用完成检索**（最弱够用）：
- `answer_preflight` 工具的 description 每轮都进模型上下文——规则钉在工具入口；
- 调用即对默认存量源跑 `grep -nEi`（OR 语义，args 直传不经 shell）：
  - `~/.dsh/LESSONS.md`
  - `~/src/*/work/DEPLOY-NOTES.md`（各工单部署/验证记录）
  - `~/src/*/work/项目复盘.md`（各工单复盘）
  - 可选 `dirs` 参数递归加检
- 命中 → 返回命中清单并提示"先读再答、对齐既有框架"；未命中 → 明确提示"未发现 ≠ 没有"，断言"没有X"须附检索式与范围。

**为什么不用 guard**：纯文本回答没有可拦截的工具执行面，guard 只能挂在工具调用上（E44：hooks 桥接不可靠，进程内 ctx.tools.* 是唯一可靠面）。

## 契约核实（E43/E44：不凭样例与记忆）

- `ToolSchema { name, description, parameters }` — `packages/llm/llm/lib/types/types.d.ts:472`
- 注册对象扩展 `{ output: { schema, render }, async execute(args, exec) }`、
  `apply(ctx, config) → disposer` — 对照生产样例 `~/.dsh/plugins/stat-research-gate` v2.10.1

## 安装（本机已装）

```bash
ln -s ~/.dsh/plugins/answer-consistency-gate ~/.dsh/profiles/superagent/node_modules/@local/answer-consistency-gate
# profile package.json: dependencies["@local/answer-consistency-gate"]="link:$HOME/.dsh/plugins/answer-consistency-gate"
#                      dsh.profile.bundles 追加 "@local/answer-consistency-gate"
# 重启 dsh 会话生效
```

## 验证

见 work/DEPLOY-NOTES.md（工单归档）；e2e 标准按 LESSONS E44：部署后必须用真实目标验证"该调时真调"。
