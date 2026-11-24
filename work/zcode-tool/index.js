/**
 * @local/zcode-tool — expose the ZCode CLI (Z.ai GLM coding agent) as the
 * `zcode_run` DSH tool.
 *
 * Contract sources (read 2026-11-22):
 * - ZCode CLI: ~/.local/zcode-src/apps/zcode-cli/docs/usage/02-cli-reference.md,
 *   05-permissions.md, 06-sessions.md, 13-automation.md (`--prompt`, `--mode`,
 *   `--output-format json`, `--attach`, `--resume`, exit-code semantics).
 * - DSH tool API: /Users/huweixing/deepseek-harness/docs/cookbook/adding-a-tool.md,
 *   docs/user/develop/basic/{tool,publish}.md, packages/core/tools/src/index.ts
 *   (raw JSON-Schema ToolDefinition, `tools/pre-execute` ask decisions).
 *
 * Safety invariants:
 * - An explicit `--mode` (default `guarded`) is always passed; `zcode --prompt`
 *   defaults to yolo, which is never relied upon.
 * - The child is spawned as its own process group and the group is killed on
 *   timeout or caller abort (SIGTERM, then SIGKILL after a grace period).
 * - Every call asks the DSH approval service before dispatch unless the
 *   deployment explicitly sets `requireApproval: false` (headless profiles).
 */

import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { stat } from 'node:fs/promises'
import { homedir } from 'node:os'
import { delimiter, dirname, isAbsolute, join, resolve } from 'node:path'

export const name = 'zcode-tool'
export const inject = ['tools']

const TOOL_NAME = 'zcode_run'

/** ZCode permission modes accepted by the current CLI (`--mode`). */
const MODES = ['guarded', 'plan', 'build', 'edit', 'yolo']
/** ZCode `--prompt` defaults to yolo; this tool never relies on that default. */
const DEFAULT_MODE = 'guarded'
const DEFAULT_TIMEOUT_MS = 10 * 60 * 1000
const MAX_TIMEOUT_MS = 30 * 60 * 1000
const MAX_TASK_CHARS = 100_000
/** Keep at most this much of each stream in memory (JSON + diagnostics). */
const MAX_CAPTURE_CHARS = 2_000_000
/** Model-facing stdout/stderr cap; longer output is marked as truncated. */
const MAX_RESULT_CHARS = 200_000
const KILL_GRACE_MS = 5_000
const HARD_SETTLE_MS = 3_000

const KNOWN_ARGUMENTS = new Set(['task', 'cwd', 'mode', 'timeout_ms', 'attach', 'resume'])

const TOOL_PARAMETERS = Object.freeze({
  type: 'object',
  properties: {
    task: {
      type: 'string',
      description: 'The prompt/task text to hand to ZCode. Required and non-empty.',
    },
    cwd: {
      type: 'string',
      description: 'Working directory for ZCode. Relative paths resolve against the session working directory. Defaults to the current session working directory.',
    },
    mode: {
      type: 'string',
      enum: MODES,
      default: DEFAULT_MODE,
      description: 'ZCode permission mode. Defaults to "guarded"; "yolo" skips ZCode permission prompts and should be used only for trusted, isolated work.',
    },
    timeout_ms: {
      type: 'integer',
      description: `Wall-clock limit in milliseconds. Default ${DEFAULT_TIMEOUT_MS}; upper bound is deployment-configured (${MAX_TIMEOUT_MS} by default). On expiry the whole ZCode process group is killed.`,
    },
    attach: {
      type: 'array',
      items: { type: 'string' },
      description: 'Local files to attach (passed as repeated --attach). Relative paths resolve against the effective cwd.',
    },
    resume: {
      type: 'string',
      description: 'Resume an existing ZCode session by sessionId (sess_...).',
    },
  },
  required: ['task'],
  additionalProperties: false,
})

const TOOL_OUTPUT_SCHEMA = Object.freeze({
  type: 'object',
  properties: {
    ok: { type: 'boolean' },
    exitCode: { oneOf: [{ type: 'integer' }, { type: 'null' }] },
    sessionId: { oneOf: [{ type: 'string' }, { type: 'null' }] },
    stdout: { type: 'string' },
    stderr: { type: 'string' },
    timedOut: { type: 'boolean' },
    durationMs: { type: 'integer' },
  },
  required: ['ok', 'exitCode', 'sessionId', 'stdout', 'stderr', 'timedOut', 'durationMs'],
  additionalProperties: false,
})

/** Whether a value is a plain object (no array / null / exotic prototype). */
export function isRecord(value) {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const prototype = Object.getPrototypeOf(value)
  return prototype === Object.prototype || prototype === null
}

