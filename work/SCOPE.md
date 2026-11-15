# SCOPE

## 本工单做什么

用户在知识库工单线程里**第二次**问：「我们这个知识库是做有插件的，但是在插件列表里看不到，原因是什么」。
上次（2026-11-15 08:48–09:00）已用 bundle/入口粒度解释过一次，用户仍来问，说明解释不够直观。

1. **核实**：用官方文档（publish.md / plugin-market.md）+ 本机真实代码（profile 清单、bundle patch、
   插件清单 API 源码）查实「插件列表按什么粒度展示、知识库插件为什么不在其中」，给出可验证的证据。
2. **抉择**：拆成独立包（列表可见）还是维持包内入口（只解释）。按用户「自己拍板、只看结果」的常设授权自行决策。
3. **落地**：把知识库插件拆成独立 bundle `dsh-para-knowledge`（~/.dsh/plugins/para-knowledge/），
   接线 profile、移除 dsh-superagent 包内实现、构建+全量测试+dump-config 验证、重启宿主、重启后核验插件列表。

## 不做什么

- 不改 para_route / para_save 的行为、参数、输出文案与门禁语义（纯搬家）。
- 不动知识库本体（~/我的知识库）的任何内容。
- 不动 dsh-superagent 仓库里其他工单的在途未提交改动（src/app/runtime.ts、mention-hint 等）。
- 不新增 OS 级沙箱（直写拦截维持现状的启发式 guard，属既有已知边界）。
