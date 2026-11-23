import json, glob, time, urllib.request, sys
try:
    import websocket
except ImportError:
    sys.exit("no websocket module")

targets = json.loads(urllib.request.urlopen("http://127.0.0.1:9333/json", timeout=8).read())
page = next((t for t in targets if "localhost:3000" in t.get("url", "") and t.get("type") == "page"), None)
if not page:
    print("targets:", [(t.get("type"), t.get("url")) for t in targets])
    sys.exit("no localhost:3000 page target")
ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=15)
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                    "params": {"expression": "document.body.innerText",
                               "returnByValue": True}}))
text = ""
t0 = time.time()
while time.time() - t0 < 15:
    m = json.loads(ws.recv())
    if m.get("id") == 1:
        text = m["result"]["result"].get("value", "")
        break
ws.close()
bad = [k for k in ("需要登录", "Sign-in required", "Unavailable", "不可用", "登录 Pi") if k in text]
print("BAD-MARKERS:", bad if bad else "none")
idx = text.find("Runtime settings")
print("--- runtime snippet ---")
print(text[idx:idx + 400] if idx >= 0 else "(dialog not open)")
print("--- tail ---")
print(text[-300:])