function positiveInt(value, fallback, min, max) {
  if (!Number.isInteger(value) || value < min) return fallback
  return Math.min(value, max)
}

/** Normalize the deployment config, falling back to safe defaults on bad input. */
export function normalizeConfig(raw) {
  const source = isRecord(raw) ? raw : {}
  const configuredMax = positiveInt(source.maxTimeoutMs, MAX_TIMEOUT_MS, 1_000, 24 * 60 * 60 * 1000)
  const configuredDefault = positiveInt(source.defaultTimeoutMs, DEFAULT_TIMEOUT_MS, 1_000, configuredMax)
  return {
    zcodePath: typeof source.zcodePath === 'string' ? source.zcodePath.trim() : '',
    requireApproval: typeof source.requireApproval === 'boolean' ? source.requireApproval : true,
    defaultTimeoutMs: Math.min(configuredDefault, configuredMax),
    maxTimeoutMs: configuredMax,
  }
}

/** Validate raw model arguments (raw JSON-schema registration does not). */
export function normalizeToolArguments(raw, config) {
  const settings = normalizeConfig(config)
  if (!isRecord(raw)) throw new Error(`${TOOL_NAME}: arguments must be an object`)
  const unknown = Object.keys(raw).filter(key => !KNOWN_ARGUMENTS.has(key))
  if (unknown.length > 0) {
    throw new Error(`${TOOL_NAME}: unknown argument(s): ${unknown.join(', ')}`)
  }

  if (typeof raw.task !== 'string') throw new Error(`${TOOL_NAME}: "task" must be a string`)
  const task = raw.task.trim()
  if (task.length === 0) throw new Error(`${TOOL_NAME}: "task" must not be empty`)
  if (task.length > MAX_TASK_CHARS) {
    throw new Error(`${TOOL_NAME}: "task" exceeds ${MAX_TASK_CHARS} characters`)
  }

  if (raw.cwd !== undefined && typeof raw.cwd !== 'string') {
    throw new Error(`${TOOL_NAME}: "cwd" must be a string`)
  }

  const mode = raw.mode === undefined ? DEFAULT_MODE : raw.mode
  if (typeof mode !== 'string' || !MODES.includes(mode)) {
    throw new Error(`${TOOL_NAME}: "mode" must be one of ${MODES.join('|')}`)
  }

  let timeoutMs = settings.defaultTimeoutMs
  if (raw.timeout_ms !== undefined) {
    if (!Number.isInteger(raw.timeout_ms) || raw.timeout_ms <= 0) {
      throw new Error(`${TOOL_NAME}: "timeout_ms" must be a positive integer`)
    }
    if (raw.timeout_ms > settings.maxTimeoutMs) {
      throw new Error(`${TOOL_NAME}: "timeout_ms" exceeds the configured maximum of ${settings.maxTimeoutMs} ms`)
    }
    timeoutMs = raw.timeout_ms
  }

  let attach = []
  if (raw.attach !== undefined) {
    if (typeof raw.attach === 'string') attach = [raw.attach]
    else if (Array.isArray(raw.attach) && raw.attach.every(item => typeof item === 'string')) attach = raw.attach
    else throw new Error(`${TOOL_NAME}: "attach" must be a string or an array of strings`)
    if (attach.some(item => item.trim().length === 0)) {
      throw new Error(`${TOOL_NAME}: "attach" entries must be non-empty paths`)
    }
    attach = attach.map(item => item.trim())
  }

  let resume
  if (raw.resume !== undefined) {
    if (typeof raw.resume !== 'string' || raw.resume.trim().length === 0) {
      throw new Error(`${TOOL_NAME}: "resume" must be a non-empty sessionId string`)
    }
    resume = raw.resume.trim()
  }

  return { task, cwd: raw.cwd === undefined ? undefined : raw.cwd.trim(), mode, timeoutMs, attach, resume }
}

/** Build the ZCode argv; `--mode` is always explicit. */
export function buildZcodeArgs(input) {
  const { task, cwd, mode = DEFAULT_MODE, attach = [], resume } = input
  if (typeof task !== 'string' || task.length === 0) throw new Error('buildZcodeArgs: task is required')
  if (typeof cwd !== 'string' || !isAbsolute(cwd)) throw new Error('buildZcodeArgs: cwd must be absolute')
  if (!MODES.includes(mode)) throw new Error(`buildZcodeArgs: invalid mode ${mode}`)
  const args = ['--prompt', task, '--cwd', cwd, '--mode', mode, '--output-format', 'json', '--no-color']
  for (const file of attach) args.push('--attach', file)
  if (resume) args.push('--resume', resume)
  return args
}

