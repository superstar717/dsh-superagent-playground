/**
 * Pure domain rules of the PARA knowledge workspace: routing suggestions, conflict-matching tokens,
 * path containment, superseded naming, frontmatter building, processing-log lines and the
 * direct-write denial used by the session guard. No I/O and no dependency on the Harness, so
 * tests cover it directly and the plugin adapter stays thin.
 * Ported 2026-11-16 from dsh-superagent src/core/knowledge.ts into this standalone bundle.
 * @module dsh-para-knowledge/knowledge
 */

import { basename, isAbsolute, join, resolve } from 'node:path'

/** The six top-level directories of the knowledge workspace, in routing order. */
export const KB_DIRECTORIES = ['00-Inbox', '01-Projects', '02-Areas', '03-Resources', '04-Archive', '05-Skills']

/** The knowledge-card types the workspace distinguishes; 00-Inbox content carries none. */
export const KB_TYPES = ['Knowledge', 'Experience', 'Source', 'Skill', 'Project']

/** The directory each KB type defaults to when the model does not name one. */
export const TYPE_DIRECTORY = {
  Knowledge: '02-Areas',
  Experience: '02-Areas',
  Source: '03-Resources',
  Skill: '05-Skills',
  Project: '01-Projects',
}

/** Routing rules as ordered keyword tables; the first matches win, unclassified input stays in 00-Inbox. */
const ROUTE_RULES = [
  { dir: '01-Projects', reason: '像一项有目标或进度的项目工作', keywords: ['项目', '进度', '里程碑', '截止', '交付', '任务', '计划', '排期', '验收', 'milestone', 'deadline', 'roadmap'] },
  // Skills 只收「可执行」信号（步骤/清单/模板/具名 SOP）；「方法/框架」是认知信号，归 02-Areas——
  // 2026-11-15 实测「提炼结构、框架、认知」曾被误路由到 Skills（kb-v2-para 工单）。
  { dir: '05-Skills', reason: '像一个可执行的流程、清单或模板', keywords: ['流程', '步骤', '工作流', 'SOP', 'sop', '模板', '清单', 'checklist', 'workflow', 'playbook'] },
  { dir: '03-Resources', reason: '像外部资料原文', keywords: ['文章', '论文', '教程', '文档', '原文', '链接', '转载', '书', '报告', 'https://', 'http://', 'paper', 'article'] },
  { dir: '02-Areas', reason: '像认知、框架或个人内化知识', keywords: ['经验', '心得', '教训', '总结', '思考', '认知', '方法论', '感悟', '复盘', '框架', '原理', '体系', '系统', 'insight', 'lesson'] },
]

/**
 * Suggest target directories for a piece of input, best first, at most three; an unclassified
 * input suggests 00-Inbox, because uncertain content stays there rather than being force-classified.
 * @param {string} text - the material title plus its first paragraphs.
 * @returns {{ dir: string, reason: string }[]} suggestions with the matched reason for each.
 */
export function suggestDirectories(text) {
  const lower = text.toLowerCase()
  const hits = ROUTE_RULES
    .map(rule => ({ rule, score: rule.keywords.filter(keyword => lower.includes(keyword.toLowerCase())).length }))
    .filter(({ score }) => score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 3)
  if (hits.length === 0) return [{ dir: '00-Inbox', reason: '无法判断资料性质，按规则留在 Inbox' }]
  return hits.map(({ rule }) => ({ dir: rule.dir, reason: rule.reason }))
}

/** CJK words of two or more characters and ASCII words of three or more, with common filler dropped. */
const STOP_TOKENS = new Set(['这个', '那个', '一个', '我们', '你们', '他们', '自己', '什么', '怎么', '如何', '可以', '就是', '但是', '因为', '所以', '如果', 'the', 'and', 'for', 'with', 'this', 'that', 'from', 'have', 'not'])

/**
 * Extract the salient tokens of a text for existing-content matching: CJK runs of 2–8 characters
 * and ASCII words of 3–20 letters, lowercased, minus filler, at most eight tokens, longer first.
 * @param {string} text - arbitrary input text.
 * @returns {string[]} the deduplicated tokens, best first.
 */
