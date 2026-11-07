// Probe inside the kanban root only + screenshot the board.
import { chromium } from '/Users/huweixing/.agents/skills/browser-automation/node_modules/playwright/index.mjs'
const url = process.argv[2]
const out = process.argv[3] || '/tmp/board.png'
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(15000)
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(8000)
  await page.getByText('Board', { exact: true }).first().click({ timeout: 8000 })
  await page.waitForTimeout(4000)
  const info = await page.evaluate(() => {
    const root = document.querySelector('.kanban-root')
    const all = [...document.querySelectorAll('[class*="kanban"]')]
    const btns = root ? [...root.querySelectorAll('button, input, textarea')].map(el => ({
      tag: el.tagName.toLowerCase(),
      text: (el.textContent || '').trim().slice(0, 30),
      aria: el.getAttribute('aria-label') || '',
      ph: el.getAttribute('placeholder') || '',
      cls: (el.className || '').toString().slice(0, 50),
    })) : []
    return { rootPresent: !!root, kanbanElCount: all.length, btns }
  })
  console.log(JSON.stringify(info, null, 1))
  await page.screenshot({ path: out })
  console.log('saved', out)
} catch (e) { console.log('ERR', e.message) } finally { await browser.close() }
