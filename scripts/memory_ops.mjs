#!/usr/bin/env node
// memory_ops.mjs — 通过 dsh-memory-evolve 官方实现类执行记忆/待办操作。
// 原则：不直改记忆 .md 文件（drift guard 会拒绝后续写入）；
// 所有写入走插件自己的 MemoryStore / TodoStore / SuggestionQueue 代码路径，
// 与 LLM 工具（memory / dtodo）行为逐字节一致。
//
// 用法：
//   node memory_ops.mjs dedup-check <关键词>          全局 memory 轨 + 本项目 key 轨查重
//   node memory_ops.mjs todo-add <due> <内容...>      work 轨待办（q2）
//   node memory_ops.mjs key-suggest <summary> <内容…>  key 建议（确认队列，内置去重）
//   node memory_ops.mjs log <内容...>                 daily+project 各写一条进展
//
// 环境：PLUGIN_DIR（插件根，缺省 ~/.dsh/plugins/dsh-memory-evolve）
//       MEM_DIR（记忆目录，缺省 ~/.dsh/memories）
//       AGENT_CWD（会话工作目录，缺省本脚本所在仓库根）
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { homedir } from 'node:os'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const here = dirname(fileURLToPath(import.meta.url))
const pluginDir = process.env.PLUGIN_DIR ?? join(homedir(), '.dsh/plugins/dsh-memory-evolve')
const memDir = process.env.MEM_DIR ?? join(homedir(), '.dsh/memories')
const agentCwd = process.env.AGENT_CWD ?? dirname(here)
const agent = {
  id: 'worker-optimize-memory-frame',
  session: { header: { cwd: agentCwd } },
}

const { MemoryStore, SuggestionQueue } = await import(join(pluginDir, 'lib/store.js'))
const { TodoStore } = await import(join(pluginDir, 'lib/todo.js'))
const { enqueueSuggestion } = await import(join(pluginDir, 'lib/review.js'))

const store = new MemoryStore(memDir)
const queue = new SuggestionQueue(join(memDir, 'SUGGESTIONS.jsonl'))
const todoStore = new TodoStore(memDir)

const [cmd, ...rest] = process.argv.slice(2)

function out(label, value) {
  console.log(`${label}: ${JSON.stringify(value)}`)
}

switch (cmd) {
  case 'dedup-check': {
    const q = String(rest[0] ?? '').trim().toLowerCase()
    if (!q) { console.error('需要关键词'); process.exit(2) }
    for (const target of ['memory', 'key']) {
      const entries = store.entriesOf(target, agent).filter((e) => e.toLowerCase().includes(q))
      out(`track=${target} matches`, { keyword: q, count: entries.length, entries })
    }
    break
  }
  case 'todo-add': {
    const [due, ...text] = rest
    const r = todoStore.addTodo('work', text.join(' '), { quadrant: 'q2', due: String(due ?? ''), cat: '记忆治理' })
    out('todo-add', r)
    process.exitCode = r.ok ? 0 : 1
    break
  }
  case 'key-suggest': {
    const [summary, ...text] = rest
    const sanitized = String(summary ?? '').replace(/[\n\r\t\]]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 120)
    const content = sanitized ? `[summary:${sanitized}]\n${text.join(' ')}` : text.join(' ')
    const r = enqueueSuggestion(queue, 'key', content, '工单提交的关键记忆建议（待用户确认）', agent)
    out('key-suggest', r)
    process.exitCode = r.ok ? 0 : 1
    break
  }
  case 'log': {
    const content = rest.join(' ')
    for (const target of ['daily', 'project']) {
      const r = store.add(target, content, agent)
      out(`log target=${target}`, r)
      if (!r.ok) process.exitCode = 1
    }
    break
  }
  default:
    console.error('未知命令；见文件头用法注释')
    process.exit(2)
}
