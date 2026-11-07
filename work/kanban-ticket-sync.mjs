#!/usr/bin/env node
// kanban-ticket-sync.mjs — sync dsh-superagent tickets into @alpacachen/dsh-kanban boards.
//
// Ticket 226d5178fb80 (kanban-empty-board): the kanban plugin stores one board
// per workspace (<workspace>/.dsh-kanban.json) and has no knowledge of the
// superagent ticket store, so every fresh ticket worktree shows an empty
// default board ("看板没有任务内容"). This script closes that gap WITHOUT
// touching plugin code or restarting the service: it drives the plugin's own
// authenticated HTTP API (/api/kanban) so every board write goes through the
// plugin's dispatcher — schema, id sequence, activity log and completedAt
// handling stay exactly as the plugin would have written them itself.
//
// What it does per ticket:
//   - locate the ticket's worktree (~/src/<name>-<id[:12]>)
//   - locate the GUI workspace id (~/.dsh/storages/workspace.json)
//   - read the board; find an existing card by the marker "工单 <id[:8]>" in
//     the note (create-only for boards a human already curates)
//   - missing  -> addCard in "In Progress" (open) or "Done" (ended)
//   - wrong column -> moveCard there (completedAt handled by the plugin)
//   - otherwise -> leave untouched (idempotent re-runs are no-ops)
//
// Auth: the service token is printed on its tmux pane ("dsh web: http://…
// ?token=…"), changes on restart, and is reused to mint the same cookie a
// browser gets. Pass --token explicitly or let the script read the pane.
//
// Usage:
//   node kanban-ticket-sync.mjs [--dry-run] [--token T] [--url http://127.0.0.1:3082]
//       [--src-dir ~/src] [--db ~/.dsh/state/superagent/orchestrator.sqlite]
//       [--workspace-json ~/.dsh/storages/workspace.json]
//       [--tmux-pane dsh-superagent:server] [--state <statefile>]
//
// Exit codes: 0 ok, 1 some tickets failed, 2 usage/environment error.

import { readdirSync, mkdirSync, readFileSync, writeFileSync, rmSync } from 'node:fs'
import { DatabaseSync } from 'node:sqlite'
import { execFileSync, execFile } from 'node:child_process'
import { homedir } from 'node:os'
import { dirname, join } from 'node:path'
import { promisify } from 'node:util'

const execFileAsync = promisify(execFile)

// ---- args ----
const arg = (name, def) => {
  const i = process.argv.indexOf('--' + name)
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def
}
const flag = (name) => process.argv.includes('--' + name)
const DRY = flag('dry-run')
const HOME = homedir()
const BASE = arg('url', 'http://127.0.0.1:3082')
const TMUX_PANE = arg('tmux-pane', 'dsh-superagent:server')
const SRC_DIR = arg('src-dir', join(HOME, 'src')).replace(/^~/, HOME)
const DB_PATH = arg('db', join(HOME, '.dsh/state/superagent/orchestrator.sqlite')).replace(/^~/, HOME)
const WS_JSON = arg('workspace-json', join(HOME, '.dsh/storages/workspace.json')).replace(/^~/, HOME)
const STATE_FILE = arg('state', join(HOME, '.dsh/state/kanban-ticket-sync/state.json')).replace(/^~/, HOME)

const log = (...a) => console.log(new Date().toISOString(), ...a)

// ---- token (explicit, else the service's tmux pane) ----
async function resolveToken() {
  const explicit = arg('token')
  if (explicit) return explicit
  const { stdout } = await execFileAsync('tmux', ['capture-pane', '-p', '-J', '-S', '-500', '-t', TMUX_PANE])
    .catch(() => ({ stdout: '' }))
  const m = stdout.match(/dsh web: http:\/\/[^\s?]+\/\?token=([A-Za-z0-9_-]+)/)
  if (!m) throw new Error(`no token: pass --token or check tmux pane ${TMUX_PANE}`)
  return m[1]
}

// ---- authenticated API client (same cookie a browser receives) ----
function api(cookie) {
  const post = async (method, args) => {
    const res = await fetch(BASE + '/api/kanban', {
      method: 'POST',
      headers: { 'content-type': 'application/json', cookie },
      body: JSON.stringify({ method, args }),
    })
    const body = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(`${method} HTTP ${res.status}: ${JSON.stringify(body).slice(0, 200)}`)
    if (body.error) throw new Error(`${method}: ${body.error}`)
    return body
  }
  return { post }
}

async function mintCookie(token) {
  const res = await fetch(`${BASE}/?token=${token}`, { redirect: 'manual' })
  const cookies = res.headers.getSetCookie?.() ?? []
  const auth = cookies.map((c) => c.split(';')[0]).find((c) => c.startsWith('dsh-auth-'))
  if (!auth) throw new Error('service did not issue an auth cookie (wrong token?)')
  return auth
}

