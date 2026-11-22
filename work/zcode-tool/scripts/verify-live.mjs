#!/usr/bin/env node
/**
 * Verify that @local/zcode-tool is usable.
 *
 * Default (zero cost):
 *   1. local contract self-check (default mode, explicit --mode, approval ask);
 *   2. live DSH host registration via the host inspector: reads the Cordis root
 *      Context in the Host realm and checks `tools.schemas()` contains zcode_run.
 *
 * `--real` additionally runs one tiny real ZCode prompt through the plugin's
 * execute path. This consumes Z.ai coding-plan quota (~66k input tokens for a
 * one-line task) and needs `zcode login` to be valid.
 *
 * Usage:
 *   node scripts/verify-live.mjs [--real] [--json] [--inspector-port 9230]
 *   ZCODE_TOOL_ZCODE=/path/to/fake node scripts/verify-live.mjs --real  # test the verifier itself
 */

import { mkdtemp, readFile, rm } from 'node:fs/promises'
import { homedir, tmpdir } from 'node:os'
import { join } from 'node:path'

import {
  apply,
  buildZcodeArgs,
  normalizeToolArguments,
  parseZcodeJson,
} from '../index.js'

const LOG_PATH = join(homedir(), '.dsh', 'state', 'dsh-superagent-restart.log')
const DEFAULT_INSPECTOR_PORT = 9230
const CDP_TIMEOUT_MS = 10_000

const LIVE_PROBE = `(() => {
  const table = globalThis[Symbol.for('dsh.inspector.realm-object-registries')]
  if (!(table instanceof Map)) return { error: 'no inspector object registry' }
  let best
  for (const registry of table.values()) {
    const retained = registry.retained
    if (!(retained instanceof Map)) continue
    for (const value of retained.values()) {
      let tools
      try {
        if (!value || typeof value !== 'object' || typeof value.get !== 'function') continue
        tools = value.get('tools')
      } catch { continue }
      if (!tools || typeof tools.schemas !== 'function') continue
      let schemas
      try { schemas = tools.schemas() } catch { continue }
      if (!Array.isArray(schemas) || schemas.length === 0) continue
      if (!best || schemas.length > best.schemas.length) best = { schemas }
    }
  }
  if (!best) return { error: 'no tools registry found in the inspector Object table' }
  const names = best.schemas.map((schema) => schema.name)
  const schema = best.schemas.find((candidate) => candidate.name === 'zcode_run')
  return {
    toolCount: names.length,
    hasZcode: names.includes('zcode_run'),
    parameters: schema ? Object.keys(schema.parameters?.properties ?? {}) : [],
    modeDefault: schema?.parameters?.properties?.mode?.default ?? null,
  }
})()`

function usage() {
  console.log(`Usage: node scripts/verify-live.mjs [--real] [--json] [--inspector-port <port>]

  (default)  zero-cost: local contract + live host registration check
  --real     also run one real ZCode task (consumes Z.ai quota)
  --json     print the machine-readable result
  --inspector-port <port>  override the host inspector port (default: read from
                           ~/.dsh/state/dsh-superagent-restart.log, else ${DEFAULT_INSPECTOR_PORT})`)
}

function parseArgs(argv) {
  const options = { real: false, json: false, inspectorPort: undefined }
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--real') options.real = true
    else if (arg === '--json') options.json = true
    else if (arg === '--help' || arg === '-h') options.help = true
    else if (arg === '--inspector-port') {
      options.inspectorPort = Number(argv[index + 1])
      index += 1
    } else throw new Error(`unknown argument: ${arg}`)
  }
  return options
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function waitFor(probe, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const value = probe()
    if (value !== undefined) return value
    await sleep(50)
  }
  return undefined
}

