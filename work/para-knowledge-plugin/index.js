/**
 * The PARA knowledge tools: `para_route` suggests where input belongs and what already exists,
 * `para_save` writes into the knowledge workspace under guard rails (path fence, no silent
 * overwrite, mandatory source for external material, atomic write, processing-log line).
 * The workspace root defaults to `~/我的知识库`; this plugin carries no Harness domain logic.
 * Ported 2026-11-16 from dsh-superagent src/para-knowledge.ts into this standalone bundle so the
 * Plugins page can list it as its own package; the dsh-superagent worker preset activates this
 * plugin by referencing the package name `dsh-para-knowledge`.
 * @module dsh-para-knowledge
 */

import { existsSync, mkdirSync, readdirSync, readFileSync, renameSync, statSync, appendFileSync, writeFileSync, unlinkSync } from 'node:fs'
import { homedir } from 'node:os'
import { basename, extname, join, resolve } from 'node:path'
import {
  KB_DIRECTORIES, KB_TYPES, TYPE_DIRECTORY, buildFrontmatter, containedInRoot, ensureFrontmatterField,
  knowledgeFilePath, logLine, salientTokens, suggestDirectories, supersededName, titleOf, directWriteDenial,
} from './knowledge.js'

/** Cordis plugin name used by loader diagnostics. */
export const name = 'para-knowledge'

/** Services required by the plugin: the tool registry and system prompt of the Session it composes into. */
export const inject = ['tools', 'systemPrompt']

/** Max bytes of one file head read during conflict matching. */
const HEAD_BYTES = 4096
/** Max files examined during one conflict scan. */
const SCAN_CAP = 120

/**
 * Resolve the effective workspace root and fail with a model-facing message when it is missing,
 * so a call against an uninitialized workspace explains the remedy instead of failing obscurely.
 * @param {string} root - the absolute workspace root.
 * @returns {string} the absolute workspace root.
 */
function ensureWorkspace(root) {
  if (!existsSync(root)) throw new Error(`知识库不存在：${root}（先完成初始化，或检查 para-knowledge 插件的 root 配置）`)
  return root
}

/**
 * Read the head of a file for conflict matching, returning an empty string for anything unreadable,
 * so one bad file never breaks a scan.
 * @param {string} path - the file to sample.
 * @returns {string} at most {@link HEAD_BYTES} bytes decoded as UTF-8.
 */
function headOf(path) {
  try {
    if (statSync(path).size <= 0) return ''
    const fd = readFileSync(path)
    return fd.subarray(0, HEAD_BYTES).toString('utf8')
  } catch {
    return ''
  }
}

/**
 * Collect the markdown files of the six workspace directories with their sampled heads.
 * @param {string} root - the workspace root.
 * @returns {{ path: string, dir: string, head: string }[]} at most {@link SCAN_CAP} entries.
 */
function scanWorkspace(root) {
  const found = []
  for (const dir of KB_DIRECTORIES) {
    const absolute = join(root, dir)
    if (!existsSync(absolute)) continue
    for (const entry of readdirSync(absolute)) {
      if (found.length >= SCAN_CAP) return found
      if (!entry.endsWith('.md') || entry.startsWith('.')) continue
      const path = join(absolute, entry)
      found.push({ path, dir, head: headOf(path) })
    }
  }
  return found
}

/**
 * Apply the plugin: resolve the workspace root and register the two PARA tools.
 * @param {import('@deepseek-ai/cordis').Context} ctx - the composition context of the Session preset this plugin loads into.
 * @param {{ root?: string } | undefined} config - the plugin configuration; every field optional.
 */
