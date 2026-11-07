// Board evidence capture for ticket 226d5178fb80 (kanban-empty-board).
// Drives Playwright directly with explicit timeouts (the DSH GUI holds
// websocket connections, so never wait for networkidle). Usage:
//   node shot-board.mjs <token> <outfile> "<workspace title>" [...more workspace titles]
// Screenshots each workspace's board in sequence into <outbase>-<n>.png
import { chromium } from '/Users/huweixing/.agents/skills/browser-automation/node_modules/playwright/index.mjs'

const [token, outBase, ...workspaces] = process.argv.slice(2)
if (!token || !outBase || workspaces.length === 0) {
  console.log('usage: node shot-board.mjs <token> <outfile-base> "<workspace title>" [...]')
  process.exit(2)
}
const url = `http://127.0.0.1:3082/?token=${token}`
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(20000)
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(8000)
  await page.getByText('Board', { exact: true }).first().click({ timeout: 10000 })
  await page.waitForTimeout(4000)
  let n = 0
  for (const ws of workspaces) {
    await page.locator('.kanban-workspace-trigger').click({ timeout: 10000 })
    await page.waitForTimeout(1500)
    await page.locator('[class*="kanban-workspace-name"]', { hasText: ws }).first().click({ timeout: 10000 })
    await page.waitForTimeout(3500)
    n += 1
    const out = n === 1 ? outBase : outBase.replace(/\.png$/, `-${n}.png`)
    await page.screenshot({ path: out, fullPage: false })
    const cards = await page.locator('.kanban-card').count()
    const emptyCols = await page.locator('.kanban-column-empty').count()
    console.log('saved', out, 'workspace:', ws, 'cards:', cards, 'emptyColumns:', emptyCols)
  }
} catch (e) {
  console.log('ERR', e.message)
  try { await page.screenshot({ path: outBase.replace(/\.png$/, '-err.png') }) } catch {}
  process.exitCode = 1
} finally {
  await browser.close()
}
