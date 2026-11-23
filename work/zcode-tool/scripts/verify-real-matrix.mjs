#!/usr/bin/env node
/**
 * Real-task verification matrix for @local/zcode-tool.
 *
 * Runs the plugin's execute path (fake ctx, requireApproval:false) against the
 * real `zcode` CLI, one scenario per sandbox directory. Every scenario consumes
 * Z.ai coding-plan quota (~35-90 s, tens of thousands of input tokens per
 * call) and needs `zcode login` to be valid.
 *
 * Closes the gaps left open in VERIFICATION-2026-11-22.md ("未验证/已知限制"):
 *   - mode matrix: plan / build / edit / yolo (guarded was verified in ②);
 *   - attach / resume against the real CLI;
 *   - a real timeout killing the process group.
 *
 * Mode semantics asserted here come from the CLI permission docs
 * (~/.local/zcode-src/apps/zcode-cli/docs/usage/05-permissions.md):
 *   plan  — writes and command execution restricted;
 *   build — writes usually need approval; a headless --prompt run has no
 *           approval client, so the write fails (the CLI may still exit 0);
 *   edit  — workspace file edits usually approval-free;
 *   yolo  — ordinary tools skip permission prompts.
 *
 * Usage:
 *   node scripts/verify-real-matrix.mjs                     # all scenarios
 *   node scripts/verify-real-matrix.mjs --only plan,edit    # subset
 *   node scripts/verify-real-matrix.mjs --json
 *   ZCODE_TOOL_ZCODE=/path/to/fake node scripts/verify-real-matrix.mjs  # test this script
 */

import { execFile } from 'node:child_process'
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { promisify } from 'node:util'

import { apply, parseZcodeJson } from '../index.js'

const execFileAsync = promisify(execFile)

const EXEC_TIMEOUT_MS = 240_000
const CALL_EXEC = () => ({ signal: new AbortController().signal, agent: undefined })

function usage() {
  console.log(`Usage: node scripts/verify-real-matrix.mjs [--only <name,name,...>] [--json]

  scenarios: plan, build, edit, yolo, attach, resume, timeout
  (each runs one real ZCode call and consumes Z.ai quota; resume runs two)`)
}

function parseArgs(argv) {
  const options = { only: undefined, json: false }
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--json') options.json = true
    else if (arg === '--help' || arg === '-h') options.help = true
    else if (arg === '--only') {
      options.only = String(argv[index + 1] ?? '')
        .split(',')
        .map(name => name.trim())
        .filter(Boolean)
      index += 1
    } else throw new Error(`unknown argument: ${arg}`)
  }
  return options
}

function truncate(text, max = 200) {
  const value = typeof text === 'string' ? text : JSON.stringify(text)
  return value.length > max ? `${value.slice(0, max)}…` : value
}

function responseOf(result) {
  const parsed = parseZcodeJson(result.stdout)
  return parsed && typeof parsed.response === 'string' ? parsed.response : ''
}

/** Register zcode_run once via apply() with approval disabled (headless). */
function makeTool() {
  const tools = []
  apply(
    {
      tools: { register(definition) { tools.push(definition) } },
      on() {},
      logger: { info() {} },
      get() { return undefined },
    },
    {
      requireApproval: false,
      ...(process.env.ZCODE_TOOL_ZCODE ? { zcodePath: process.env.ZCODE_TOOL_ZCODE } : {}),
    },
  )
  return tools[0]
}

async function withSandbox(name, run) {
  const cwd = await mkdtemp(join(tmpdir(), `zcode-matrix-${name}-`))
  try {
    return await run(cwd)
  } finally {
    await rm(cwd, { recursive: true, force: true })
  }
}

/**
 * plan: reading is allowed, writes/commands are restricted. Assert the marker
 * file is quoted and the sandbox gained no new files.
 */
async function scenarioPlan(tool) {
  return withSandbox('plan', async cwd => {
    const marker = 'ZCODE-PLAN-MARKER-Q7X'
    await writeFile(join(cwd, 'note.txt'), `${marker}\n`, 'utf8')
    const result = await tool.execute({
      task: '读取 note.txt，在回复中原样给出它的全部内容。不要创建、修改或删除任何文件，也不要执行命令。',
      cwd,
      mode: 'plan',
      timeout_ms: EXEC_TIMEOUT_MS,
    }, CALL_EXEC())
    const entries = await readdir(cwd)
    // The ZCode CLI scaffolds dot-directories (e.g. .mimosa, .video_agent) in
    // the cwd itself; only visible files count as model-made writes.
    const files = entries.filter(name => !name.startsWith('.'))
    const response = responseOf(result)
    const pass = result.ok === true
      && files.length === 1 && files[0] === 'note.txt'
      && response.includes(marker)
    return {
      pass,
      detail: `ok=${result.ok} exit=${result.exitCode} files=[${files.join(',')}] all=[${entries.join(',')}] response=${truncate(response)}`,
    }
  })
}

