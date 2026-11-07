// Probe the Board view structure: open 3082, click Board, list buttons.
import { chromium } from '/Users/huweixing/.agents/skills/browser-automation/node_modules/playwright/index.mjs'
const url = process.argv[2]
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(15000)
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(8000)
  await page.getByText('Board', { exact: true }).first().click({ timeout: 8000 })
  await page.waitForTimeout(4000)
  const btns = await page.evaluate(() => {
    const els = [...document.querySelectorAll('button, [role="textbox"], input')]
    return els.slice(0, 60).map(el => ({
      tag: el.tagName.toLowerCase(),
      text: (el.textContent || '').trim().slice(0, 40),
      aria: el.getAttribute('aria-label') || '',
      ph: el.getAttribute('placeholder') || '',
      cls: (el.className || '').toString().slice(0, 60),
    })).filter(b => b.text || b.aria || b.ph)
  })
  console.log(JSON.stringify(btns, null, 1))
} catch (e) { console.log('ERR', e.message) } finally { await browser.close() }
