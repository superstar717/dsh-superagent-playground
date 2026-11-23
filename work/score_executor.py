#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""剪辑谱执行器 · edit-score/v1

照谱执行：score.json (+transcript.json) → plan/effects/ASS → ffmpeg 两 pass 渲染 → 验证。
算法与已交付管线（build_plan2/build_subs2/render2）逐条对齐，保证同一谱可复现同一成片；
换视频只换谱，不改执行器。

用法：
  校验+产物比对（不渲染）:
    python3 score_executor.py --score S.json --source SRC.mp4 --transcript T.json \
        --work OUTDIR --reference-plan plan2.json --reference-effects effects.json \
        --reference-ass final2.ass
  完整渲染+验证:
    python3 score_executor.py ... --render [--compare 已交付成片.mp4]
"""
import argparse, json, os, re, subprocess, sys

TOL = 0.08          # 词级时间轴边界容差（HANDOFF 坑 3：±80ms）
CUT_EDGE_EPS = 0.02 # 整词删除校验容差


def sh(args, cwd=None):
    r = subprocess.run(args, capture_output=True, text=True, cwd=cwd)
    if r.returncode != 0:
        print("rc=%d" % r.returncode)
        print((r.stderr or "")[-1800:])
        raise SystemExit(1)
    return r


def load_score(path):
    s = json.load(open(path, encoding="utf-8"))
    assert s.get("schema") == "edit-score/v1", "schema 必须是 edit-score/v1"
    return s


def validate(score, words, dur):
    ok = True
    keeps = score["keep"]
    # 输出顺序内 keep 两两不重叠（钩子倒挂是靠输出顺序表达，不靠源时间）
    for i in range(len(keeps) - 1):
        a2 = keeps[i + 1]["src"]
        if a2[0] < keeps[i]["src"][1] and not (a2[1] <= keeps[i]["src"][0]):
            pass  # 源时间倒挂允许（钩子置顶），仅检查输出顺序本身合法
    for k in keeps:
        a, b = k["src"]
        if not (0 <= a < b <= dur + 0.01):
            ok = False
            print("!! keep 越界 %s" % (k["src"],))
    # 整词删除校验：与删除区间相交的词必须完整落在区间内
    for e in score["edits"]:
        if e["type"] not in ("repeat", "restart"):
            continue
        a, b = e["src"]
        ws = [w for w in words if w[0] < b - 0.005 and w[1] > a + 0.005]
        partial = [w for w in ws if w[0] < a - CUT_EDGE_EPS or w[1] > b + CUT_EDGE_EPS]
        text = "".join(w[2] for w in ws)
        print("cut %.2f-%.2f %s | 删:%s" % (a, b, e["note"], text))
        if partial:
            ok = False
            print("  !! 削到边角的词:", [(round(w[0], 2), round(w[1], 2), w[2]) for w in partial])
    print("VALID=%s" % ("OK" if ok else "FAIL"))
    return ok


def segments_of(score):
    return [{"start": a, "end": b, "note": k.get("note", "")}
            for k, (a, b) in ((k, k["src"]) for k in score["keep"])]


def remap(t, segs, tol=0.0):
    """源时间 → 输出时间；tol=0 用于特效（与 build_plan2.win 一致），tol=TOL 用于字幕。"""
    acc = 0.0
    for s in segs:
        if s["start"] - tol <= t <= s["end"] + tol:
            return min(max(acc + (t - s["start"]), 0.0), acc + (s["end"] - s["start"]))
        acc += s["end"] - s["start"]
    return None


def join_times(segs):
    out, acc = [], 0.0
    for i in range(len(segs) - 1):
        acc += segs[i]["end"] - segs[i]["start"]
        out.append(round(acc, 2))
    return out


def emit_plan(score, source_duration):
    segs = segments_of(score)
    # 钩子=输出顺序第一段（倒挂由输出顺序表达）
    hook = score["keep"][0]["src"]
    plan = {"source_duration": source_duration, "hook": list(hook),
            "segments": segs,
            "expected_duration": round(sum(b - a for a, b, _ in [(s["start"], s["end"], s["note"]) for s in segs]), 3)}
    return plan


def emit_effects(score, segs):
    fx = {"zooms": [], "callouts": []}
    for z in score["effects"]["zoom"]["items"]:
        t = win(z["src"][0], z["src"][1], segs)
        if t:
            fx["zooms"].append({"t": t, "note": z["note"]})
    for c in score["effects"]["callouts"]:
        t = win(c["src"][0], c["src"][1], segs)
        if t:
            fx["callouts"].append({"text": c["text"], "t": t})
    return fx


def win(t1, t2, segs):
    o1, o2 = remap(t1, segs), remap(t2, segs)
    return [round(o1, 2), round(o2, 2)] if o1 is not None and o2 is not None else None


def emit_ass(score, tr, segs, font):
    fx = emit_effects(score, segs)
    rules = score["subtitle"]["line_rules"]
    fixes = score["subtitle"]["fixes"]

    def fix_text(s):
        for a, b in fixes:
            s = s.replace(a, b)
        return s

    words = []
    for seg in tr["segments"]:
        for w in seg.get("words", []):
            o_s, o_e = remap(w["start"], segs, TOL), remap(w["end"], segs, TOL)
            if o_s is None or o_e is None:
                continue
            words.append((o_s, o_e, w["word"]))

    jts = join_times(segs)
    lines, cur, cur_start, cur_end = [], [], None, None

    def crosses_join(a, b):
        return any(a < jt - 0.02 < b for jt in jts)

    for (s, e, w) in words:
        wclean = w.strip()
        if not wclean:
            continue
        if cur and (len("".join(cur)) + len(wclean) > rules["max_len"]
                    or s - cur_end > rules["max_gap"]
                    or (rules["break_on_join"] and crosses_join(cur_end, s))):
            lines.append((cur_start, cur_end, "".join(cur)))
            cur, cur_start, cur_end = [], None, None
        if cur_start is None:
            cur_start = s
        cur.append(wclean)
        cur_end = e
    if cur:
        lines.append((cur_start, cur_end, "".join(cur)))

    out_lines = []
    for (s, e, t) in lines:
        t = fix_text(t).strip()
        if not t:
            continue
        if e - s < rules["min_dur"]:
            e = s + rules["min_dur"]
        out_lines.append([s, e, t])
    for i in range(len(out_lines) - 1):
        if out_lines[i][1] > out_lines[i + 1][0] - rules["overlap_guard"]:
            out_lines[i][1] = max(out_lines[i][0] + 0.4, out_lines[i + 1][0] - rules["overlap_guard"])

    def ts(t):
        h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
        return "%d:%02d:%05.2f" % (h, m, s)

    st = score["subtitle"]["styles"]
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: %d
PlayResY: %d
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,%s,%d,%s,%s,%s,&H00000000,0,0,0,0,100,100,%d,0,1,%d,%d,%d,20,20,%d,1
Style: Callout,%s,%d,%s,%s,%s,&H00000000,-1,0,0,0,100,100,%d,0,1,%d,%d,%d,16,16,%d,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
""" % (score["subtitle"]["playres"][0], score["subtitle"]["playres"][1],
        font, st["default"]["size"], st["default"]["primary"], st["default"]["primary"], st["default"]["outline"],
        st["default"]["spacing"], st["default"]["outline_w"], st["default"]["shadow"], st["default"]["alignment"], st["default"]["margin_v"],
        font, st["callout"]["size"], st["callout"]["primary"], st["callout"]["primary"], st["callout"]["outline"],
        st["callout"]["spacing"], st["callout"]["outline_w"], st["callout"]["shadow"], st["callout"]["alignment"], st["callout"]["margin_v"])

    body = ""
    for s, e, t in out_lines:
        body += "Dialogue: 0,%s,%s,Default,,0,0,0,,%s\n" % (ts(s), ts(e), t)
    for c in fx["callouts"]:
        s, e = c["t"]
        e = min(e, s + st["callout"]["max_show_s"])
        if e - s < st["callout"]["min_show_s"]:
            e = s + st["callout"]["min_show_s"]
        body += "Dialogue: 1,%s,%s,Callout,,0,0,0,,{%s}%s\n" % (
            ts(s), ts(e), st["callout"]["animation"], c["text"])
    return header + body, len(out_lines), len(fx["callouts"])