export function salientTokens(text) {
  const counts = new Map()
  const bump = token => {
    if (token.length < 2 || STOP_TOKENS.has(token)) return
    counts.set(token, (counts.get(token) ?? 0) + 1)
  }
  for (const run of text.matchAll(/[\u4e00-\u9fff]{2,8}/g)) bump(run[0])
  for (const run of text.matchAll(/[A-Za-z][A-Za-z0-9_-]{2,19}/g)) bump(run[0].toLowerCase())
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || b[0].length - a[0].length).slice(0, 8).map(([token]) => token)
}

/**
 * Whether a resolved target path stays inside a resolved root, so a crafted filename cannot escape
 * the knowledge workspace. Pure string containment; callers resolve real paths first.
 * @param {string} root - the absolute workspace root.
 * @param {string} target - the absolute candidate path.
 * @returns {boolean} true when `target` equals or lives under `root`.
 */
export function containedInRoot(root, target) {
  if (!isAbsolute(root) || !isAbsolute(target)) return false
  const normalizedRoot = resolve(root)
  const normalizedTarget = resolve(target)
  return normalizedTarget === normalizedRoot || normalizedTarget.startsWith(normalizedRoot + '/')
}

/**
 * The archived name for a file replaced by an explicit update: the same basename with a
 * `.superseded-<stamp>` suffix before the extension, so no version is ever silently overwritten.
 * @param {string} filename - the current file name, with or without extension.
 * @param {string} stamp - a filesystem-safe timestamp such as `20261115-1605`.
 * @returns {string} the archived file name.
 */
export function supersededName(filename, stamp) {
  const dot = filename.lastIndexOf('.')
  return dot > 0 ? `${filename.slice(0, dot)}.superseded-${stamp}${filename.slice(dot)}` : `${filename}.superseded-${stamp}`
}

/**
 * The frontmatter block of a knowledge card; `source` is carried verbatim — the plugin refuses
 * 03-Resources writes whose source is missing, so an empty source never reaches this function.
 * @param {{ title: string, type: string, source: string, created: string, candidate?: boolean }} fields - the card's frontmatter fields.
 * @returns {string} the YAML frontmatter text ending with a blank line.
 */
export function buildFrontmatter(fields) {
  const lines = ['---', `title: ${fields.title}`, `type: ${fields.type}`, `source: ${fields.source}`, `created: ${fields.created}`]
  if (fields.candidate) lines.push('candidate: true')
  lines.push('related: []', '---', '')
  return lines.join('\n') + '\n'
}

/**
 * Ensure a frontmatter field exists in an existing card: a frontmatter-less text passes through
 * unchanged (00-Inbox stays friction-free); a missing field is inserted before the closing fence.
 * @param {string} content - the existing file content.
 * @param {string} field - the frontmatter key, such as `source`.
 * @param {string | undefined} value - the value to insert when the key is absent; `undefined` inserts nothing.
 * @returns {string | null} the content with the field guaranteed, or null when there is no frontmatter to amend.
 */
export function ensureFrontmatterField(content, field, value) {
  if (!content.startsWith('---')) return null
  const end = content.indexOf('\n---', 3)
  if (end < 0) return null
  const head = content.slice(0, end)
  if (new RegExp(`^${field}:`, 'm').test(head)) return content
  if (value === undefined) return content
  return `${head}\n${field}: ${value}${content.slice(end)}`
}

/**
 * One processing-log line, the human-readable audit trail of every write the plugin performs.
 * @param {string} timestamp - the local time of the action, such as `2026-11-15 16:05`.
 * @param {string} summary - what was processed, at most about 40 characters.
 * @param {string} action - the action performed, such as `para_save` or `para_save+superseded`.
 * @param {string} targetPath - the absolute path written.
 * @param {string} source - the recorded source, `无来源说明` when absent.
 * @returns {string} the log line without trailing newline.
 */
export function logLine(timestamp, summary, action, targetPath, source) {
  const short = summary.length > 40 ? `${summary.slice(0, 40)}…` : summary
  return `- ${timestamp} | ${short} | ${action} | ${targetPath} | ${source || '无来源说明'}`
}

