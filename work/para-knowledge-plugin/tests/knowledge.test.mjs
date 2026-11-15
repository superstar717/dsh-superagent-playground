/**
 * The pure domain rules of the PARA knowledge workspace: routing suggestions, conflict tokens,
 * path containment, superseded naming, frontmatter building, log lines and the direct-write
 * denial. Ported 2026-11-16 from dsh-superagent tests/knowledge.spec.ts (vitest) to node:test,
 * keeping every case 1:1. Run: `npm test` (node --test tests/).
 */
import { join } from 'node:path'
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildFrontmatter, containedInRoot, directWriteDenial, ensureFrontmatterField, knowledgeFilePath, logLine, salientTokens,
  suggestDirectories, supersededName,
} from '../knowledge.js'

describe('knowledge routing', () => {
  it('suggests 01-Projects for goal-bearing work', () => {
    const suggestions = suggestDirectories('短视频选题项目计划：目标两周内完成 30 条选题，里程碑与截止时间如下')
    assert.equal(suggestions[0].dir, '01-Projects')
  })

  it('suggests 05-Skills for reusable procedures', () => {
    const suggestions = suggestDirectories('视频剪辑 SOP：五步工作流，含模板与清单，可直接复用')
    assert.equal(suggestions[0].dir, '05-Skills')
  })

  it('routes cognitive frameworks to 02-Areas, not 05-Skills', () => {
    // 2026-11-15 实测误路由：提炼「结构、框架、认知」曾被首推到 05-Skills。
    const suggestions = suggestDirectories('提炼结构、框架、认知、系统等核心知识，认知博主的方法论与体系')
    assert.equal(suggestions[0].dir, '02-Areas')
  })

  it('suggests 03-Resources for external material with links', () => {
    const suggestions = suggestDirectories('转载文章：某论文解读 https://example.com/paper 原文如下')
    assert.equal(suggestions[0].dir, '03-Resources')
  })

  it('suggests 02-Areas for personal lessons', () => {
    const suggestions = suggestDirectories('复盘与心得：这次拍摄的最大教训是选题决定一半流量，我的总结如下')
    assert.equal(suggestions[0].dir, '02-Areas')
  })

  it('keeps unclassifiable input in 00-Inbox instead of force-classifying it', () => {
    const suggestions = suggestDirectories('嗯，随便记一句：明天记得带伞')
    assert.equal(suggestions[0].dir, '00-Inbox')
  })
})

describe('salient tokens', () => {
  it('extracts CJK runs and ASCII words, dropping filler, longest-frequency first', () => {
    const tokens = salientTokens('选题方法（selection workflow）：讲「选题」，选题决定流量')
    assert.ok(tokens.includes('选题方法'))
    assert.ok(tokens.includes('选题'))
    assert.ok(tokens.includes('selection'))
    assert.ok(!tokens.includes('的'))
  })

  it('returns at most eight tokens', () => {
    const tokens = salientTokens('抖音直播带货选品流量转化话术脚本投放复盘数据分析私域运营公域引流')
    assert.ok(tokens.length <= 8)
  })
})

describe('path containment', () => {
  const root = '/Users/someone/我的知识库'

  it('accepts paths inside the root', () => {
    assert.equal(containedInRoot(root, join(root, '02-Areas', '什么是PARA.md')), true)
  })

  it('rejects traversal and outside paths', () => {
    assert.equal(containedInRoot(root, join(root, '..', '姜胡说', 'secret.md')), false)
    assert.equal(containedInRoot(root, '/etc/passwd'), false)
    assert.equal(containedInRoot(root, '相对路径.md'), false)
  })

  it('rejects a sibling directory whose name merely extends the root name', () => {
    assert.equal(containedInRoot(root, `${root}-evil/文件.md`), false)
  })

  it('builds a file path only for the six directories', () => {
    assert.equal(knowledgeFilePath(root, '02-Areas', '什么是PARA.md'), join(root, '02-Areas', '什么是PARA.md'))
    assert.equal(knowledgeFilePath(root, '99-Evil', 'x.md'), null)
  })
})

describe('superseded naming', () => {
  it('inserts the stamp before the extension', () => {
    assert.equal(supersededName('什么是PARA.md', '20261115-1605'), '什么是PARA.superseded-20261115-1605.md')
  })

  it('appends the stamp to extension-less names', () => {
    assert.equal(supersededName('未命名', '20261115-1605'), '未命名.superseded-20261115-1605')
  })
})