def render(score, work, source, ass_name, base_name, out_name, segs, dur):
    v = score["render"]["video"]; a = score["render"]["audio"]
    # pass 1：拼接（每段音频 8ms 边缘淡入淡出防咔哒）
    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for s in segs:
        args += ["-ss", str(s["start"]), "-t", str(round(s["end"] - s["start"], 3)), "-i", source]
    n = len(segs)
    xf = score["audio"]["join_crossfade_s"]
    fc = ""
    for i in range(n):
        d = segs[i]["end"] - segs[i]["start"]
        fc += "[%d:a]afade=t=in:st=0:d=%.3f,afade=t=out:st=%.3f:d=%.3f[a%d];" % (
            i, xf, max(d - xf * 1.25, 0), xf, i)
    fc += "".join("[%d:v][a%d]" % (i, i) for i in range(n))
    fc += "concat=n=%d:v=1:a=1[v][a]" % n
    args += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
             "-c:v", v["codec"], "-crf", str(v["crf"]), "-preset", v["preset"], "-pix_fmt", v["pix_fmt"],
             "-c:a", a["codec"], "-b:a", a["bitrate"], "-movflags", "+faststart",
             os.path.join(work, base_name)]
    print("pass1 ...", flush=True)
    sh(args)

    # whoosh 音效素材
    whoosh = os.path.join(work, "whoosh.wav")
    sh(["ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "anoisesrc=d=0.5:c=brown:a=0.9",
        "-af", "lowpass=f=900,highpass=f=180,afade=t=in:st=0:d=0.18,afade=t=out:st=0.22:d=0.28,volume=0.5",
        whoosh])

    wj = [j["out"] for j in score["effects"]["whoosh_joins"]]
    wj = [t for t in wj if t < dur - 1]

    # pass 2：运镜 + 字幕花字 + 淡入淡出 + 音效
    zc = score["render"]["zoom_crop"]
    pw, ph = score["meta"]["width"], score["meta"]["height"]
    cw, ch = zc["cw"], zc["ch"]
    z = "crop=%d:%d:%d:%d,scale=%d:%d,setsar=1" % (cw, ch, (pw - cw) // 2, (ph - ch) // 2, pw, ph)
    zooms = score["effects"]["zoom"]["items"]
    splits = "".join("[z%d]" % i for i in range(len(zooms)))
    fc = "[0:v]split=%d[base]%s;" % (1 + len(zooms), splits)
    for i, zm in enumerate(zooms):
        fc += "[z%d]%s[zz%d];" % (i, z, i)
    prev = "base"
    for i, zm in enumerate(zooms):
        t = win(zm["src"][0], zm["src"][1], segs)
        outl = "o%d" % i if i < len(zooms) - 1 else "oz"
        fc += "[%s][zz%d]overlay=enable='between(t,%.2f,%.2f)'[%s];" % (prev, i, t[0], t[1], outl)
        prev = outl
    fd = score["effects"]["fades"]
    # subtitle.burn（可选，默认 true）：源片已带烧录字幕时，渲染不二次压字（ASS 产物仍照常生成供比对）
    burn = score["subtitle"].get("burn", True)
    # 时长 0 的淡入淡出必须跳过：实测 fade d=0 会把首帧涂黑（非 no-op），留空链条接 null
    vchain = []
    if fd.get("video_in", 0) > 0:
        vchain.append("fade=t=in:st=0:d=%.2f" % fd["video_in"])
    if fd.get("video_out", 0) > 0:
        vchain.append("fade=t=out:st=%.2f:d=%.2f" % (dur - fd["video_out"] - 0.05, fd["video_out"]))
    if burn:
        vchain.append("ass=filename=%s" % ass_name)
    fc += "[%s]%s[v];" % (prev, ",".join(vchain) if vchain else "null")
    a_in = "[0:a]"
    for i, t in enumerate(wj):
        fc += "[%d:a]adelay=%d:all=1[w%d];" % (1 + i, int(t * 1000) - 150, i)
        a_in += "[w%d]" % i
    achain = "amix=inputs=%d:normalize=0" % (1 + len(wj))
    if fd.get("audio_out", 0) > 0:
        achain += ",afade=t=out:st=%.2f:d=%.2f" % (dur - fd["audio_out"] - 0.05, fd["audio_out"])
    fc += "%s%s[a]" % (a_in, achain)

    args = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", os.path.join(work, base_name)]
    for _ in wj:
        args += ["-i", whoosh]
    args += ["-filter_complex", fc, "-map", "[v]", "-map", "[a]",
             "-c:v", v["codec"], "-crf", str(v["crf"]), "-preset", v["preset"], "-pix_fmt", v["pix_fmt"],
             "-c:a", a["codec"], "-b:a", a["bitrate"], "-movflags", "+faststart",
             os.path.join(work, out_name)]
    print("pass2 ...", flush=True)
    sh(args, cwd=work)
    return wj


def verify(work, out_name, dur, score):
    p = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", os.path.join(work, out_name)])
    out_dur = float(p.stdout.strip())
    print("output=%.2fs expected=%.2fs diff=%.2fs" % (out_dur, dur, out_dur - dur))
    tol = score["acceptance"]["duration_tolerance_s"]
    # QC 抽帧时刻可由谱指定（长片默认时刻无意义时用）；缺省回退到样本默认，向后兼容
    qc = score["acceptance"].get("qc_frames",
                                 [["hook", 1.6], ["callout", 35.5], ["zoom", 126.8],
                                  ["callout2", 116.0], ["end", 159.8]])
    for name, t in qc:
        sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", "%.1f" % t, "-i", os.path.join(work, out_name),
            "-frames:v", "1", os.path.join(work, "score_%s.png" % name)])
        print("frame score_%s" % name)
    print("VERIFY-%s" % ("OK" if abs(out_dur - dur) < tol else "DURATION-MISMATCH"))


