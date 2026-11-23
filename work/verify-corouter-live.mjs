#!/usr/bin/env node
/**
 * Live probe: is dsh-opendesign-corouter loaded in the running dsh host?
 *
 * Connects to the host inspector CDP endpoint (default 127.0.0.1:9230),
 * evaluates in the Host realm, walks the inspector object registries to the
 * Cordis root context, calls `llm.listProviders()` and
 * `llm.listConfigurableProviders()`, and reports whether the
 * opendesign-corouter-plan / opendesign-corouter-paid providers are present.
 *
 * Zero side effects: no model calls, no credential access, no config writes.
 * Pattern reused from ~/.dsh/plugins/zcode-tool/scripts/verify-live.mjs
 * (inspector realm-object-registries probe, 2026-11-22).
 *
 * Usage: node work/verify-corouter-live.mjs [--json] [--inspector-port 9230]
 *
 * 2026-11-23 verified output (superagent profile, host pid 58210):
 *   providers include
 *     opendesign-corouter-plan "OpenDesign CoRouter · 套餐赠送"
 *     opendesign-corouter-paid "OpenDesign CoRouter · 付费模型"
 *   configurable entries carry settingsNs llm-opendesign-corouter,
 *   defaultBaseURL https://amr-link.open-design.ai/v1, nativeAuth.oauth true.
 */

const CDP_TIMEOUT_MS = 10_000

const PROBE = `(() => {
  const table = globalThis[Symbol.for('dsh.inspector.realm-object-registries')]
  if (!(table instanceof Map)) return { error: 'no inspector object registry' }
  let best
  for (const registry of table.values()) {
    const retained = registry.retained
    if (!(retained instanceof Map)) continue
    for (const value of retained.values()) {
      let llm
      try {
        if (!value || typeof value !== 'object' || typeof value.get !== 'function') continue
        llm = value.get('llm')
      } catch { continue }
      if (llm && typeof llm.listProviders === 'function') { best = llm; break }
    }
    if (best) break
  }
  if (!best) return { error: 'no llm service found in the inspector Object table' }
  const call = (fn) => { try { return fn() } catch (e) { return { __error: String(e).slice(0, 200) } } }
  const providers = call(() => best.listProviders())
  const configurable = call(() => best.listConfigurableProviders?.())
  const pick = (list, re) => (Array.isArray(list) ? list : []).filter(e => re.test(String(e?.id ?? e?.provider ?? '')))
  const planP = pick(providers, /opendesign-corouter-plan/)
  const paidP = pick(providers, /opendesign-corouter-paid/)
  const planC = pick(configurable, /opendesign-corouter-plan/)
  const paidC = pick(configurable, /opendesign-corouter-paid/)
  return {
    providerCount: Array.isArray(providers) ? providers.length : null,
    plan: { provider: planP[0] ?? null, configurable: planC[0] ?? null },
    paid: { provider: paidP[0] ?? null, configurable: paidC[0] ?? null },
    hasPlan: planP.length > 0,
    hasPaid: paidP.length > 0,
  }
})()`

function sleep(ms) { return new Promise(r => setTimeout(r, ms)) }

async function waitFor(probe, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const value = probe()
    if (value !== undefined) return value
    await sleep(50)
  }
  return undefined
}

async function main() {
  const json = process.argv.includes('--json')
  const portArgIdx = process.argv.indexOf('--inspector-port')
  const port = portArgIdx > -1 ? Number(process.argv[portArgIdx + 1]) : 9230

  const targets = await (await fetch(`http://127.0.0.1:${port}/json`, { signal: AbortSignal.timeout(5000) })).json()
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
      params: { expression: PROBE, returnByValue: true },
    }))
    const reply = await waitFor(() => messages.find(m => m.id === 2), CDP_TIMEOUT_MS)
    if (reply === undefined) throw new Error('inspector Runtime.evaluate timed out')
    if (reply.result?.exceptionDetails) {
      throw new Error(`inspector evaluate failed: ${reply.result.exceptionDetails.text ?? 'unknown error'} ${JSON.stringify(reply.result.exceptionDetails).slice(0, 300)}`)
    }
    const value = reply.result?.result?.value
    if (value === undefined) throw new Error('inspector evaluate returned no value')
    if (value.error) throw new Error(value.error)
    const ok = value.hasPlan && value.hasPaid
    if (json) {
      console.log(JSON.stringify(value, null, 2))
    } else {
      console.log(`providers on host: ${value.providerCount}`)
      for (const key of ['plan', 'paid']) {
        const e = value[key]
        console.log(`${key}: provider=${JSON.stringify(e.provider)} configurable=${JSON.stringify(e.configurable)}`)
      }
      console.log(`${ok ? 'PASS' : 'FAIL'}: plan=${value.hasPlan} paid=${value.hasPaid}`)
    }
    process.exitCode = ok ? 0 : 1
  } finally {
    socket.close()
  }
}

main().catch(err => {
  console.error('PROBE ERROR:', err.message)
  process.exit(2)
})
