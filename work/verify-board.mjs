// Post-restart board verification: render, card persistence, workspace list.
import { chromium } from '/Users/huweixing/.agents/skills/browser-automation/node_modules/playwright/index.mjs'
const url = process.argv[2]
const OUT = '/Users/huweixing/src/enable-kanban-937d8cafda22/work'
const TITLE = '启用看板插件，让工单进度可见'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(15000)
const trace = {}
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(9000)
  await page.getByText('Board', { exact: true }).first().click({ timeout: 8000 })
  await page.waitForTimeout(4000)
  trace.boardRoot = await page.evaluate(() => !!document.querySelector('.kanban-root'))
  trace.ourCardVisible = (await page.getByText(TITLE).count()) > 0
  // what does the workspace selector offer?
  trace.workspaces = await page.evaluate(() => {
    const root = document.querySelector('.kanban-root')
    if (!root) return []
    const btn = root.querySelector('.kanban-workspace-trigger')
    return btn ? [btn.textContent.trim()] : []
  })
  // switch to another workspace (first menu item that differs) and see emptiness
  await page.locator('.kanban-workspace-trigger').click({ timeout: 8000 })
  await page.waitForTimeout(1200)
  const items = await page.evaluate(() => [...document.querySelectorAll('[class*="kanban-workspace-name"]')].map(e => e.textContent.trim()))
  trace.menuWorkspaces = items.slice(0, 12)
  const other = items.find(t => t !== 'enable-kanban-937d8cafda22')
  if (other) {
    await page.getByText(other, { exact: true }).first().click()
    await page.waitForTimeout(3000)
    trace.otherWorkspace = other
    trace.otherBoardEmpty = (await page.getByText('No cards', { exact: true }).count()) > 0
    await page.screenshot({ path: `${OUT}/verify-other-workspace-empty.png` })
    // switch back to our workspace for the final proof shot
    await page.locator('.kanban-workspace-trigger').click({ timeout: 8000 })
    await page.waitForTimeout(1200)
    await page.getByText('enable-kanban-937d8cafda22', { exact: true }).first().click()
    await page.waitForTimeout(3000)
  }
  trace.ourCardVisibleBack = (await page.getByText(TITLE).count()) > 0
  await page.screenshot({ path: `${OUT}/verify-post-restart-board.png` })
  console.log(JSON.stringify(trace, null, 1))
} catch (e) { console.log('ERR', e.message, JSON.stringify(trace)) } finally { await browser.close() }
