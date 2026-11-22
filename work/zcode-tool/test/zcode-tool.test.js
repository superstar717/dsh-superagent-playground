import assert from 'node:assert/strict'
import { chmod, mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { after, test } from 'node:test'

import {
  apply,
  approvalDecision,
  buildChildEnvironment,
  buildZcodeArgs,
  extractSessionId,
  normalizeConfig,
  normalizeToolArguments,
  parseZcodeJson,
  resolveAttachments,
  resolveCwd,
  runProcess,
} from '../index.js'

const root = await mkdtemp(join(tmpdir(), 'zcode-tool-test-'))
after(async () => {
  await rm(root, { recursive: true, force: true })
})

async function fakeZcode(body, fileName = 'fake-zcode.mjs') {
  const file = join(root, fileName)
  await writeFile(file, `#!/usr/bin/env node\n${body}\n`, { mode: 0o755 })
  await chmod(file, 0o755)
  return file
}

function fakeContext() {
  const tools = []
  const listeners = new Map()
  const ctx = {
    tools: {
      register(definition) {
        tools.push(definition)
        return () => {}
      },
    },
    on(event, listener) {
      listeners.set(event, listener)
    },
    logger: { info() {} },
    get() {
      return undefined
    },
  }
  return { ctx, tools, listeners }
}

test('normalizeConfig applies safe defaults and ignores bad types', () => {
  assert.deepEqual(normalizeConfig(undefined), {
    zcodePath: '',
    requireApproval: true,
    defaultTimeoutMs: 600_000,
    maxTimeoutMs: 1_800_000,
  })
  const config = normalizeConfig({
    zcodePath: '  /opt/zcode  ',
    requireApproval: false,
    defaultTimeoutMs: 120_000,
    maxTimeoutMs: 900_000,
  })
  assert.equal(config.zcodePath, '/opt/zcode')
  assert.equal(config.requireApproval, false)
  assert.equal(config.defaultTimeoutMs, 120_000)
  assert.equal(config.maxTimeoutMs, 900_000)
  assert.equal(normalizeConfig({ requireApproval: 'yes', maxTimeoutMs: -1 }).requireApproval, true)
  assert.equal(normalizeConfig({ maxTimeoutMs: 60_000, defaultTimeoutMs: 1_800_000 }).defaultTimeoutMs, 60_000)
})

test('normalizeToolArguments: defaults, explicit values and coercion', () => {
  const args = normalizeToolArguments({ task: 'hello' }, {})
  assert.deepEqual(args, {
    task: 'hello',
    cwd: undefined,
    mode: 'guarded',
    timeoutMs: 600_000,
    attach: [],
    resume: undefined,
  })

  const explicit = normalizeToolArguments({
    task: '  do it  ',
    cwd: ' sub ',
    mode: 'plan',
    timeout_ms: 1_000,
    attach: 'a.txt',
    resume: ' sess_1 ',
  }, {})
  assert.equal(explicit.task, 'do it')
  assert.equal(explicit.cwd, 'sub')
  assert.equal(explicit.mode, 'plan')
  assert.equal(explicit.timeoutMs, 1_000)
  assert.deepEqual(explicit.attach, ['a.txt'])
  assert.equal(explicit.resume, 'sess_1')

  assert.deepEqual(
    normalizeToolArguments({ task: 'x', attach: ['a', 'b'] }, {}).attach,
    ['a', 'b'],
  )
})

test('normalizeToolArguments rejects invalid input', () => {
  const bad = [
    [null, /arguments must be an object/],
    [{}, /"task" must be a string/],
    [{ task: '   ' }, /must not be empty/],
    [{ task: 'x', unknown: 1 }, /unknown argument/],
    [{ task: 'x', mode: 'auto' }, /"mode" must be one of/],
    [{ task: 'x', timeout_ms: 0 }, /positive integer/],
    [{ task: 'x', timeout_ms: 1.5 }, /positive integer/],
    [{ task: 'x', timeout_ms: 9_999_999 }, /configured maximum/],
    [{ task: 'x', attach: [1] }, /"attach" must be a string or an array/],
    [{ task: 'x', attach: [''] }, /entries must be non-empty/],
    [{ task: 'x', resume: '  ' }, /"resume" must be a non-empty/],
    [{ task: 'x', cwd: 7 }, /"cwd" must be a string/],
  ]
  for (const [input, pattern] of bad) {
    assert.throws(() => normalizeToolArguments(input, {}), pattern)
  }
  assert.throws(
    () => normalizeToolArguments({ task: 'x', timeout_ms: 1_500 }, { maxTimeoutMs: 1_000 }),
    /configured maximum of 1000/,
  )
  assert.throws(() => normalizeToolArguments({ task: 'x'.repeat(100_001) }, {}), /exceeds 100000/)
})

test('buildZcodeArgs always passes an explicit mode', () => {
  const args = buildZcodeArgs({
    task: 'do the thing',
    cwd: '/tmp/work',
    mode: 'guarded',
    attach: ['/tmp/a.txt', '/tmp/b.txt'],
    resume: 'sess_1',
  })
  assert.deepEqual(args, [
    '--prompt', 'do the thing',
    '--cwd', '/tmp/work',
    '--mode', 'guarded',
    '--output-format', 'json',
    '--no-color',
    '--attach', '/tmp/a.txt',
    '--attach', '/tmp/b.txt',
    '--resume', 'sess_1',
  ])
  assert.throws(() => buildZcodeArgs({ task: 'x', cwd: 'relative', mode: 'guarded' }), /cwd must be absolute/)
  assert.throws(() => buildZcodeArgs({ task: 'x', cwd: '/tmp', mode: 'auto' }), /invalid mode/)
})

test('parseZcodeJson reads clean, noisy and pretty-printed output', () => {
  assert.deepEqual(parseZcodeJson('{"sessionId":"sess_a","response":"ok"}'), {
    sessionId: 'sess_a',
    response: 'ok',
  })
  assert.deepEqual(parseZcodeJson('warming up\n{"sessionId":"sess_b"}\n'), { sessionId: 'sess_b' })
  assert.deepEqual(
    parseZcodeJson('{\n  "sessionId": "sess_c",\n  "response": "ok"\n}\n'),
    { sessionId: 'sess_c', response: 'ok' },
  )
  assert.equal(parseZcodeJson('not json at all'), undefined)
  assert.equal(parseZcodeJson(''), undefined)
})

test('extractSessionId tolerates truncated JSON and reports null when absent', () => {
  assert.equal(extractSessionId('{"sessionId":"sess_d","response":"ok"}'), 'sess_d')
  assert.equal(extractSessionId('{"sessionId":"sess_e","response":"a very long truncated'), 'sess_e')
  assert.equal(extractSessionId('{"response":"no session here"}'), null)
  assert.equal(extractSessionId(''), null)
})

test('approvalDecision is an ask by default and can be disabled', () => {
  const exec = {
    name: 'zcode_run',
    arguments: { task: 'fix the build', mode: 'plan', cwd: '/tmp/work' },
  }
  const decision = approvalDecision({}, exec)
  assert.equal(decision.kind, 'ask')
  assert.match(decision.reason, /mode=plan/)
  assert.match(decision.reason, /cwd=\/tmp\/work/)
  assert.match(decision.reason, /fix the build/)
  assert.equal(decision.displayReason.en.includes('/tmp/work'), true)
  assert.equal(decision.displayReason['zh-CN'].includes('plan'), true)

  assert.equal(approvalDecision({ requireApproval: false }, exec), undefined)
  assert.equal(approvalDecision({}, { name: 'bash', arguments: {} }), undefined)
  assert.equal(approvalDecision({}, null), undefined)

  const longTask = approvalDecision({}, { name: 'zcode_run', arguments: { task: 'x'.repeat(300) } })
  assert.equal(longTask.reason.endsWith('…'), true)
})

test('resolveCwd resolves relative paths and validates directories', async () => {
  const base = join(root, 'cwd-base')
  await mkdir(join(base, 'sub'), { recursive: true })
  assert.equal(await resolveCwd(undefined, base), base)
  assert.equal(await resolveCwd('sub', base), join(base, 'sub'))
  assert.equal(await resolveCwd(join(base, 'sub'), base), join(base, 'sub'))
  await assert.rejects(() => resolveCwd('missing', base), /cwd does not exist/)
  await writeFile(join(base, 'file.txt'), 'x')
  await assert.rejects(() => resolveCwd('file.txt', base), /not a directory/)
})

test('resolveAttachments resolves relative paths and rejects missing/dir entries', async () => {
  const attachDir = join(root, 'attach')
  await mkdir(attachDir, { recursive: true })
  await writeFile(join(attachDir, 'a.txt'), 'x')
  assert.deepEqual(await resolveAttachments(['a.txt'], attachDir), [join(attachDir, 'a.txt')])
  assert.deepEqual(await resolveAttachments([join(attachDir, 'a.txt')], attachDir), [join(attachDir, 'a.txt')])
  await assert.rejects(() => resolveAttachments(['missing.txt'], attachDir), /attachment does not exist/)
  await assert.rejects(() => resolveAttachments(['.'], attachDir), /not a file/)
})

test('buildChildEnvironment guarantees the host Node directory on PATH', () => {
  const env = buildChildEnvironment({ PATH: '/usr/bin' })
  assert.equal(env.PATH.startsWith(dirname(process.execPath)), true)
  assert.equal(env.PATH.includes('/usr/bin'), true)
  assert.equal(env.NO_COLOR, '1')
})

test('runProcess returns a structured success result', async () => {
  const result = await runProcess({
    command: process.execPath,
    args: ['-e', 'console.log(JSON.stringify({sessionId:"sess_proc"}))'],
    cwd: root,
    timeoutMs: 5_000,
  })
  assert.equal(result.ok, true)
  assert.equal(result.exitCode, 0)
  assert.equal(result.timedOut, false)
  assert.deepEqual(parseZcodeJson(result.stdout), { sessionId: 'sess_proc' })
})

test('runProcess reports nonzero exits without throwing', async () => {
  const result = await runProcess({
    command: process.execPath,
    args: ['-e', 'process.stderr.write("boom\\n"); process.exit(2)'],
    cwd: root,
    timeoutMs: 5_000,
  })
  assert.equal(result.ok, false)
  assert.equal(result.exitCode, 2)
  assert.match(result.stderr, /boom/)
})

test('runProcess kills the process group on timeout', async () => {
  const started = Date.now()
  const result = await runProcess({
    command: process.execPath,
    args: ['-e', 'setInterval(() => {}, 1000)'],
    cwd: root,
    timeoutMs: 200,
  })
  const elapsed = Date.now() - started
  assert.equal(result.timedOut, true)
  assert.equal(result.ok, false)
  assert.equal(result.exitCode, null)
  assert.match(result.stderr, /timed out after 200 ms/)
  assert.ok(elapsed < 5_000, `timeout kill took too long: ${elapsed} ms`)
})

test('runProcess honours caller aborts', async () => {
  const controller = new AbortController()
  const pending = runProcess({
    command: process.execPath,
    args: ['-e', 'setInterval(() => {}, 1000)'],
    cwd: root,
    timeoutMs: 30_000,
    signal: controller.signal,
  })
  setTimeout(() => controller.abort(), 100)
  const result = await pending
  assert.equal(result.aborted, true)
  assert.equal(result.ok, false)
  assert.match(result.stderr, /cancelled by caller/)
})

test('runProcess reports spawn failures in the structured result', async () => {
  const result = await runProcess({
    command: join(root, 'definitely-missing-zcode'),
    args: [],
    cwd: root,
    timeoutMs: 1_000,
  })
  assert.equal(result.ok, false)
  assert.equal(result.exitCode, null)
  assert.match(result.stderr, /failed to start ZCode/)
})

test('apply registers the tool and the approval gate', () => {
  const { ctx, tools, listeners } = fakeContext()
  apply(ctx, {})
  assert.equal(tools.length, 1)
  const tool = tools[0]
  assert.equal(tool.name, 'zcode_run')
  assert.equal(typeof tool.execute, 'function')
  assert.deepEqual(tool.parameters.required, ['task'])
  assert.equal(tool.parameters.additionalProperties, false)
  assert.equal(tool.parameters.properties.mode.enum.includes('guarded'), true)
  assert.equal(tool.output.schema.properties.sessionId.oneOf[1].type, 'null')
  assert.equal(typeof tool.output.render, 'function')
  assert.equal(listeners.has('tools/pre-execute'), true)
})

test('apply gate asks for zcode_run and passes through other tools', async () => {
  const { ctx, listeners } = fakeContext()
  apply(ctx, {})
  const gate = listeners.get('tools/pre-execute')

  let nextCalled = false
  const decision = await gate(
    { name: 'zcode_run', arguments: { task: 'run', mode: 'guarded', cwd: '/tmp' } },
    async () => {
      nextCalled = true
      return { kind: 'allow' }
    },
  )
  assert.equal(decision.kind, 'ask')
  assert.equal(nextCalled, false)

  const passthrough = await gate({ name: 'bash', arguments: {} }, async () => ({ kind: 'allow' }))
  assert.deepEqual(passthrough, { kind: 'allow' })
})

test('apply with requireApproval=false leaves the gate open', async () => {
  const { ctx, listeners } = fakeContext()
  apply(ctx, { requireApproval: false })
  const gate = listeners.get('tools/pre-execute')
  let nextCalled = false
  const decision = await gate({ name: 'zcode_run', arguments: { task: 'run' } }, async () => {
    nextCalled = true
    return { kind: 'allow' }
  })
  assert.deepEqual(decision, { kind: 'allow' })
  assert.equal(nextCalled, true)
})

test('execute end-to-end with a fake ZCode binary', async () => {
  const script = await fakeZcode(
    'console.log(JSON.stringify({ sessionId: "sess_fake_1", response: "OK", argv: process.argv.slice(2) }))',
    'ok-zcode.mjs',
  )
  const { ctx, tools } = fakeContext()
  apply(ctx, { zcodePath: script, requireApproval: false })
  const tool = tools[0]
  const result = await tool.execute(
    { task: 'say OK', cwd: join(root, 'cwd-base'), mode: 'guarded' },
    { signal: new AbortController().signal, agent: undefined },
  )
  assert.equal(result.ok, true)
  assert.equal(result.exitCode, 0)
  assert.equal(result.sessionId, 'sess_fake_1')
  assert.equal(result.timedOut, false)
  const parsed = JSON.parse(result.stdout)
  assert.deepEqual(parsed.argv.slice(0, 8), [
    '--prompt', 'say OK', '--cwd', join(root, 'cwd-base'), '--mode', 'guarded', '--output-format', 'json',
  ])
})

test('execute surfaces nonzero exits and rejects invalid arguments before spawning', async () => {
  const failing = await fakeZcode('process.stderr.write("nope\\n"); process.exit(7)', 'fail-zcode.mjs')
  const { ctx, tools } = fakeContext()
  apply(ctx, { zcodePath: failing, requireApproval: false })
  const tool = tools[0]
  const result = await tool.execute(
    { task: 'fail', cwd: root },
    { signal: new AbortController().signal, agent: undefined },
  )
  assert.equal(result.ok, false)
  assert.equal(result.exitCode, 7)
  assert.equal(result.sessionId, null)
  assert.match(result.stderr, /nope/)

  await assert.rejects(
    () => tool.execute({ task: '' }, { signal: new AbortController().signal, agent: undefined }),
    /"task" must not be empty/,
  )
})