/** Resolve the ZCode executable: config override, local wrapper, then PATH. */
export function resolveZcodePath(configured) {
  if (typeof configured === 'string' && configured.trim().length > 0) return configured.trim()
  const localWrapper = join(homedir(), '.local', 'bin', 'zcode')
  if (existsSync(localWrapper)) return localWrapper
  return 'zcode'
}

/** Child environment: guarantee the host Node and ~/.local/bin are on PATH. */
export function buildChildEnvironment(baseEnv = process.env) {
  const env = { ...baseEnv }
  const prefix = [dirname(process.execPath), join(homedir(), '.local', 'bin')]
  const path = [prefix.join(delimiter), env.PATH ?? env.Path ?? ''].filter(Boolean).join(delimiter)
  env.PATH = path
  env.NO_COLOR = '1'
  return env
}

/** Resolve and validate the effective working directory. */
export async function resolveCwd(requestedCwd, defaultCwd) {
  const base = typeof defaultCwd === 'string' && defaultCwd.length > 0 ? defaultCwd : process.cwd()
  if (requestedCwd !== undefined && typeof requestedCwd !== 'string') {
    throw new Error(`${TOOL_NAME}: "cwd" must be a string`)
  }
  const directory = requestedCwd && requestedCwd.length > 0
    ? (isAbsolute(requestedCwd) ? requestedCwd : resolve(base, requestedCwd))
    : base
  let info
  try {
    info = await stat(directory)
  } catch (error) {
    throw new Error(`${TOOL_NAME}: cwd does not exist: ${directory}`)
  }
  if (!info.isDirectory()) throw new Error(`${TOOL_NAME}: cwd is not a directory: ${directory}`)
  return directory
}

/** Resolve and validate attachment paths; returns absolute paths. */
export async function resolveAttachments(attach, cwd) {
  const resolved = []
  for (const entry of attach) {
    const file = isAbsolute(entry) ? entry : resolve(cwd, entry)
    let info
    try {
      info = await stat(file)
    } catch (error) {
      throw new Error(`${TOOL_NAME}: attachment does not exist: ${file}`)
    }
    if (!info.isFile()) throw new Error(`${TOOL_NAME}: attachment is not a file: ${file}`)
    resolved.push(file)
  }
  return resolved
}

function collectChunk(chunk, current, maxCaptureChars) {
  const text = typeof chunk === 'string' ? chunk : chunk.toString('utf8')
  const remaining = maxCaptureChars - current.length
  if (remaining <= 0) return { text: current, truncated: true }
  if (text.length <= remaining) return { text: current + text, truncated: false }
  return { text: current + text.slice(0, remaining), truncated: true }
}

function capResultStream(text, truncated) {
  if (text.length <= MAX_RESULT_CHARS && !truncated) return text
  const kept = text.slice(0, MAX_RESULT_CHARS)
  const note = `\n[zcode-tool] output truncated: showing ${kept.length} of ${text.length} captured characters${truncated ? '; more output was discarded' : ''}`
  return kept + note
}

function appendDiagnostic(text, line) {
  return text.length === 0 ? line : `${text}\n${line}`
}