describe('frontmatter', () => {
  it('builds a card block with the mandatory fields', () => {
    const text = buildFrontmatter({ title: '什么是PARA', type: 'Knowledge', source: 'https://example.com', created: '2026-11-15', candidate: true })
    assert.ok(text.includes('title: 什么是PARA'))
    assert.ok(text.includes('source: https://example.com'))
    assert.ok(text.includes('candidate: true'))
    assert.ok(text.startsWith('---'))
  })

  it('inserts a missing field into existing frontmatter and keeps present fields', () => {
    const existing = '---\ntitle: A\ntype: Source\n---\n\n正文'
    const withSource = ensureFrontmatterField(existing, 'source', 'https://example.com')
    assert.ok(withSource.includes('source: https://example.com'))
    assert.ok(withSource.includes('正文'))
    assert.ok(ensureFrontmatterField(existing.replace('type: Source\n', 'type: Source\nsource: 已有\n'), 'source', 'x')
      .includes('source: 已有'))
  })

  it('returns null for frontmatter-less text so 00-Inbox stays untouched', () => {
    assert.equal(ensureFrontmatterField('纯文本', 'source', 'x'), null)
  })
})

describe('processing log', () => {
  it('formats one line with time, summary, action, path and source', () => {
    const line = logLine('2026-11-15 16:05', '一篇很长的资料标题需要被截断处理一下下', 'para_save', '/kb/03-Resources/a.md', 'https://example.com')
    assert.match(line, /^- 2026-11-15 16:05 \| .+ \| para_save \| \/kb\/03-Resources\/a\.md \| https:\/\/example\.com$/)
  })

  it('truncates long summaries and marks a missing source', () => {
    const line = logLine('2026-11-15 16:05', '一'.repeat(60), 'para_save', '/kb/00-Inbox/a.md', '')
    assert.ok(line.includes('…'))
    assert.ok(line.endsWith('| 无来源说明'))
  })
})

describe('direct write denial', () => {
  const root = '/Users/someone/我的知识库'

  it('denies write/edit targeting the workspace, allows elsewhere', () => {
    assert.ok(directWriteDenial('write', { file_path: join(root, '02-Areas', 'x.md'), content: 'x' }, root).includes('para_save'))
    assert.ok(directWriteDenial('edit', { file_path: '~/我的知识库/02-Areas/x.md' }, root).includes('para_save'))
    assert.equal(directWriteDenial('write', { file_path: '/Users/someone/other/x.md', content: 'x' }, root), undefined)
  })

  it('denies shell writes against the workspace but keeps git versioning allowed', () => {
    assert.ok(directWriteDenial('bash', { command: `echo x >> ${root}/02-Areas/x.md` }, root).includes('禁用'))
    assert.equal(directWriteDenial('bash', { command: `git -C ${root} add -A && git -C ${root} commit -m x` }, root), undefined)
    assert.equal(directWriteDenial('bash', { command: `git -C ${root} push` }, root), undefined)
    assert.equal(directWriteDenial('bash', { command: `git -C ${root} mv 05-Skills/a.md 04-Archive/a.superseded.md` }, root), undefined)
    assert.equal(directWriteDenial('bash', { command: `ls /Users/someone/other` }, root), undefined)
  })

  it('never denies the knowledge tools themselves, nor reads', () => {
    assert.equal(directWriteDenial('para_save', { dir: '03-Resources', filename: 'x.md', content: 'x' }, root), undefined)
    assert.equal(directWriteDenial('para_route', { content: 'x' }, root), undefined)
    assert.equal(directWriteDenial('read', { file_path: join(root, 'INDEX.md') }, root), undefined)
  })

  it('allows direct edits to root governance files and config, denies content dirs', () => {
    assert.equal(directWriteDenial('edit', { file_path: join(root, 'INDEX.md') }, root), undefined)
    assert.equal(directWriteDenial('edit', { file_path: join(root, 'config', 'agent-governance.md') }, root), undefined)
    assert.equal(directWriteDenial('write', { file_path: join(root, 'README.md'), content: 'x' }, root), undefined)
    assert.ok(directWriteDenial('write', { file_path: join(root, '02-Areas', 'x.md'), content: 'x' }, root).includes('para_save'))
  })
})
