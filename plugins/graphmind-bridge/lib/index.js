/**
 * graphmind-bridge — expose a running GraphMind (LightRAG) knowledge-graph
 * service as read-only DSH model tools. The upstream stays the single source
 * of truth: every tool is a thin, capped HTTP call to the GraphMind API.
 *
 * Config (all optional):
 *   upstream:       GraphMind base URL, default http://127.0.0.1:8777
 *   defaultDataset: dataset id used when a call omits `dataset`
 */
const DEFAULT_UPSTREAM = 'http://127.0.0.1:8777'
const SEARCH_TIMEOUT_MS = 180_000
const FAST_TIMEOUT_MS = 30_000
const MAX_NEIGHBOR_NODES = 60
const MAX_NEIGHBOR_EDGES = 100

export const name = 'graphmind-bridge'
export const inject = ['tools']

/** One JSON API call against the GraphMind service. */
async function api(upstream, path, { method = 'GET', body, timeoutMs = FAST_TIMEOUT_MS, signal } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(new Error(`GraphMind 请求超时（${Math.round(timeoutMs / 1000)}s）`)), timeoutMs)
  const onAbort = () => controller.abort(new Error('已取消'))
  signal?.addEventListener('abort', onAbort, { once: true })
  try {
    const res = await fetch(upstream.replace(/\/$/, '') + path, {
      method,
      headers: body === undefined ? {} : { 'content-type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    })
    const text = await res.text()
    let value = null
    try {
      value = JSON.parse(text)
    } catch {
      value = { raw: text.slice(0, 2000) }
    }
    if (!res.ok) {
      const detail = value?.detail ?? value?.error ?? `HTTP ${res.status}`
      throw new Error(`GraphMind ${res.status}：${typeof detail === 'string' ? detail : JSON.stringify(detail)}`)
    }
    return value
  } catch (error) {
    if (error?.cause?.code === 'ECONNREFUSED' || /fetch failed/i.test(String(error))) {
      throw new Error(`GraphMind 后端不可达（${upstream}）。请先在 graphmind-replica 目录用 ./start.sh 启动服务。`)
    }
    throw error
  } finally {
    clearTimeout(timer)
    signal?.removeEventListener('abort', onAbort)
  }
}

/** Resolve the dataset id from args, config default, or the first dataset. */
async function resolveDataset(upstream, config, explicit, signal) {
  const wanted = String(explicit ?? '').trim() || String(config?.defaultDataset ?? '').trim()
  if (wanted !== '') return wanted
  const list = await api(upstream, '/api/datasets', { signal })
  const first = (list?.datasets ?? []).find(item => item.has_index && item.index_complete) ?? list?.datasets?.[0]
  if (first === undefined) throw new Error('GraphMind 里还没有可用数据集。')
  return first.id
}

function truncateNode(node) {
  const description = String(node?.description ?? '').replace(/\s+/gu, ' ').trim()
  return {
    id: String(node?.id ?? ''),
    label: String(node?.label ?? node?.id ?? ''),
    entity_type: String(node?.type ?? node?.entity_type ?? ''),
    summary: description.length > 160 ? description.slice(0, 157) + '…' : description,
  }
}

function truncateEdge(edge) {
  const label = String(edge?.label ?? '').replace(/\s+/gu, ' ').trim()
  return {
    from: String(edge?.from ?? edge?.source ?? ''),
    to: String(edge?.to ?? edge?.target ?? ''),
    relation: label.length > 120 ? label.slice(0, 117) + '…' : label,
    weight: Number(edge?.weight ?? 0),
  }
}

/** Register the read-only tools. */
function registerTools(ctx, config) {
  const upstream = String(config?.upstream ?? '').trim() || DEFAULT_UPSTREAM
  const register = definition => {
    const dispose = ctx.tools.register(definition)
    ctx.effect(() => dispose, `graphmind-bridge: tool ${definition.name}`)
  }

  register({
    name: 'kg_datasets',
    description: '列出 GraphMind 知识图谱服务里的全部数据集（知识空间）：id、名称、实体/关系数量。需要指定数据集的其它 kg_* 工具从这里拿 id。',
    parameters: { type: 'object', properties: {}, additionalProperties: false },
    output: {
      schema: {
        type: 'object',
        properties: {
          datasets: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                id: { type: 'string' },
                name: { type: 'string' },
                entities: { type: 'number' },
                relations: { type: 'number' },
                ready: { type: 'boolean' },
              },
              required: ['id', 'name', 'entities', 'relations', 'ready'],
              additionalProperties: false,
            },
          },
        },
        required: ['datasets'],
        additionalProperties: false,
      },
      render: (_args, value) => [{
        type: 'text',
        text: value.datasets.length === 0
          ? 'GraphMind 里没有数据集。'
          : value.datasets.map(item =>
              `${item.id} · ${item.name} · 实体 ${item.entities} · 关系 ${item.relations}${item.ready ? '' : ' · 索引未完成'}`,
            ).join('\n'),
      }],
    },
    async execute(_args, exec) {
      if (exec.signal.aborted) throw new Error('已取消')
      const list = await api(upstream, '/api/datasets', { signal: exec.signal })
      const datasets = (list?.datasets ?? []).map(item => ({
        id: String(item.id ?? ''),
        name: String(item.name ?? ''),
        entities: Number(item.entity_count ?? 0),
        relations: Number(item.relationship_count ?? 0),
        ready: Boolean(item.has_index && item.index_complete),
      }))
      return { datasets }
    },
  })

  register({
    name: 'kg_search',
    description: '在 GraphMind 知识图谱里做图谱增强问答（RAG）：返回带参考来源的回答。适合需要私域知识、可追溯依据的问题。mode 可选 local（实体聚焦，默认）/ global（关系宏观）/ hybrid（两者合并）/ mix（图谱+向量，最全面）/ naive（纯向量）。',
    parameters: {
      type: 'object',
      properties: {
        query: { type: 'string', description: '要提问的问题' },
        dataset: { type: 'string', description: '数据集 id；缺省用配置的默认数据集或第一个可用数据集' },
        mode: { type: 'string', description: '检索模式，默认 local' },
      },
      required: ['query'],
      additionalProperties: false,
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          dataset: { type: 'string' },
          mode: { type: 'string' },
          answer: { type: 'string' },
          context: { type: 'string', description: '检索到的图谱原文片段（截断到 2000 字符）' },
        },
        required: ['dataset', 'mode', 'answer', 'context'],
        additionalProperties: false,
      },
      render: (_args, value) => [{
        type: 'text',
        text: `[${value.dataset} · ${value.mode}]\n${value.answer}${value.context === '' ? '' : '\n\n检索片段：\n' + value.context}`,
      }],
    },
    async execute(args, exec) {
      if (exec.signal.aborted) throw new Error('已取消')
      const query = String(args?.query ?? '').trim()
      if (query === '') throw new Error('query 不能为空')
      const dataset = await resolveDataset(upstream, config, args?.dataset, exec.signal)
      const mode = ['naive', 'local', 'global', 'hybrid', 'mix'].includes(args?.mode) ? args.mode : 'local'
      const value = await api(upstream, `/api/datasets/${encodeURIComponent(dataset)}/search`, {
        method: 'POST',
        body: { query, mode },
        timeoutMs: SEARCH_TIMEOUT_MS,
        signal: exec.signal,
      })
      const context = String(value?.context ?? '').trim()
      return {
        dataset,
        mode,
        answer: String(value?.answer ?? '').trim(),
        context: context.length > 2000 ? context.slice(0, 1997) + '…' : context,
      }
    },
  })

  register({
    name: 'kg_find_entities',
    description: '按关键词模糊搜索 GraphMind 图谱里的实体名（用于给 kg_neighborhood / kg_entity 找准确名字）。只返回名字和类型，轻量。',
    parameters: {
      type: 'object',
      properties: {
        q: { type: 'string', description: '搜索关键词' },
        dataset: { type: 'string', description: '数据集 id；缺省用默认数据集' },
        limit: { type: 'number', description: '最多返回几个，默认 15，上限 50' },
      },
      required: ['q'],
      additionalProperties: false,
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          dataset: { type: 'string' },
          query: { type: 'string' },
          entities: {
            type: 'array',
            items: {
              type: 'object',
              properties: { name: { type: 'string' } },
              required: ['name'],
              additionalProperties: false,
            },
          },
        },
        required: ['dataset', 'query', 'entities'],
        additionalProperties: false,
      },
      render: (_args, value) => [{
        type: 'text',
        text: value.entities.length === 0
          ? `在 ${value.dataset} 没找到匹配「${value.query}」的实体。`
          : `在 ${value.dataset} 找到 ${value.entities.length} 个：` + value.entities.map(item => item.name).join('、'),
      }],
    },
    async execute(args, exec) {
      if (exec.signal.aborted) throw new Error('已取消')
      const q = String(args?.q ?? '').trim()
      if (q === '') throw new Error('q 不能为空')
      const dataset = await resolveDataset(upstream, config, args?.dataset, exec.signal)
      const limit = Math.max(1, Math.min(50, Number(args?.limit ?? 15) || 15))
      const value = await api(upstream, `/api/datasets/${encodeURIComponent(dataset)}/graph/search-entities?q=${encodeURIComponent(q)}&limit=${limit}`, { signal: exec.signal })
      const entities = (Array.isArray(value) ? value : value?.entities ?? value?.results ?? [])
        .map(item => ({ name: String(typeof item === 'string' ? item : item?.name ?? item?.id ?? '') }))
        .filter(item => item.name !== '')
      return { dataset, query: q, entities }
    },
  })

  register({
    name: 'kg_neighborhood',
    description: '读取 GraphMind 图谱里一个实体的 N 层邻域子图：相关实体、关系边、实体类型和摘要。适合看「某实体和哪些东西有关系」。',
    parameters: {
      type: 'object',
      properties: {
        entity: { type: 'string', description: '实体精确名字（先用 kg_find_entities 找）' },
        dataset: { type: 'string', description: '数据集 id；缺省用默认数据集' },
        depth: { type: 'number', description: '邻域层数 1–5，默认 2' },
      },
      required: ['entity'],
      additionalProperties: false,
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          dataset: { type: 'string' },
          entity: { type: 'string' },
          depth: { type: 'number' },
          truncated: { type: 'boolean' },
          nodes: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                id: { type: 'string' },
                label: { type: 'string' },
                entity_type: { type: 'string' },
                degree: { type: 'number' },
                summary: { type: 'string' },
              },
              required: ['id', 'label', 'entity_type', 'degree', 'summary'],
              additionalProperties: false,
            },
          },
          edges: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                from: { type: 'string' },
                to: { type: 'string' },
                relation: { type: 'string' },
                weight: { type: 'number' },
              },
              required: ['from', 'to', 'relation', 'weight'],
              additionalProperties: false,
            },
          },
        },
        required: ['dataset', 'entity', 'depth', 'truncated', 'nodes', 'edges'],
        additionalProperties: false,
      },
      render: (_args, value) => [{
        type: 'text',
        text: [
          `${value.dataset} · ${value.entity} · ${value.depth} 层 · ${value.nodes.length} 实体 / ${value.edges.length} 关系${value.truncated ? '（已截断）' : ''}`,
          ...value.nodes.map(node => `- ${node.label || node.id}（${node.entity_type || '未知类型'}，连接 ${node.degree}）${node.summary === '' ? '' : '：' + node.summary}`),
          '',
          ...value.edges.map(edge => `${edge.from} → ${edge.to}${edge.relation === '' ? '' : '：' + edge.relation}`),
        ].join('\n'),
      }],
    },
    async execute(args, exec) {
      if (exec.signal.aborted) throw new Error('已取消')
      const entity = String(args?.entity ?? '').trim()
      if (entity === '') throw new Error('entity 不能为空')
      const dataset = await resolveDataset(upstream, config, args?.dataset, exec.signal)
      const depth = Math.max(1, Math.min(5, Number(args?.depth ?? 2) || 2))
      const value = await api(upstream, `/api/datasets/${encodeURIComponent(dataset)}/graph/neighborhood?entity=${encodeURIComponent(entity)}&depth=${depth}`, { signal: exec.signal })
      const rawNodes = Array.isArray(value?.nodes) ? value.nodes : []
      const rawEdges = Array.isArray(value?.edges) ? value.edges : []
      const rawEdgesNormalized = rawEdges.map(truncateEdge)
      const degreeById = new Map()
      for (const edge of rawEdgesNormalized) {
        degreeById.set(edge.from, (degreeById.get(edge.from) ?? 0) + 1)
        degreeById.set(edge.to, (degreeById.get(edge.to) ?? 0) + 1)
      }
      const nodes = rawNodes.slice(0, MAX_NEIGHBOR_NODES).map(node => {
        const item = truncateNode(node)
        return { ...item, degree: degreeById.get(item.id) ?? 0 }
      })
      const keptIds = new Set(nodes.map(node => node.id))
      const edges = rawEdgesNormalized
        .filter(edge => keptIds.has(edge.from) && keptIds.has(edge.to))
        .slice(0, MAX_NEIGHBOR_EDGES)
      return { dataset, entity, depth, truncated: rawNodes.length > nodes.length || rawEdges.length > edges.length, nodes, edges }
    },
  })

  register({
    name: 'kg_entity',
    description: '读取 GraphMind 图谱里一个实体的完整详情：类型、完整描述、邻居实体名单。需要完整描述（不被截断）时用这个。',
    parameters: {
      type: 'object',
      properties: {
        name: { type: 'string', description: '实体精确名字（先用 kg_find_entities 找）' },
        dataset: { type: 'string', description: '数据集 id；缺省用默认数据集' },
      },
      required: ['name'],
      additionalProperties: false,
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          dataset: { type: 'string' },
          name: { type: 'string' },
          found: { type: 'boolean' },
          entity_type: { type: 'string' },
          description: { type: 'string' },
          neighbors: { type: 'array', items: { type: 'string' } },
        },
        required: ['dataset', 'name', 'found', 'entity_type', 'description', 'neighbors'],
        additionalProperties: false,
      },
      render: (_args, value) => [{
        type: 'text',
        text: value.found
          ? [
              `${value.dataset} · ${value.name}（${value.entity_type || '未知类型'}）`,
              value.description,
              value.neighbors.length > 0 ? '\n邻居：' + value.neighbors.join('、') : '',
            ].join('\n')
          : `在 ${value.dataset} 没有实体「${value.name}」。`,
      }],
    },
    async execute(args, exec) {
      if (exec.signal.aborted) throw new Error('已取消')
      const name = String(args?.name ?? '').trim()
      if (name === '') throw new Error('name 不能为空')
      const dataset = await resolveDataset(upstream, config, args?.dataset, exec.signal)
      try {
        const value = await api(upstream, `/api/datasets/${encodeURIComponent(dataset)}/entity?name=${encodeURIComponent(name)}`, { signal: exec.signal })
        const properties = value?.properties ?? {}
        const neighbors = (Array.isArray(value?.neighbors) ? value.neighbors : [])
          .map(item => String(typeof item === 'string' ? item : item?.name ?? item?.id ?? ''))
          .filter(item => item !== '')
        return {
          dataset,
          name,
          found: true,
          entity_type: String(properties.entity_type ?? ''),
          description: String(properties.description ?? '').trim(),
          neighbors,
        }
      } catch (error) {
        if (/404/.test(String(error))) return { dataset, name, found: false, entity_type: '', description: '', neighbors: [] }
        throw error
      }
    },
  })

  register({
    name: 'kg_stats',
    description: '读取 GraphMind 一个数据集的知识图谱统计概览：实体/关系数量、实体类型分布等。',
    parameters: {
      type: 'object',
      properties: {
        dataset: { type: 'string', description: '数据集 id；缺省用默认数据集' },
      },
      additionalProperties: false,
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          dataset: { type: 'string' },
          stats: { type: 'string' },
        },
        required: ['dataset', 'stats'],
        additionalProperties: false,
      },
      render: (_args, value) => [{ type: 'text', text: `${value.dataset}\n${value.stats}` }],
    },
    async execute(args, exec) {
      if (exec.signal.aborted) throw new Error('已取消')
      const dataset = await resolveDataset(upstream, config, args?.dataset, exec.signal)
      const value = await api(upstream, `/api/datasets/${encodeURIComponent(dataset)}/graph/stats`, { signal: exec.signal })
      const lines = Object.entries(value ?? {})
        .filter(([, item]) => item !== null && item !== undefined)
        .map(([key, item]) => `${key}: ${typeof item === 'object' ? JSON.stringify(item) : String(item)}`)
      return { dataset, stats: lines.join('\n') }
    },
  })
}

/** Cordis plugin entry. */
export function apply(ctx, config = {}) {
  registerTools(ctx, config)
}