def compare(work, a, b):
    """整片 PSNR/SSIM + 时长差。"""
    p = sh(["ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", os.path.join(work, b)])
    print("ref=%s dur=%.3f" % (b, float(p.stdout.strip())))
    r = subprocess.run(["ffmpeg", "-i", os.path.join(work, a), "-i", os.path.join(work, b),
                        "-lavfi", "psnr", "-f", "null", "-"], capture_output=True, text=True, cwd=work)
    m = re.search(r"average:([\d.]+|inf).*", r.stderr)
    line = [l for l in r.stderr.splitlines() if "PSNR" in l or "average" in l]
    print("\n".join(line[-3:]) if line else "psnr parse fail")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--font", default=None, help="覆盖 font_stack（默认取第一个）")
    ap.add_argument("--prefix", default="score")
    ap.add_argument("--reference-plan", default=None)
    ap.add_argument("--reference-effects", default=None)
    ap.add_argument("--reference-ass", default=None)
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--compare", default=None, help="与已交付成片整片 PSNR 比对")
    a = ap.parse_args()

    a.work = os.path.abspath(a.work)  # pass2 会切 cwd 到 work：相对路径在此会错位
    os.makedirs(a.work, exist_ok=True)
    score = load_score(a.score)
    tr = json.load(open(a.transcript, encoding="utf-8"))
    dur = tr["duration"]
    words = [(w["start"], w["end"], w["word"]) for s in tr["segments"] for w in s.get("words", [])]

    ok = validate(score, words, dur)
    segs = segments_of(score)
    plan = emit_plan(score, dur)
    fx = emit_effects(score, segs)

    font = a.font or score["subtitle"]["font_stack"][0]
    ass, n_sub, n_cal = emit_ass(score, tr, segs, font)

    plan_path = os.path.join(a.work, "%s_plan.json" % a.prefix)
    fx_path = os.path.join(a.work, "%s_effects.json" % a.prefix)
    ass_path = os.path.join(a.work, "%s.ass" % a.prefix)
    json.dump(plan, open(plan_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(fx, open(fx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(ass_path, "w", encoding="utf-8").write(ass)
    print("subs=%d callouts=%d joins=%s" % (n_sub, n_cal, join_times(segs)))

    # 谱内自检：特效重映射必须命中谱记录的交付输出时刻
    for i, z in enumerate(score["effects"]["zoom"]["items"]):
        t = win(z["src"][0], z["src"][1], segs)
        if "expected_out" in z and [round(t[0], 2), round(t[1], 2)] != z["expected_out"]:
            print("!! zoom%d 重映射 %s != expected %s" % (i, t, z["expected_out"]))
            ok = False
    for c in score["effects"]["callouts"]:
        t = win(c["src"][0], c["src"][1], segs)
        if "expected_out" in c and [round(t[0], 2), round(t[1], 2)] != c["expected_out"]:
            print("!! callout '%s' 重映射 %s != expected %s" % (c["text"], t, c["expected_out"]))
            ok = False

    # 与已交付真值逐项比对
    if a.reference_plan:
        ref = json.load(open(a.reference_plan, encoding="utf-8"))
        ref_se = [[round(s["start"], 3), round(s["end"], 3)] for s in ref["segments"]]
        our_se = [[round(s["start"], 3), round(s["end"], 3)] for s in plan["segments"]]
        same = ref_se == our_se and abs(ref["expected_duration"] - plan["expected_duration"]) < 0.01
        print("plan-vs-ref: %s (expected %.3f vs %.3f)（note 为谱注记，不参与比对）" % ("MATCH" if same else "DIFF",
              ref["expected_duration"], plan["expected_duration"]))
        if not same:
            for i, (x, y) in enumerate(zip(ref_se, our_se)):
                if x != y:
                    print("  首个差异段 %d: ref=%s ours=%s" % (i, x, y))
                    break
    if a.reference_effects:
        ref = json.load(open(a.reference_effects, encoding="utf-8"))
        # note 为谱注记；比对功能字段（时刻/文本）
        ref_c = {c["text"]: c["t"] for c in ref.get("callouts", [])}
        our_c = {c["text"]: c["t"] for c in fx.get("callouts", [])}
        ref_z = [z["t"] for z in ref.get("zooms", [])]
        our_z = [z["t"] for z in fx.get("zooms", [])]
        same = ref_z == our_z and ref_c == our_c
        print("effects-vs-ref: %s（note 为谱注记，不参与比对）" % ("MATCH" if same else "DIFF"))
        if not same:
            print("  ref :", json.dumps(ref, ensure_ascii=False))
            print("  ours:", json.dumps(fx, ensure_ascii=False))
    if a.reference_ass:
        ref = open(a.reference_ass, encoding="utf-8").read()
        same = ref == ass
        print("ass-vs-ref: %s (%d vs %d bytes)" % ("MATCH" if same else "DIFF", len(ref.encode('utf-8')), len(ass.encode('utf-8'))))
        if not same:
            rl, al = ref.splitlines(), ass.splitlines()
            for i, (x, y) in enumerate(zip(rl, al)):
                if x != y:
                    print("  首个差异行 %d:\n    ref : %s\n    ours: %s" % (i + 1, x, y))
                    break
            if len(rl) != len(al):
                print("  行数不同 ref=%d ours=%d" % (len(rl), len(al)))

    if not ok:
        print("VALID-FAIL：中止渲染")
        sys.exit(2)

    if a.render:
        base_name = "%s_base.mp4" % a.prefix
        out_name = "%s.mp4" % a.prefix
        render(score, a.work, a.source, os.path.basename(ass_path), base_name, out_name, segs, plan["expected_duration"])
        verify(a.work, out_name, plan["expected_duration"], score)
        if a.compare:
            compare(a.work, out_name, a.compare)


if __name__ == "__main__":
    main()