function killProcessGroup(pid, signalName) {
  if (!Number.isInteger(pid) || pid <= 0) return
  if (process.platform === 'win32') {
    try {
      spawn('taskkill', ['/pid', String(pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true })
    } catch {
      // Best effort; the close/error handler still settles the call.
    }
    return
  }
  try {
    process.kill(-pid, signalName)
  } catch {
    try {
      process.kill(pid, signalName)
    } catch {
      // Already gone.
    }
  }
}

/**
 * Run one child to completion, with timeout/abort process-group termination.
 * Exported for tests; `execute` is the only production caller.
 */
export function runProcess(options) {
  const {
    command,
    args,
    cwd,
    timeoutMs,
    signal,
    env = buildChildEnvironment(),
    maxCaptureChars = MAX_CAPTURE_CHARS,
    killGraceMs = KILL_GRACE_MS,
  } = options

  return new Promise(resolvePromise => {
    const startedAt = Date.now()
    let stdout = ''
    let stderr = ''
    let stdoutDiscarded = false
    let stderrDiscarded = false
    let timedOut = false
    let aborted = false
    let settled = false
    let spawnError
    let child
    let timeoutTimer
    let killTimer
    let settleTimer

    const settle = (exitCode, signalName) => {
      if (settled) return
      settled = true
      clearTimeout(timeoutTimer)
      clearTimeout(killTimer)
      clearTimeout(settleTimer)
      if (signal) signal.removeEventListener('abort', onAbort)
      if (timedOut) stderr = appendDiagnostic(stderr, `[zcode-tool] timed out after ${timeoutMs} ms; process group killed`)
      if (aborted) stderr = appendDiagnostic(stderr, '[zcode-tool] cancelled by caller; process group killed')
      if (spawnError) stderr = appendDiagnostic(stderr, `[zcode-tool] failed to start ZCode: ${spawnError.message}`)
      resolvePromise({
        ok: !timedOut && !aborted && !spawnError && exitCode === 0,
        exitCode: typeof exitCode === 'number' ? exitCode : null,
        signal: typeof signalName === 'string' ? signalName : null,
        stdout: capResultStream(stdout, stdoutDiscarded),
        stderr: capResultStream(stderr, stderrDiscarded),
        timedOut,
        aborted,
        durationMs: Date.now() - startedAt,
      })
    }

    const terminate = () => {
      if (!child || settled) return
      killProcessGroup(child.pid, 'SIGTERM')
      killTimer = setTimeout(() => killProcessGroup(child.pid, 'SIGKILL'), killGraceMs)
      // A process that ignores SIGKILL cannot exist, but never let the tool
      // hang on a missing close event.
      settleTimer = setTimeout(() => settle(child.exitCode, child.signalCode), killGraceMs + HARD_SETTLE_MS)
    }

    const onAbort = () => {
      aborted = true
      terminate()
    }

    if (signal?.aborted) {
      aborted = true
      settle(null, null)
      return
    }

    if (Number.isFinite(timeoutMs) && timeoutMs > 0) {
      timeoutTimer = setTimeout(() => {
        timedOut = true
        terminate()
      }, timeoutMs)
    }

    if (signal) signal.addEventListener('abort', onAbort, { once: true })

    try {
      child = spawn(command, args, {
        cwd,
        env,
        stdio: ['ignore', 'pipe', 'pipe'],
        detached: process.platform !== 'win32',
        windowsHide: true,
      })
    } catch (error) {
      spawnError = error
      settle(null, null)
      return
    }

    child.stdout.setEncoding('utf8')
    child.stderr.setEncoding('utf8')
    child.stdout.on('data', chunk => {
      const next = collectChunk(chunk, stdout, maxCaptureChars)
      stdout = next.text
      stdoutDiscarded = stdoutDiscarded || next.truncated
    })
    child.stderr.on('data', chunk => {
      const next = collectChunk(chunk, stderr, maxCaptureChars)
      stderr = next.text
      stderrDiscarded = stderrDiscarded || next.truncated
    })
    child.once('error', error => {
      spawnError = error
      terminate()
      settle(null, null)
    })
    child.once('close', (code, signalName) => settle(code, signalName))
  })
}

/** Parse the last JSON object emitted by ZCode (`--output-format json`). */
export function parseZcodeJson(stdout) {
  const text = typeof stdout === 'string' ? stdout.trim() : ''
  if (text.length === 0) return undefined
  const attempts = [text]
  for (const line of text.split(/\r?\n/).slice(-200).reverse()) {
    const candidate = line.trim()
    if (candidate.startsWith('{')) attempts.push(candidate)
    if (attempts.length >= 50) break
  }
  for (const attempt of attempts) {
    try {
      const parsed = JSON.parse(attempt)
      if (isRecord(parsed)) return parsed
    } catch {
      // Try the next candidate.
    }
  }
  return undefined
}

/** Extract the ZCode sessionId from JSON output, tolerating truncated stdout. */
export function extractSessionId(stdout) {
  const parsed = parseZcodeJson(stdout)
  if (parsed && typeof parsed.sessionId === 'string' && parsed.sessionId.length > 0) {
    return parsed.sessionId
  }
  const match = /"sessionId"\s*:\s*"([^"\\]{1,200})"/.exec(typeof stdout === 'string' ? stdout : '')
  return match ? match[1] : null
}