export async function apply(ctx, config) {
  const root = resolve(typeof config?.root === 'string' && config.root.trim() !== '' ? config.root : join(homedir(), '我的知识库'))

  const paraRoute = {
    name: 'para_route',
    description: 'PARA 知识库路由建议：判断资料应进入哪个目录（00-Inbox/01-Projects/02-Areas/03-Resources/04-Archive/05-Skills），'
      + '并检索库内是否已有相关内容。只读不写。处理资料前先调用本工具，再决定新建、补充、关联或留在 Inbox。',
    parameters: {
      type: 'object',
      properties: {
        content: { type: 'string', description: '资料的标题与首段或摘要（≤4000 字），用于分类与查重。' },
        intent: { type: 'string', description: '用户对该资料的意图说明（可选），辅助分类。' },
      },
      required: ['content'],
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          suggestions: { type: 'array' },
          existing: { type: 'array' },
          advice: { type: 'string' },
        },
        required: ['suggestions', 'existing', 'advice'],
      },
      render: (_args, value) => [{
        type: 'text',
        text: `<para_route>\n建议目录：${value.suggestions.map(item => `${item.dir}（${item.reason}）`).join('；') || '00-Inbox'}`
          + `\n已有相关：${value.existing.length > 0 ? value.existing.join('、') : '未发现'}\n${value.advice}\n</para_route>`,
      }],
    },
    async execute(args) {
      const input = args ?? {}
      if (typeof input.content !== 'string' || input.content.trim().length === 0) {
        throw new Error('content must be a non-empty string')
      }
      const text = input.content.slice(0, 4000) + (typeof input.intent === 'string' && input.intent.trim().length > 0 ? `\n${input.intent.slice(0, 500)}` : '')
      const suggestions = suggestDirectories(text)
      const tokens = salientTokens(text)
      const existing = scanWorkspace(root)
        .map(file => {
          const fileName = basename(file.path)
          const score = tokens.filter(token => fileName.includes(token) || file.head.includes(token)).length
          return { path: file.path, score }
        })
        .filter(match => match.score > 0)
        .sort((a, b) => b.score - a.score)
        .slice(0, 8)
        .map(match => match.path)
      const advice = existing.length > 0
        ? '发现库内已有相关文件：先读取它们，再决定是新建、补充进既有文件，还是在 related 中建立关联；不要重复保存同一知识。'
        : suggestions[0].dir === '00-Inbox'
          ? '无法可靠判断资料性质：存入 00-Inbox/（原样保留，不强行分类），并在处理日志记录，等待后续判断。'
          : `建议存入 ${suggestions[0].dir}/；外部原文进 03-Resources 必须带 source；写入用 para_save。`
      return { suggestions, existing, advice }
    },
  }

  const paraSave = {
    name: 'para_save',
    description: '受控写入 PARA 知识库：路径围栏（仅限库内）、默认拒绝覆盖已有文件（supersede=true 时旧文件改名保留）、'
      + '03-Resources 强制 source、frontmatter 自动补全、原子写入并追加 config/processing-log.md。'
      + '写入前应已用 para_route 判断落点。00-Inbox 原样保存，不强制格式。',
    parameters: {
      type: 'object',
      properties: {
        dir: { type: 'string', description: `目标目录，其一：${KB_DIRECTORIES.join(' / ')}` },
        filename: { type: 'string', description: '文件名（不含路径；建议中文问题式标题；自动补 .md）。' },
        content: { type: 'string', description: '要写入的完整 Markdown 内容；给 source_path 时可省略（正文取自该文件）。' },
        source_path: { type: 'string', description: '源文件绝对路径（可选）：读取该文件全文作为正文，适合把原管线的转写/文档批量归档进库；文件在库外也允许（只读导入）。' },
        source: { type: 'string', description: '来源链接或出处；存 03-Resources 时必填（source_path 亦计入），其他目录建议提供。' },
        type: { type: 'string', description: '卡片类型（可选）：Knowledge / Experience / Source / Skill / Project；缺省按目录推断。' },
        supersede: { type: 'boolean', description: '目标已存在时是否显式替换（旧文件改名 .superseded-<时间> 保留）。默认 false。' },
      },
      required: ['dir', 'filename'],
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          status: { type: 'string', enum: ['written', 'superseded', 'conflict'] },
          path: { type: 'string' },
          log_line: { type: 'string' },
          detail: { type: 'string' },
        },
        required: ['status', 'path', 'log_line', 'detail'],
      },
      render: (_args, value) => [{
        type: 'text',
        text: `<para_save status="${String(value.status)}">\n${value.detail}\n路径：${String(value.path)}\n日志：${String(value.log_line)}\n</para_save>`,
      }],
    },
    async execute(args) {
      const input = args ?? {}
      const dir = typeof input.dir === 'string' ? input.dir : ''
      const filename = typeof input.filename === 'string' ? input.filename.trim() : ''
      let content = typeof input.content === 'string' ? input.content : ''
      const sourceArg = typeof input.source === 'string' && input.source.trim().length > 0 ? input.source.trim() : undefined
      // source_path import: read the original file as the body (only-read import; the file may live
      // outside the workspace, e.g. an ASR pipeline path) and default the source to that path.
      let source = sourceArg
      const sourcePath = typeof input.source_path === 'string' && input.source_path.trim().length > 0 ? input.source_path.trim() : undefined
      if (sourcePath) {
        const origin = resolve(sourcePath)
        if (!existsSync(origin)) throw new Error(`source_path 不存在：${origin}`)
        if (!content) content = readFileSync(origin, 'utf8')
        source = source ?? origin
      }
      if (!dir || !filename || (!content && dir !== '00-Inbox')) {
        throw new Error('dir、filename、content 必须为非空字符串（00-Inbox 允许空内容占位文件）；或提供 source_path 作为正文来源')
      }
      const sanitized = basename(filename).replace(/[\\/:*?"<>|.]/g, match => (match === '.' ? match : '')).replace(/^\.+/, '').trim()
      const safeName = (sanitized.length > 0 ? sanitized : `未命名-${Date.now()}`) + (extname(sanitized).toLowerCase() === '.md' ? '' : '.md')
      const target = knowledgeFilePath(ensureWorkspace(root), dir, safeName)
      if (target === null) {
        throw new Error(`目标越出知识库范围：dir=${dir} filename=${filename}`)
      }
      const now = new Date()
      const pad = value => String(value).padStart(2, '0')
      const stamp = `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
      const timestamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`

      mkdirSync(resolve(target, '..'), { recursive: true })
      const archiveDir = resolve(root, '04-Archive')
      let status = 'written'
      let supersededArchivePath = ''
      let detail = ''
      if (existsSync(target)) {
        if (input.supersede !== true) {
          const preview = headOf(target).split('\n').slice(0, 20).join('\n')
          return {
            status: 'conflict',
            path: target,
            log_line: '',
            detail: `目标已存在，未写入（默认拒绝覆盖）。既有文件前 20 行：\n${preview}\n确认要替换时以 supersede=true 重发（旧文件会迁入 04-Archive/ 以 ${supersededName(safeName, stamp)} 命名保留）；或改用其他文件名/先读后补。`,
          }
        }
        // Superseded versions move to the archive directory（归档不等于删除，也不留在原目录）：
        // same .superseded-<stamp> name under 04-Archive, numeric suffix on collision.
        mkdirSync(archiveDir, { recursive: true })
        supersededArchivePath = resolve(archiveDir, supersededName(safeName, stamp))
        let bump = 2
        while (existsSync(supersededArchivePath)) {
          supersededArchivePath = resolve(archiveDir, `${supersededName(safeName, stamp)}-${bump}`)
          bump += 1
        }
        renameSync(target, supersededArchivePath)
        status = 'superseded'
        detail = `已替换（旧文件迁入 04-Archive/ 保留：${basename(supersededArchivePath)}）。`
      }

      let body = content
      if (dir !== '00-Inbox') {
        const type = (typeof input.type === 'string' && KB_TYPES.includes(input.type))
          ? input.type
          : (Object.entries(TYPE_DIRECTORY).find(([, directory]) => directory === dir)?.[0] ?? 'Knowledge')
        if (dir === '03-Resources' && !source) {
          throw new Error('03-Resources 为外部原文目录：source（链接/出处）必填，不许留空。')
        }
        if (content.startsWith('---')) {
          const amended = ensureFrontmatterField(content, 'source', source)
          if (amended !== null) body = amended
        } else {
          body = buildFrontmatter({ title: titleOf(safeName), type, source: source ?? '无来源说明', created: timestamp.slice(0, 10), candidate: dir === '02-Areas' })
            + content
        }
      }
      const temporary = `${target}.${process.pid}.tmp`
      writeFileSync(temporary, body, 'utf8')
      renameSync(temporary, target)

      const line = logLine(timestamp, safeName, status === 'superseded' ? 'para_save+superseded' : 'para_save', target, source ?? '')
      try {
        appendFileSync(resolve(root, 'config', 'processing-log.md'), `${line}\n`, 'utf8')
      } catch (error) {
        // The log is the receipt: a write without its log line must not survive (K10). Roll the
        // filesystem back — remove the new file, restore the superseded one from the archive —
        // then report the failure.
        try {
          unlinkSync(target)
          if (status === 'superseded') renameSync(supersededArchivePath, target)
        } catch { /* report the log failure either way; the log failure itself is the primary error */ }
        throw new Error(`处理日志写入失败，本次写入已回滚（不得把失败记录成成功）：${resolve(root, 'config', 'processing-log.md')}；原因：${String(error)}`)
      }
      if (status === 'written') detail = `已写入 ${dir}/。${dir === '00-Inbox' ? '（Inbox 不强制格式）' : 'frontmatter 已补全。'}记得检查 INDEX.md 是否需要更新。`
      return { status, path: target, log_line: line, detail }
    },
  }

  ctx.tools.register(paraRoute)
  ctx.tools.register(paraSave)
  // Hard fence for the bypass paths the Phase 0 audit flagged: a worker writing the workspace with
  // the native write/edit tools or a shell redirect skips para_save entirely. The guard denies
  // such calls (reads stay free; git versioning commands stay allowed) — turning the governance
  // guidance into a tool-layer enforcement, still short of an OS sandbox.
  ctx.tools.guard(execution => directWriteDenial(String(execution.name), execution.arguments, root))
  // Tell the model, in its own system prompt, when and how to process input into the workspace —
  // the tool descriptions alone carry the rules but not the trigger. The section evaluates per
  // assembly and contributes nothing where the tools are absent (mirrors the write tool's hint).
  ctx.systemPrompt.section({
    name: 'para-knowledge',
    order: 9500,
    text: ({ scope }) => ctx.tools.get('para_save', scope) === undefined
      ? ''
      : '收到文档、文章、资料或「处理入库」类请求时：先用 para_route 判断该进 ' + root +
        ' 的哪个目录并检查已有内容，再按其建议用 para_save 保存。要点：外部原文进 03-Resources/ 且必须带来源链接；' +
        '项目进展更新 01-Projects/；可复用方法/流程进 05-Skills/；个人经验总结经确认后进 02-Areas/；' +
        '拿不准的原样进 00-Inbox/，不强行分类；已有同名文件默认不覆盖。保存后向用户报告文件位置。' +
        '完整规则见库内 config/agent-governance.md。',
  })
  // Fail loudly if the workspace exists but is not the initialized workspace, so a wrong root
  // surfaces at composition time instead of at first write.
  if (existsSync(root) && !existsSync(resolve(root, 'config', 'agent-governance.md'))) {
    ctx.logger.warn('para-knowledge: %s 缺少 config/agent-governance.md，可能不是初始化过的知识库', root)
  }
}

/** Re-exported for tests and future adapters; pure rules live in `knowledge.js`. */
export { containedInRoot, knowledgeFilePath, salientTokens, suggestDirectories, supersededName }