/**
 * build: writes need approval; headless has no approval client, so the write
 * must fail. The CLI itself may still exit 0 (documented), so the file being
 * absent is the assertion; exit code and response are recorded as observed.
 */
async function scenarioBuild(tool) {
  return withSandbox('build', async cwd => {
    const result = await tool.execute({
      task: '创建文件 build.txt，内容为一行文本：ok',
      cwd,
      mode: 'build',
      timeout_ms: EXEC_TIMEOUT_MS,
    }, CALL_EXEC())
    const files = await readdir(cwd)
    const pass = !files.includes('build.txt')
    return {
      pass,
      detail: `files=[${files.join(',')}] ok=${result.ok} exit=${result.exitCode} response=${truncate(responseOf(result))}`,
    }
  })
}

/** edit: workspace file edits are usually approval-free. */
async function scenarioEdit(tool) {
  return withSandbox('edit', async cwd => {
    const result = await tool.execute({
      task: '创建文件 edit.txt，内容为一行文本：ok',
      cwd,
      mode: 'edit',
      timeout_ms: EXEC_TIMEOUT_MS,
    }, CALL_EXEC())
    const files = await readdir(cwd)
    const content = await readFile(join(cwd, 'edit.txt'), 'utf8').catch(() => '')
    const response = responseOf(result)
    const pass = files.includes('edit.txt') && content.includes('ok')
    return {
      pass,
      detail: `files=[${files.join(',')}] content=${truncate(content, 60)} ok=${result.ok} exit=${result.exitCode} response=${truncate(response)}`,
    }
  })
}

/** yolo: ordinary tools skip permission prompts, including shell commands. */
async function scenarioYolo(tool) {
  return withSandbox('yolo', async cwd => {
    const result = await tool.execute({
      task: '用 shell 命令把一行文本 ok 写入文件 yolo.txt，然后确认写入成功。',
      cwd,
      mode: 'yolo',
      timeout_ms: EXEC_TIMEOUT_MS,
    }, CALL_EXEC())
    const files = await readdir(cwd)
    const content = await readFile(join(cwd, 'yolo.txt'), 'utf8').catch(() => '')
    const response = responseOf(result)
    const pass = files.includes('yolo.txt') && content.includes('ok')
    return {
      pass,
      detail: `files=[${files.join(',')}] content=${truncate(content, 60)} ok=${result.ok} exit=${result.exitCode} response=${truncate(response)}`,
    }
  })
}

/**
 * attach: an attached file's content must reach the model. Uses a relative
 * attach path on purpose so resolveAttachments' cwd resolution is exercised.
 */
async function scenarioAttach(tool) {
  return withSandbox('attach', async cwd => {
    const marker = 'ZCODE-ATTACH-PASS-9K4'
    await writeFile(join(cwd, 'brief.md'), `# 会议纪要\n\n口令：${marker}\n`, 'utf8')
    const result = await tool.execute({
      task: '附件 brief.md 中记录的口令是什么？只回复口令本身。',
      cwd,
      mode: 'guarded',
      attach: ['brief.md'],
      timeout_ms: EXEC_TIMEOUT_MS,
    }, CALL_EXEC())
    const response = responseOf(result)
    const pass = response.includes(marker)
    return {
      pass,
      detail: `ok=${result.ok} exit=${result.exitCode} sessionId=${result.sessionId} response=${truncate(response)}`,
    }
  })
}

/**
 * resume: session continuity across two zcode_run calls. The first call plants
 * a secret and yields a sessionId; the resumed call must recall it.
 */