/** Pure approval decision for `tools/pre-execute`; undefined means "next()". */
export function approvalDecision(config, exec) {
  const settings = normalizeConfig(config)
  if (!settings.requireApproval) return undefined
  if (!isRecord(exec) || exec.name !== TOOL_NAME) return undefined
  const args = isRecord(exec.arguments) ? exec.arguments : {}
  const mode = typeof args.mode === 'string' && MODES.includes(args.mode) ? args.mode : DEFAULT_MODE
  const cwd = typeof args.cwd === 'string' && args.cwd.trim().length > 0 ? args.cwd.trim() : '<session cwd>'
  const task = typeof args.task === 'string' ? args.task.trim() : ''
  const preview = task.length > 160 ? `${task.slice(0, 160)}…` : task
  return {
    kind: 'ask',
    reason: `zcode_run: mode=${mode}, cwd=${cwd}, task=${preview || '<missing>'}`,
    displayReason: {
      en: `Run the ZCode CLI in ${cwd} (permission mode: ${mode})?`,
      'zh-CN': `在 ${cwd} 以 ${mode} 权限模式运行 ZCode CLI？`,
    },
  }
}

/** Resolve the session working directory without hard-depending on the service. */
function defaultWorkingDirectory(ctx, exec) {
  try {
    const service = ctx.get?.('workingDirectory')
    const session = exec?.agent?.session
    if (service && session) {
      const directory = service.get(session)
      if (typeof directory === 'string' && directory.length > 0) return directory
    }
  } catch {
    // Fall through to the host process directory.
  }
  return process.cwd()
}

function renderResult(args, value) {
  const mode = isRecord(args) && typeof args.mode === 'string' ? args.mode : DEFAULT_MODE
  const seconds = typeof value.durationMs === 'number' ? (value.durationMs / 1000).toFixed(1) : '?'
  const header = [
    `[zcode_run] ${value.ok ? 'ok' : 'failed'}`,
    `mode=${mode}`,
    `exit=${value.exitCode === null ? 'null' : value.exitCode}`,
    `${seconds}s`,
    ...(value.timedOut ? ['TIMED OUT'] : []),
    ...(value.sessionId ? [`sessionId=${value.sessionId}`] : []),
  ].join(' · ')
  const lines = [header]
  if (value.stdout.length > 0) lines.push('--- stdout ---', value.stdout)
  if (value.stderr.length > 0) lines.push('--- stderr ---', value.stderr)
  if (value.stdout.length === 0 && value.stderr.length === 0) lines.push('(no output)')
  return [{ type: 'text', text: lines.join('\n') }]
}

/**
 * Register `zcode_run` and the approval gate.
 * @param {object} ctx - Cordis context with the tools service.
 * @param {object} [rawConfig] - deployment config from cordis.patch.yml.
 */
export function apply(ctx, rawConfig) {
  const config = normalizeConfig(rawConfig)

  ctx.tools.register({
    name: TOOL_NAME,
    description: [
      'Run one non-interactive ZCode CLI prompt (Z.ai GLM coding agent) against a working directory.',
      'Use this when a task needs ZCode specifically (its own tools, skills or model), not for ordinary shell work.',
      'Permissions default to ZCode "guarded": dangerous operations still ask ZCode for approval. "yolo" skips those prompts and is only for trusted isolated work.',
      'The call blocks until ZCode exits or timeout_ms expires; on timeout the whole process group is killed.',
      '"ok" means the CLI exited 0, not that the task succeeded — inspect stdout (JSON with sessionId/response) and stderr.',
      'Every call is gated by DSH approval by default; the deployment can set requireApproval=false for headless use.',
    ].join(' '),
    parameters: TOOL_PARAMETERS,
    output: {
      schema: TOOL_OUTPUT_SCHEMA,
      render: renderResult,
    },
    async execute(rawArgs, exec) {
      const args = normalizeToolArguments(rawArgs, config)
      const cwd = await resolveCwd(args.cwd, defaultWorkingDirectory(ctx, exec))
      const attach = await resolveAttachments(args.attach, cwd)
      const argv = buildZcodeArgs({ task: args.task, cwd, mode: args.mode, attach, resume: args.resume })
      const result = await runProcess({
        command: resolveZcodePath(config.zcodePath),
        args: argv,
        cwd,
        timeoutMs: args.timeoutMs,
        signal: exec.signal,
        env: buildChildEnvironment(),
      })
      return {
        ok: result.ok,
        exitCode: result.exitCode,
        sessionId: extractSessionId(result.stdout),
        stdout: result.stdout,
        stderr: result.stderr,
        timedOut: result.timedOut,
        durationMs: result.durationMs,
      }
    },
  })

  ctx.on('tools/pre-execute', async (exec, next) => {
    const decision = approvalDecision(config, exec)
    return decision ?? next()
  })

  ctx.logger?.info?.(
    `[zcode-tool] ${TOOL_NAME} registered (default mode=${DEFAULT_MODE}, approval=${config.requireApproval ? 'ask' : 'off'}, zcode=${resolveZcodePath(config.zcodePath)})`,
  )
}
