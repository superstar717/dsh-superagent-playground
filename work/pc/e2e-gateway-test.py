import json, time, urllib.request

GW = "http://127.0.0.1:18480/v1/chat/completions"

def ask(body):
    req = urllib.request.Request(GW, json.dumps(body).encode(), {"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.loads(r.read())
    return out, time.time() - t0

# E198 repro: the max_tokens that used to 400 (request exceeds the context window)
big = {"model": "localmodels-byok",
       "messages": [{"role": "user", "content": "1+1等于几？直接答数字"}],
       "max_tokens": 32768, "temperature": 0}
try:
    out, dt = ask(big)
    ch = out["choices"][0]
    print("E198-REPRO OK http200", round(dt, 1), "s; finish:", ch.get("finish_reason"),
          "; content:", (ch["message"].get("content") or "")[:60],
          "; usage:", out.get("usage", {}).get("completion_tokens"), "out /",
          out.get("usage", {}).get("prompt_tokens"), "in")
except Exception as e:
    print("E198-REPRO FAIL:", repr(e)[:300])

# a real question through the gateway (what Linger's Pi agent will send)
real = {"model": "localmodels-byok",
        "messages": [{"role": "user", "content": "用一句话说明你是什么模型"}],
        "max_tokens": 2048, "temperature": 0}
try:
    out, dt = ask(real)
    ch = out["choices"][0]
    print("REAL OK", round(dt, 1), "s; finish:", ch.get("finish_reason"),
          "; content:", (ch["message"].get("content") or "").strip()[:120])
except Exception as e:
    print("REAL FAIL:", repr(e)[:300])
