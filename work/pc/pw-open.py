import shutil, os
from playwright.sync_api import sync_playwright

src = r"C:\Users\Administrator\.local\state\linger-ls-copy"
udb = r"F:\AI\logs\pw-profile"
if os.path.exists(udb):
    shutil.rmtree(udb, ignore_errors=True)
os.makedirs(os.path.join(udb, "Default", "Local Storage", "leveldb"), exist_ok=True)
os.makedirs(os.path.join(udb, "Default", "IndexedDB"), exist_ok=True)
shutil.copytree(os.path.join(src, "Local Storage", "leveldb"), os.path.join(udb, "Default", "Local Storage", "leveldb"), dirs_exist_ok=True)
shutil.copytree(os.path.join(src, "indexeddb"), os.path.join(udb, "Default", "IndexedDB", "http_localhost_3000.indexeddb.leveldb"), dirs_exist_ok=True)

with sync_playwright() as p:
    ctx = None
    try:
        ctx = p.chromium.launch_persistent_context(udb, channel="msedge", headless=True, viewport={"width": 1600, "height": 900})
        print("engine: msedge")
    except Exception as e:
        print("msedge failed:", str(e)[:200])
        ctx = p.chromium.launch_persistent_context(udb, headless=True, viewport={"width": 1600, "height": 900})
        print("engine: bundled chromium")
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    pg.goto("http://localhost:3000/", timeout=30000)
    pg.wait_for_timeout(6000)
    print("URL:", pg.url)
    body = pg.evaluate("() => document.body.innerText.slice(0, 600)")
    print("---body---")
    print(body)
    pg.screenshot(path=r"F:\AI\logs\pw-1.png")
    ctx.close()
