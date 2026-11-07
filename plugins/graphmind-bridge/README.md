# graphmind-bridge

把一台正在运行的 [GraphMind](../../../graphmind-replica)（LightRAG 知识图谱服务）接入
DeepSeek Harness：模型的工具列表里多出一组只读 `kg_*` 工具，直接查询你的知识图谱。

对应文章《给DeepSeek-harness装上知识空间+本体论》的"图谱插件"层——知识空间、本体抽取、
图谱可视化都在 GraphMind 侧完成，本插件只做桥接。

## 工具

| 工具 | 作用 |
| --- | --- |
| `kg_datasets` | 列出全部数据集（知识空间）：id、实体/关系数量 |
| `kg_search` | 图谱增强问答（5 种检索模式），返回带参考的回答 |
| `kg_find_entities` | 按关键词模糊找实体名 |
| `kg_neighborhood` | 读一个实体的 N 层邻域子图（实体、关系、类型、摘要） |
| `kg_entity` | 读一个实体的完整详情 |
| `kg_stats` | 数据集的图谱统计（数量、类型分布） |

全部只读；写入/索引构建仍在 GraphMind 界面或 API 完成。

## 前提

GraphMind 后端在运行（默认 `http://127.0.0.1:8777`，在 graphmind-replica 目录 `./start.sh`）。

## 配置

```yaml
- id: graphmind-bridge
  name: graphmind-bridge
  config:
    upstream: http://127.0.0.1:8777   # GraphMind 地址
    defaultDataset: harness_d9b1af    # 缺省数据集 id（不配则用第一个就绪的数据集）
```

## 安装

```powershell
dsh plugin --profile <profile> add <本目录路径>
```

装完后**完全退出并重启 DeepSeek Harness**（不是只刷新页面）。

## 自测

```bash
node --check lib/index.js
# 对着正在运行的 GraphMind 直接跑六个工具（不经宿主）：
node --input-type=module -e "import {apply} from './lib/index.js'; const r=[]; apply({tools:{register:d=>(r.push(d),()=>{})},effect:()=>{}},{}); const ex={signal:new AbortController().signal}; for (const [n,a] of [['kg_datasets',{}],['kg_stats',{}]]) { const t=r.find(x=>x.name===n); console.log(n, JSON.stringify(await t.execute(a,ex)).slice(0,200)); }"
```

2026-11-06 实测记录见工单报告：六工具在 DSH 0.2.1-rc.5 headless 真宿主中由模型实际调用成功。
