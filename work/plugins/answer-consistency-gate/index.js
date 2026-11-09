/**
 * answer-consistency-gate — 同题作答一致性门禁插件（AGENTS.md 第十一节 / LESSONS E104）。
 *
 * 机制（最弱够用，practices.md 原则一）：
 * - 不用 guard：纯文本回答没有可拦截的工具执行面，强拦必然误伤（E44：hooks 桥接不可靠）。
 * - 用「工具描述即常驻规则」：answer_preflight 的 description 每轮都进模型上下文，
 *   把第十一节三条规则钉在工具入口；调用本身即完成"存量检索"这一硬动作，
 *   把合规成本降到一次调用。
 *
 * 契约来源（E43/E44 教训：不凭样例与记忆，双源核实）：
 * - ToolSchema { name, description, parameters } — packages/llm/llm/lib/types/types.d.ts:472
 * - 注册对象扩展 { output: { schema, render }, async execute(args, exec) }、
 *   apply(ctx, config) → disposer — 对照生产样例 ~/.dsh/plugins/stat-research-gate（v2.10.1）
 */

import { spawnSync } from 'node:child_process'
import { homedir } from 'node:os'
import { existsSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

export const name = 'answer-consistency-gate'
export const inject = ['tools', 'workingDirectory']

const MAX_HITS = 40

const HOME = homedir()

function expandHome(p) {
  const s = String(p || '')
  if (s === '~') return HOME
  if (s.startsWith('~/')) return join(HOME, s.slice(2))
  return s
}

/** 默认存量源：全局错误录 + 各工单 work/ 的复盘与部署说明。 */
function listDefaultTargets() {
  const files = []
  const missing = []
  const lessons = join(HOME, '.dsh', 'LESSONS.md')
  if (existsSync(lessons)) files.push(lessons)
  else missing.push(lessons)
  const srcRoot = join(HOME, 'src')
  try {
    for (const name of readdirSync(srcRoot)) {
      for (const f of ['DEPLOY-NOTES.md', '项目复盘.md']) {
        const p = join(srcRoot, name, 'work', f)
        if (existsSync(p)) files.push(p)
      }
    }
  } catch (e) {
    missing.push(`${srcRoot} (${e.code || e.message})`)
  }
  return { files, missing }
}

/** grep -n -e kw1 -e kw2（OR 语义），args 数组直传不经 shell（防注入）。 */
function runGrep(keywords, targets, maxHits) {
  const hits = []
  const errors = []
  let filesSearched = 0
  const chunk = 24 // xargs 式分块，避免 target过长单命令失败
  for (let i = 0; i < targets.length; i += chunk) {
    const part = targets.slice(i, i + chunk)
    const existing = part.filter(p => existsSync(p))
    filesSearched += existing.length
    if (!existing.length) continue
    const args = ['-n', '-E', '-i', '--max-count', '4']
    for (const k of keywords) args.push('-e', k)
    args.push(...existing)
    const r = spawnSync('grep', args, { encoding: 'utf8', timeout: 20000 })
    if (r.status === 2 && r.stderr) errors.push(r.stderr.trim().slice(0, 200))
    for (const line of (r.stdout || '').split('\n')) {
      if (!line || hits.length >= maxHits) continue
      const m = line.match(/^([^:]+):(\d+):(.*)$/)
      if (m) hits.push({ file: m[1].replace(/^\/Users\/[^/]+/, '~'), line: Number(m[2]), text: m[3].trim() })
    }
  }
  return { hits, filesSearched, errors }
}

export function apply(ctx, config) {
  const disposers = []
  disposers.push(ctx.tools.register(definePreflightTool(ctx, config)))
  return () => disposers.forEach(dispose => dispose())
}

function definePreflightTool(ctx, config) {
  return {
    name: 'answer_preflight',
    description: [
      '【同题作答一致性门禁 · AGENTS.md 第十一节】回答「X 是不是 Y / 两者什么关系 / 为什么两次回答不同」类比对性问题，',
      '或复核其他会话/工单的既有结论之前，必须先调用本工具检索存量结论（既往工单复盘/DEPLOY-NOTES/LESSONS）。',
      '命中 → 先读命中处、对齐既有框架再补充修正，不独立再造叙事。',
      '回答时先给对应映射、再给严格字面标准下的差距，并显式声明所用评价框架；',
      '未查实的「没有X」一律写「未发现X」并附检索式与范围。keywords 建议含精确名与变体（用户口语常有错别字）。',
    ].join(''),
    parameters: {
      type: 'object',
      properties: {
        keywords: {
          type: 'array',
          items: { type: 'string' },
          description: '检索关键词数组（OR 语义），含精确名与常见变体/错别字',
        },
        dirs: {
          type: 'array',
          items: { type: 'string' },
          description: '额外递归检索目录（可选；缺省检索默认存量源）',
        },
      },
      required: ['keywords'],
      additionalProperties: false,
    },
    output: {
      schema: {
        type: 'object',
        properties: {
          summary: { type: 'string' },
          hits: {
            type: 'array',
            items: {
              type: 'object',
              properties: {
                file: { type: 'string' },
                line: { type: 'integer' },
                text: { type: 'string' },
              },
              required: ['file', 'text'],
              additionalProperties: false,
            },
          },
          filesSearched: { type: 'integer' },
        },
        required: ['summary', 'hits'],
        additionalProperties: false,
      },
      render: (_args, value) => [{ type: 'text', text: value.summary }],
    },
    async execute(args, exec) {
      void ctx
      void exec
      const keywords = (Array.isArray(args.keywords) ? args.keywords : [])
        .map(k => String(k).trim()).filter(Boolean)
      if (!keywords.length) {
        return {
          summary: 'keywords 为空，未检索。比对性问题作答前需给出关键词（含精确名与变体）。',
          hits: [],
          filesSearched: 0,
        }
      }
      const extraDirs = [
        ...(Array.isArray(args.dirs) ? args.dirs : []),
        ...(config && Array.isArray(config.extraDirs) ? config.extraDirs : []),
      ].map(d => expandHome(String(d)))

      const { files } = listDefaultTargets()
      const targets = [...files, ...extraDirs.filter(Boolean)]
      const started = Date.now()
      const { hits, filesSearched, errors } = runGrep(keywords, targets, MAX_HITS)

      const lines = []
      if (hits.length) {
        lines.push(`【存量结论命中 ${hits.length} 处（${filesSearched} 个文件，${Date.now() - started}ms）——先读命中处再作答：对齐既有框架，补充或修正，不独立再造叙事。】`)
        for (const h of hits.slice(0, 12)) lines.push(`- ${h.file}:${h.line || '?'} ${h.text.slice(0, 160)}`)
        if (hits.length > 12) lines.push(`… 其余 ${hits.length - 12} 条见 hits`)
      } else {
        lines.push(`【未发现（检索 ${filesSearched} 个文件 / ${Date.now() - started}ms）≠ 没有。】`)
        lines.push('作答仍须：先给对应映射、再给字面标准下的差距，显式声明评价框架；「没有X」需附本次检索式与范围。')
      }
      for (const e of errors.slice(0, 3)) lines.push(`[检索异常] ${e}`)
      return { summary: lines.join('\n'), hits, filesSearched }
    },
  }
}
