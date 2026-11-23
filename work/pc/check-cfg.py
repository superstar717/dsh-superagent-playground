import json, sys, os
p = r"F:\AI\PolyStrata\PolyStrata-main\strata-q2_0.json"
try:
    cfg = json.load(open(p, encoding="utf-8-sig"))
    print("JSON OK; fit_max_tokens =", cfg.get("fit_max_tokens"), "; keys =", len(cfg))
except Exception as e:
    print("JSON FAIL:", repr(e))

for f in (r"F:\AI\logs\serve-q2_0.log", r"F:\AI\logs\serve-q2_0.err.log"):
    st = os.stat(f)
    print(f, "size", st.st_size, "mtime", __import__("time").strftime("%H:%M:%S", __import__("time").localtime(st.st_mtime)))
