// Probe what the Add card click actually opens (document-wide).
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
  await page.getByText('Add card', { exact: true }).nth(1).click({ timeout: 8000 })
  await page.waitForTimeout(2000)
  const info = await page.evaluate(() => {
    const dlg = document.querySelector('[role="dialog"]')
    const inputs = [...document.querySelectorAll('[role="dialog"] input, [role="dialog"] textarea')]
    const btns = dlg ? [...dlg.querySelectorAll('button')].map(b => b.textContent.trim().slice(0, 30)) : []
    return {
      dialogPresent: !!dlg,
      dlgCls: dlg ? (dlg.className || '').toString().slice(0, 80) : '',
      inputs: inputs.map(el => ({ tag: el.tagName.toLowerCase(), aria: el.getAttribute('aria-label') || '', ph: el.getAttribute('placeholder') || '', cls: (el.className||'').toString().slice(0,50) })),
      btns,
    }
  })
  console.log(JSON.stringify(info, null, 1))
  await page.screenshot({ path: '/tmp/addcard-dialog.png' })
} catch (e) { console.log('ERR', e.message) } finally { await browser.close() }