/**
 * The display title of a card: the filename without its `.md` suffix.
 * @param {string} filename - the sanitized file name.
 * @returns {string} the title text.
 */
export function titleOf(filename) {
  return basename(filename).replace(/\.md$/i, '')
}

/**
 * The absolute path of a knowledge file, rejecting any escape from the workspace: the directory
 * must be one of the six and the joined path must stay under the root.
 * @param {string} root - the absolute workspace root.
 * @param {string} dir - the requested top-level directory.
 * @param {string} filename - the requested file name, already sanitized of separators.
 * @returns {string | null} the joined absolute path, or null when the request escapes the workspace.
 */
export function knowledgeFilePath(root, dir, filename) {
  if (!KB_DIRECTORIES.includes(dir)) return null
  const target = resolve(join(root, dir, filename))
  return containedInRoot(root, target) ? target : null
}

/** The mutating tools a direct write denial examines; reads stay free. */
const MUTATING_TOOLS = new Set(['write', 'edit', 'bash', 'pwsh'])

/**
 * Whether one argument of a mutating tool call targets the knowledge workspace. `~` expands to the
 * caller's home; everything else resolves as-is, so relative paths (which resolve elsewhere) pass.
 * @param {string} value - a string argument of the call.
 * @param {string} root - the absolute workspace root.
 * @returns {boolean} true when the value points inside the workspace.
 */
function targetsWorkspace(value, root) {
  const expanded = value.startsWith('~') ? join(root, '..', value.slice(1)) : value
  return containedInRoot(root, resolve(expanded))
}

/**
 * Whether a workspace path is a governance/maintenance file at the workspace root (INDEX/README/
 * CLAUDE/AGENTS) or under config/ — files whose sanctioned maintenance is direct, user-authorized
 * editing rather than para_save (which only writes into the six directories).
 * @param {string} path - an absolute path inside the workspace.
 * @param {string} root - the absolute workspace root.
 * @returns {boolean} true for root-level maintenance files and anything under config/.
 */
function isMaintenanceFile(path, root) {
  const parent = resolve(path, '..')
  return parent === resolve(root) || parent === resolve(join(root, 'config'))
}

/**
 * The denial reason for a tool call that would write into the knowledge workspace without going
 * through `para_save` — the model-facing text also names the sanctioned path. Reads, the
 * knowledge tools themselves, root/config maintenance files (INDEX/README/治理规则/处理日志),
 * and git versioning commands on the workspace stay allowed; bash/pwsh are otherwise checked by
 * command text, a heuristic that by design cannot be complete (see the Phase 0 audit: it detects
 * the common redirect forms).
 * @param {string} tool - the called tool's name.
 * @param {unknown} args - the call's raw arguments.
 * @param {string} root - the absolute workspace root.
 * @returns {string | undefined} the denial reason, or undefined when the call may proceed.
 */
export function directWriteDenial(tool, args, root) {
  if (!MUTATING_TOOLS.has(tool)) return undefined
  const record = (args ?? {})
  if (tool === 'write' || tool === 'edit') {
    const filePath = typeof record.file_path === 'string' ? record.file_path : ''
    if (filePath && targetsWorkspace(filePath, root)) {
      const absolute = filePath.startsWith('~') ? join(root, '..', filePath.slice(1)) : filePath
      if (isMaintenanceFile(resolve(absolute), root)) return undefined
      return '知识库写入必须走 para_save（路径围栏/来源强制/处理日志），直接写文件已被禁用。要读取库内文件用 read；要入库资料用 para_route + para_save。'
    }
    return undefined
  }
  const command = typeof record.command === 'string' ? record.command : ''
  if (command && (command.includes(root) || command.includes(basename(root)))) {
    if (/git\s+(-C\s+\S+\s+)?(init|add|commit|push|pull|fetch|log|status|diff|show|ls-files|mv)\b/.test(command)) return undefined
    return `对知识库（${basename(root)}）的 shell 写操作已被禁用：入库走 para_route + para_save；版本历史用 git 命令；读取用 read 工具。`
  }
  return undefined
}
