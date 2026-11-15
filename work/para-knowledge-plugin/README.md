# dsh-para-knowledge

PARA 知识库插件（独立 DSH bundle）。为 DeepSeek Harness 的执行器会话提供两个工具与一道写入门禁，
治理对象是 `~/我的知识库`（PARA 六目录知识工作区）：

- **para_route** — 路由建议（只读）：判断资料应进入哪个目录，并检索库内是否已有相关内容。
- **para_save** — 受控写入：路径围栏（仅限库内）、默认拒绝覆盖（supersede=true 时旧文件迁入
  04-Archive/ 保留）、03-Resources 强制来源、frontmatter 自动补全、原子写入、追加处理日志
  （日志失败即回滚写入）。
- **会话级 guard** — 拦截原生 write/edit 与 shell 直写库路径（root/config 治理文件与 git 版本命令放行），
  入库必须走 para_save。
- **system prompt 指引** — 给 worker 会话固定注入「收到资料 → para_route → para_save」的处理指引。

## 为什么是独立 bundle

2026-11-16 之前，本插件是 `dsh-superagent` 包内入口（`dsh-superagent/para-knowledge`）。
DSH 的插件列表（Plugins → Installed）按**安装的包**展示（依赖 + `dsh.bundle.patch` 声明），
不展示包内入口，所以用户在插件列表里看不到知识库插件。拆成独立包后列表可见；
功能与行为保持不变（纯 JS 重写，全部领域规则与文案 1:1 移植，23 个回归用例通过）。

## 激活方式

会话级激活仍由 `dsh-superagent` 的 worker preset 引用本包名完成（只有执行器会话加载本插件，
主 Session 不加载）。本包自身的 patch 行保持 disabled，只是让 bundle 层存在、插件列表可见。

## 配置

| 字段 | 默认 | 说明 |
|---|---|---|
| `root` | `~/我的知识库` | 知识工作区根目录，在 patch 行的 `config` 里覆盖。 |

## 测试

```sh
npm test   # node --test "tests/*.test.mjs"，23 用例
```
