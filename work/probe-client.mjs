// Deep probe: what did the client actually load? Sidebar buttons, kanban
// markers in served JS, full screenshot.
import { chromium } from '/Users/huweixing/.agents/skills/browser-automation/node_modules/playwright/index.mjs'
const url = process.argv[2]
const OUT = '/Users/huweixing/src/enable-kanban-937d8cafda22/work'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(15000)
const trace = {}
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(12000)
  trace.title = await page.title()
  trace.bodyHasKanban = await page.evaluate(() => document.body.innerHTML.includes('kanban'))
  trace.sidebarButtons = await page.evaluate(() => [...document.querySelectorAll('button')].map(b => (b.textContent || '').trim()).filter(t => t && t.length < 30).slice(0, 25))
  // which JS assets served, do any mention dsh-kanban?
  trace.assets = await page.evaluate(async () => {
    const srcs = [...document.querySelectorAll('script[src]')].map(s => s.src)
    const out = []
    for (const s of srcs.slice(0, 10)) {
      try { const t = await (await fetch(s)).text(); out.push({ src: s.split('/').pop().slice(0, 40), len: t.length, kanban: t.includes('dsh-kanban') }) } catch { out.push({ src: s.split('/').pop().slice(0, 40), err: true }) }
    }
    return out
  })
  await page.screenshot({ path: `${OUT}/verify-client-state.png` })
  console.log(JSON.stringify(trace, null, 1))
} catch (e) { console.log('ERR', e.message, JSON.stringify(trace)) } finally { await browser.close() }