async function scenarioResume(tool) {
  return withSandbox('resume', async cwd => {
    const secret = '蓝鲸42'
    const first = await tool.execute({
      task: `请记住暗号：${secret}。只回复：收到。不要调用任何工具。`,
      cwd,
      mode: 'guarded',
      timeout_ms: EXEC_TIMEOUT_MS,
    }, CALL_EXEC())
    if (!first.sessionId) {
      return {
        pass: false,
        detail: `first call produced no sessionId: ok=${first.ok} exit=${first.exitCode} stdout=${truncate(first.stdout)}`,
      }
    }
    const second = await tool.execute({
      task: '我们之前的会话里我告诉过你一个暗号。只回复暗号本身。',
      cwd,
      mode: 'guarded',
      resume: first.sessionId,
      timeout_ms: EXEC_TIMEOUT_MS,
    }, CALL_EXEC())
    const response = responseOf(second)
    const pass = response.includes(secret)
    return {
      pass,
      detail: `sessionId=${first.sessionId} secondOk=${second.ok} secondExit=${second.exitCode} response=${truncate(response)}`,
    }
  })
}

async function pgrepMatches(pattern) {
  try {
    const { stdout } = await execFileAsync('pgrep', ['-f', pattern], { timeout: 10_000 })
    return stdout.split(/\r?\n/).map(line => line.trim()).filter(Boolean)
  } catch (error) {
    if (error?.code === 1) return [] // pgrep exits 1 when nothing matched
    throw error
  }
}

/**
 * timeout: a real long task must be killed with its whole process group when
 * timeout_ms expires (SIGTERM → 5 s grace → SIGKILL → 3 s settle). The stderr
 * diagnostic, the wall-clock bound and the absence of orphaned `sleep 300`
 * processes are all asserted (pgrep baseline diff; the prompt string itself
 * contains "sleep 300", so a strict equality diff is required, not a
 * "nothing matches" check).
 */
async function scenarioTimeout(tool) {
  return withSandbox('timeout', async cwd => {
    const pattern = 'sleep 300'
    const before = await pgrepMatches(pattern)
    const result = await tool.execute({
      task: '执行 shell 命令 sleep 300，等命令结束后回复：done',
      cwd,
      mode: 'yolo',
      timeout_ms: 15_000,
    }, CALL_EXEC())
    await new Promise(resolve => setTimeout(resolve, 2_000))
    const after = await pgrepMatches(pattern)
    const orphans = after.filter(pid => !before.includes(pid))
    const stderrMark = result.stderr.includes('timed out after 15000 ms; process group killed')
    const pass = result.timedOut === true
      && result.ok === false
      && stderrMark
      && result.durationMs >= 15_000 && result.durationMs <= 45_000
      && orphans.length === 0
    return {
      pass,
      detail: `timedOut=${result.timedOut} ok=${result.ok} durationMs=${result.durationMs} stderrMark=${stderrMark} orphans=[${orphans.join(',')}] stderr=${truncate(result.stderr, 300)}`,
    }
  })
}

const SCENARIOS = {
  plan: scenarioPlan,
  build: scenarioBuild,
  edit: scenarioEdit,
  yolo: scenarioYolo,
  attach: scenarioAttach,
  resume: scenarioResume,
  timeout: scenarioTimeout,
}

async function main() {
  const options = parseArgs(process.argv.slice(2))
  if (options.help) {
    usage()
    return
  }

  const names = options.only ?? Object.keys(SCENARIOS)
  const unknown = names.filter(name => !SCENARIOS[name])
  if (unknown.length > 0) {
    throw new Error(`unknown scenario(s): ${unknown.join(', ')}; known: ${Object.keys(SCENARIOS).join(', ')}`)
  }

  const tool = makeTool()
  const results = []
  for (const name of names) {
    const started = Date.now()
    let outcome
    try {
      outcome = await SCENARIOS[name](tool)
    } catch (error) {
      outcome = { pass: false, error: String(error?.message ?? error).split('\n')[0] }
    }
    results.push({ scenario: name, ok: outcome.pass === true, ...outcome, durationMs: Date.now() - started })
  }

  const allPass = results.every(result => result.ok)
  if (options.json) {
    console.log(JSON.stringify({ ok: allPass, results }, null, 2))
  } else {
    for (const result of results) {
      const head = `[${result.ok ? 'PASS' : 'FAIL'}] ${result.scenario} (${Math.round(result.durationMs / 1000)}s)`
      console.log(result.error ? `${head}: ${result.error}` : `${head}: ${result.detail ?? ''}`)
    }
    console.log(allPass ? 'Result: PASS' : 'Result: FAIL')
  }
  process.exitCode = allPass ? 0 : 1
}

await main()