// ---- tickets (read-only snapshot so the live WAL is never touched) ----
function readTickets() {
  const tmp = join(HOME, '.dsh', 'cache', `kanban-sync-orch-${process.pid}.sqlite`)
  mkdirSync(dirname(tmp), { recursive: true })
  execFileSync('sqlite3', [DB_PATH, `.backup ${tmp}`]) // single dot-command arg; includes WAL content
  try {
    const db = new DatabaseSync(tmp, { readOnly: true })
    const rows = db.prepare('SELECT id, value FROM ticket ORDER BY json_extract(value, \'$.createdAt\')').all()
    db.close()
    return rows.map(({ id, value }) => {
      const v = JSON.parse(value)
      const assignments = Array.isArray(v.assignments) ? v.assignments : []
      return {
        id,
        id8: id.slice(0, 8),
        title: String(v.title ?? id8),
        createdAt: v.createdAt ?? null,
        ended: v.ended ?? null, // {at, by, outcome} | null
        lastState: assignments.at(-1)?.state ?? null,
      }
    })
  } finally {
    rmSync(tmp, { force: true })
    rmSync(tmp + '-wal', { force: true })
    rmSync(tmp + '-shm', { force: true })
  }
}

// ---- worktrees and GUI workspaces ----
function worktreeFor(id, dirs) {
  const suffix = id.slice(0, 12)
  return dirs.find((d) => d.endsWith('-' + suffix)) ?? null
}

function workspaceIdByPath() {
  const raw = JSON.parse(readFileSync(WS_JSON, 'utf8'))
  const table = raw?.tables?.workspaces ?? {}
  const map = new Map()
  for (const [wid, ws] of Object.entries(table)) if (ws?.path) map.set(ws.path, wid)
  return map
}

// ---- sync ----
const MARKER = (t) => `工单 ${t.id8}` // detection key, also present in enable-kanban's hand-made card

async function main() {
  const token = await resolveToken()
  const cookie = await mintCookie(token)
  const { post } = api(cookie)
  const tickets = readTickets()
  const dirs = readdirSync(SRC_DIR).map((d) => join(SRC_DIR, d))
  const wsByPath = workspaceIdByPath()

  const created = []
  const moved = []
  const unchanged = []
  const failures = []
  const skipped = []

  for (const t of tickets) {
    try {
      const wt = worktreeFor(t.id, dirs)
      if (!wt) { skipped.push([t.id8, 'no worktree dir']); continue }
      const wsId = wsByPath.get(wt)
      if (!wsId) { skipped.push([t.id8, 'workspace not in GUI registry']); continue }

      const { board } = await post('get', { workspaceId: wsId })
      const desiredTitle = t.ended ? 'Done' : 'In Progress'
      const column = board.columns.find((c) => c.title === desiredTitle)
      if (!column) { failures.push([t.id8, `board has no "${desiredTitle}" column`]); continue }

      const card = board.cards.find((c) => String(c.note ?? '').includes(MARKER(t)))
      if (!card) {
        const note = [
          `工单 ${t.id}`,
          `状态：${t.ended ? `已完成（${String(t.ended.at ?? '').slice(0, 10)}，${t.ended.outcome ?? '未知结果'}）` : '进行中'}`,
          `同步时间：${new Date().toISOString()}`,
          '来源：superagent 工单系统自动同步（kanban-ticket-sync.mjs）',
        ].join('\n')
        if (DRY) { log('dry-run create', t.id8, '→', desiredTitle); created.push([t.id8, 'dry-run']) }
        else {
          const res = await post('addCard', { workspaceId: wsId, columnId: column.id, title: t.title, note })
          log('created card', res.cardId, 'for', t.id8, 'in', desiredTitle)
          created.push([t.id8, res.cardId])
        }
      } else if (card.columnId !== column.id) {
        if (DRY) { log('dry-run move', t.id8, '→', desiredTitle); moved.push([t.id8, 'dry-run']) }
        else {
          await post('moveCard', { workspaceId: wsId, id: card.id, columnId: column.id })
          log('moved card', card.id, 'for', t.id8, '→', desiredTitle)
          moved.push([t.id8, card.id])
        }
      } else {
        unchanged.push(t.id8)
      }
    } catch (err) {
      failures.push([t.id8, String(err.message || err).slice(0, 160)])
    }
  }

  const summary = { runAt: new Date().toISOString(), dryRun: DRY, created, moved, unchanged, failures, skipped }
  if (!DRY) { mkdirSync(dirname(STATE_FILE), { recursive: true }); writeFileSync(STATE_FILE, JSON.stringify(summary, null, 2) + '\n') }
  log(JSON.stringify({ created: created.length, moved: moved.length, unchanged: unchanged.length, skipped: skipped.length, failures: failures.length }))
  for (const [id, why] of skipped) log('skipped', id, '—', why)
  for (const [id, why] of failures) log('FAILED', id, '—', why)
  if (failures.length) process.exitCode = 1
}

main().catch((err) => { console.error(err); process.exit(2) })
