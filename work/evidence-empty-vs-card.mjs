// Evidence: empty board in the default (new) workspace vs populated board in
// the enable-kanban workspace.
import { chromium } from '/Users/huweixing/.agents/skills/browser-automation/node_modules/playwright/index.mjs'
const url = process.argv[2]
const OUT = '/Users/huweixing/src/enable-kanban-937d8cafda22/work'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(20000)
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(9000)
  await page.getByText('Board', { exact: true }).first().click({ timeout: 10000 })
  await page.waitForTimeout(5000)
  await page.screenshot({ path: `${OUT}/empty-board-default-workspace.png` })
  // switch to the enable-kanban workspace via the menu (force: overlay intercepts)
  await page.locator('.kanban-workspace-trigger').click()
  await page.waitForTimeout(1500)
  await page.locator('.kanban-workspace-name', { hasText: 'enable-kanban-937d8cafda22' }).first().click({ force: true })
  await page.waitForTimeout(5000)
  const card = await page.getByText('启用看板插件，让工单进度可见').count()
  console.log(JSON.stringify({ defaultWorkspaceShot: true, ourCardVisibleAfterSwitch: card > 0 }))
  await page.screenshot({ path: `${OUT}/board-with-card-enable-kanban.png` })
} catch (e) { console.log('ERR', e.message) } finally { await browser.close() }