async function discoverInspectorPort() {
  try {
    const log = await readFile(LOG_PATH, 'utf8')
    const matches = [...log.matchAll(/dsh inspector: .*?ws=127\.0\.0\.1:(\d+)\/devtools\/page\//g)]
    if (matches.length > 0) return Number(matches.at(-1)[1])
  } catch {
    // Fall back to the default port below.
  }
  return DEFAULT_INSPECTOR_PORT
}

async function fetchJson(url) {
  const response = await fetch(url, { signal: AbortSignal.timeout(5_000) })
  if (!response.ok) throw new Error(`${url} returned HTTP ${response.status}`)
  return response.json()
}

async function probeLiveRegistration(port) {
  const targets = await fetchJson(`http://127.0.0.1:${port}/json`)
  const target = Array.isArray(targets) ? targets[0] : undefined
  if (!target?.webSocketDebuggerUrl) throw new Error('inspector returned no CDP target')

  const socket = new WebSocket(target.webSocketDebuggerUrl)
  const messages = []
  socket.onmessage = event => messages.push(JSON.parse(event.data))
  await new Promise((resolve, reject) => {
    socket.onopen = resolve
    socket.onerror = () => reject(new Error('could not connect to the inspector CDP socket'))
  })

  try {
    socket.send(JSON.stringify({ id: 1, method: 'Runtime.enable', params: {} }))
    await sleep(300)
    socket.send(JSON.stringify({
      id: 2,
      method: 'Runtime.evaluate',
      params: { expression: LIVE_PROBE, returnByValue: true },
    }))
    const reply = await waitFor(() => messages.find(message => message.id === 2), CDP_TIMEOUT_MS)
    if (reply === undefined) throw new Error('inspector Runtime.evaluate timed out')
    if (reply.result?.exceptionDetails) {
      throw new Error(`inspector evaluate failed: ${reply.result.exceptionDetails.text ?? 'unknown error'}`)
    }
    const value = reply.result?.result?.value
    if (value === undefined) throw new Error('inspector evaluate returned no value')
    if (value.error) throw new Error(value.error)
    return value
  } finally {
    socket.close()
  }
}

async function localChecks() {
  const normalized = normalizeToolArguments({ task: 'probe' }, {})
  if (normalized.mode !== 'guarded') throw new Error(`default mode is ${normalized.mode}, expected guarded`)
  const argv = buildZcodeArgs({ task: 'probe', cwd: '/tmp', mode: normalized.mode })
  if (!argv.includes('--mode') || argv[argv.indexOf('--mode') + 1] !== 'guarded') {
    throw new Error('buildZcodeArgs did not pass an explicit --mode guarded')
  }

  const tools = []
  const listeners = new Map()
  const fakeContext = {
    tools: { register(definition) { tools.push(definition) } },
    on(event, listener) { listeners.set(event, listener) },
    logger: { info() {} },
    get() { return undefined },
  }
  apply(fakeContext, {})
  if (tools[0]?.name !== 'zcode_run') throw new Error('apply() did not register zcode_run')
  const gate = listeners.get('tools/pre-execute')
  if (typeof gate !== 'function') throw new Error('apply() did not register tools/pre-execute')
  const decision = await gate(
    { name: 'zcode_run', arguments: { task: 'probe' } },
    async () => ({ kind: 'allow' }),
  )
  if (decision?.kind !== 'ask') throw new Error('approval gate did not default to ask')
  return { defaultMode: normalized.mode, parameters: Object.keys(tools[0].parameters.properties) }
}

async function realCheck() {
  const cwd = await mkdtemp(join(tmpdir(), 'zcode-tool-verify-'))
  try {
    const tools = []
    const fakeContext = {
      tools: { register(definition) { tools.push(definition) } },
      on() {},
      logger: { info() {} },
      get() { return undefined },
    }
    apply(fakeContext, {
      requireApproval: false,
      ...(process.env.ZCODE_TOOL_ZCODE ? { zcodePath: process.env.ZCODE_TOOL_ZCODE } : {}),
    })
    const started = Date.now()
    const result = await tools[0].execute(
      {
        task: process.env.ZCODE_TOOL_TASK || '只回复两个字：正常。不要调用任何工具。',
        cwd,
        mode: 'guarded',
        timeout_ms: 180_000,
      },
      { signal: new AbortController().signal, agent: undefined },
    )
    const parsed = parseZcodeJson(result.stdout)
    return {
      ok: result.ok,
      exitCode: result.exitCode,
      sessionId: result.sessionId,
      response: parsed && typeof parsed.response === 'string' ? parsed.response : undefined,
      timedOut: result.timedOut,
      durationMs: Date.now() - started,
    }
  } finally {
    await rm(cwd, { recursive: true, force: true })
  }
}

async function main() {
  const options = parseArgs(process.argv.slice(2))
  if (options.help) {
    usage()
    return
  }

  const result = { steps: [], ok: false }
  const fail = (step, error) => {
    result.steps.push({ step, ok: false, error: String(error?.message ?? error) })
    throw error
  }

  try {
    const local = await localChecks().catch(error => fail('local-contract', error))
    result.steps.push({ step: 'local-contract', ok: true, ...local })

    const port = options.inspectorPort ?? await discoverInspectorPort()
    let live
    try {
      live = await probeLiveRegistration(port)
      if (!live.hasZcode) throw new Error(`zcode_run not registered in the live host (${live.toolCount} tools)`)
    } catch (error) {
      fail('live-registration', new Error(`${error.message} (inspector port ${port})`))
    }
    result.steps.push({ step: 'live-registration', ok: true, inspectorPort: port, ...live })

    if (options.real) {
      const real = await realCheck().catch(error => fail('real-zcode', error))
      if (!real.ok || !real.sessionId) {
        throw new Error(`real ZCode task failed: ok=${real.ok}, exit=${real.exitCode}, sessionId=${real.sessionId}`)
      }
      result.steps.push({ step: 'real-zcode', ok: true, ...real })
    }
    result.ok = true
  } catch (error) {
    result.error = String(error?.message ?? error)
  }

  if (options.json) {
    console.log(JSON.stringify(result, null, 2))
  } else {
    for (const step of result.steps) {
      if (!step.ok) {
        console.log(`[FAIL] ${step.step}: ${step.error}`)
        continue
      }
      if (step.step === 'local-contract') {
        console.log(`[PASS] local contract: default mode=${step.defaultMode}, params=${step.parameters.join(',')}, approval=ask`)
      } else if (step.step === 'live-registration') {
        console.log(`[PASS] live host registration (inspector ${step.inspectorPort}): ${step.toolCount} tools, zcode_run found, params=${step.parameters.join(',')}, mode default=${step.modeDefault}`)
      } else if (step.step === 'real-zcode') {
        console.log(`[PASS] real ZCode: exit=${step.exitCode}, sessionId=${step.sessionId}, response=${JSON.stringify(step.response)}, ${step.durationMs} ms`)
      }
    }
    if (result.error && !result.steps.some(step => !step.ok)) console.log(`[FAIL] ${result.error}`)
    if (result.ok) {
      console.log(options.real
        ? 'Result: PASS (plugin is live and real ZCode execution works)'
        : 'Result: PASS (plugin is loaded in the live host; add --real to exercise ZCode, and approve the first GUI call to verify the approval click path)')
    } else {
      console.log('Result: FAIL')
    }
  }

  process.exitCode = result.ok ? 0 : 1
}

await main()
