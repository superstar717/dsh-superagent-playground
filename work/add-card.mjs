// E2E v2: add a real card via the portaled dialog, then reload to confirm persistence.
import { chromium } from '/Users/huweixing/.agents/skills/browser-automation/node_modules/playwright/index.mjs'
const url = process.argv[2]
const OUT = '/Users/huweixing/src/enable-kanban-937d8cafda22/work'
const TITLE = '启用看板插件，让工单进度可见'
const NOTE = '工单 937d8cafda22：@alpacachen/dsh-kanban 1.11.0 已部署到 superagent profile 并重启生效。来源、备份与回滚见工单 PR。'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(15000)
const trace = {}
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(8000)
  await page.getByText('Board', { exact: true }).first().click({ timeout: 8000 })
  await page.waitForTimeout(4000)
  await page.getByText('Add card', { exact: true }).nth(1).click({ timeout: 8000 })
  await page.waitForTimeout(2000)
  const dlg = page.locator('[role="dialog"]')
  await dlg.getByPlaceholder('Card title').fill(TITLE)
  await dlg.locator('textarea').first().fill(NOTE)
  await page.screenshot({ path: `${OUT}/after-card-dialog.png` })
  await dlg.getByText('Save', { exact: true }).click({ timeout: 8000 })
  await page.waitForTimeout(2500)
  trace.cardVisibleAfterSave = (await page.getByText(TITLE).count()) > 0
  await page.screenshot({ path: `${OUT}/after-card-created.png` })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await page.waitForTimeout(8000)
  await page.getByText('Board', { exact: true }).first().click({ timeout: 8000 })
  await page.waitForTimeout(4000)
  trace.cardVisibleAfterReload = (await page.getByText(TITLE).count()) > 0
  trace.notePreviewAfterReload = (await page.getByText('已部署到 superagent profile', { exact: false }).count()) > 0
  await page.screenshot({ path: `${OUT}/after-card-persisted.png` })
  console.log(JSON.stringify(trace, null, 1))
} catch (e) { console.log('ERR', e.message, JSON.stringify(trace)) } finally { await browser.close() }
