// Screenshot helper for ticket 937d8cafda22 — drives Playwright directly with
// explicit timeouts (the DSH GUI holds websocket connections, so never wait
// for networkidle). Usage:
//   node shot.mjs <url> <outfile> [clickText] [waitMs]
import { chromium } from '/Users/huweixing/.agents/skills/browser-automation/node_modules/playwright/index.mjs'

const [url, out, clickText, waitMsArg] = process.argv.slice(2)
const waitMs = Number(waitMsArg || 6000)
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
page.setDefaultTimeout(15000)
try {
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 })
  await page.waitForTimeout(waitMs)
  if (clickText) {
    await page.getByText(clickText, { exact: false }).first().click({ timeout: 8000 })
    await page.waitForTimeout(3000)
  }
  await page.screenshot({ path: out, fullPage: false })
  console.log('saved', out)
} catch (e) {
  console.log('ERR', e.message)
  try { await page.screenshot({ path: out.replace(/\.png$/, '-err.png') }) ; console.log('saved error-state shot') } catch {}
} finally {
  await browser.close()
}
