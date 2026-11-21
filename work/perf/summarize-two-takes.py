#!/usr/bin/env python3
# summarize-two-takes.py — cut the sampled windows and report per-process CPU
# means for a measure-two-takes.sh run. Reads <run>/top.txt + windows.txt +
# pids.txt; writes <run>/summary.json and prints a compact table.
import json, re, subprocess, sys, os

run = sys.argv[1]
top = os.path.join(run, 'top.txt')

# windows from the log-stamped step lines
marks = {}
for line in open(os.path.join(run, 'windows.txt'), errors='replace'):
    ts, _, rest = line.strip().partition(' ')
    for key in ('take1:control-pill-live', 'take1:stop-signalled',
                'take2:control-pill-live', 'take2:stop-signalled'):
        if key in rest:
            marks[key] = int(ts)
    if 'ALL_OK' in rest:
        marks['ALL_OK'] = int(ts)

# pids of this instance
pids = {}
for line in open(os.path.join(run, 'pids.txt')):
    kind, _, pid = line.strip().partition(' ')
    if kind in ('MAIN', 'GPU', 'VCAM', 'RENDERER'):
        pids.setdefault(kind, []).append(int(pid))
# first spawned renderer = the editor main window; the rest are pill/preview pages
if len(pids.get('RENDERER', [])) > 1:
    pids['RENDERER'] = sorted(pids['RENDERER'])
    pids.setdefault('PILLPAGES', pids['RENDERER'][1:])

# samples: one frame per "PID %CPU COMMAND" header row
samples = []
hdr = re.compile(r'^\s*PID\s+%CPU')
for line in open(top, errors='replace'):
    if hdr.match(line):
        samples.append([])
        continue
    m = re.match(r'^\s*(\d+)\s+([\d.]+)\s+(.*)$', line)
    if m and samples:
        samples[-1].append((int(m.group(1)), float(m.group(2)), m.group(3).strip()))

def window_mean(t0, t1):
    """Mean CPU per pid-kind over top frames whose epoch lands in [t0,t1].
    top frames carry no epoch: we date them by frame index around the wall
    clock of the run — instead, use counts: each top -s 2 frame ≈2s apart,
    anchored at the first mark. We therefore reconstruct epochs per frame."""
    out = {}
    n = 0
    tot = 0
    for frame in samples:
        for pid, cpu, _cmd in frame:
            out.setdefault(pid, []).append(cpu)
        n += 1
    return out, n

# Frame epochs: top stretches under load; anchor frames to marks by walking
# frames and assigning nearest-epoch via elapsed 2s cadence from run start,
# corrected at each mark boundary. Simpler robust cut: split frames at the
# frame index whose time matches mark deltas in ORDER of marks occurrence.
# --- pragmatic approach: assign each frame an epoch by 2s cadence starting at
# the earliest mark minus pill-wait (~unknown). We instead report per-quantile
# slices: use the marks' RELATIVE order to cut by frame fraction is unreliable.
# Robust and good enough for A/B: report (a) overall mean, (b) mean of the
# LAST 20 frames before end (idle window tail), (c) max steady value.
def stats(pid_list, frames):
    vals = []
    for f in frames:
        for pid, cpu, _cmd in f:
            if pid in pid_list:
                vals.append(cpu)
    if not vals:
        return None
    vals.sort()
    return {'n': len(vals), 'mean': round(sum(vals) / len(vals), 1),
            'p50': vals[len(vals) // 2], 'max': vals[-1]}

editor = set(pids.get('RENDERER', []))
gpu = set(pids.get('GPU', []))
vcam = set(pids.get('VCAM', []))
pill = set(pids.get('PILLPAGES', []))
mainset = set(pids.get('MAIN', []))

# Frame epochs: top stretches under load, so derive the per-frame interval
# from the measured sampling window (top-start.txt .. top-end.txt).
def read_epoch(name):
    p = os.path.join(run, name)
    return int(open(p).read().strip()) if os.path.exists(p) else None

ts = read_epoch('top-start.txt')
te = read_epoch('top-end.txt')
if 'ALL_OK' in marks:
    n_frames = len(samples)
    if ts is not None and te is not None and n_frames > 0:
        start_epoch = ts
        interval = max(0.1, (te - ts) / n_frames)
    else:
        end_epoch = marks['ALL_OK'] + 48
        interval = 2.0
        start_epoch = end_epoch - interval * n_frames

    def frames_in(t0, t1):
        lo = max(0, int((t0 - start_epoch) / interval))
        hi = min(n_frames, int((t1 - start_epoch) / interval) + 1)
        return samples[lo:hi]
    w = {}
    if all(k in marks for k in ('take1:control-pill-live', 'take1:stop-signalled')):
        w['take1'] = frames_in(marks['take1:control-pill-live'], marks['take1:stop-signalled'])
        if 'take2:control-pill-live' in marks:
            w['between'] = frames_in(marks['take1:stop-signalled'], marks['take2:control-pill-live'])
        if 'take2:stop-signalled' in marks:
            w['take2'] = frames_in(marks['take2:control-pill-live'], marks['take2:stop-signalled'])
    w['idle'] = frames_in(marks['ALL_OK'] + 5, marks['ALL_OK'] + 45)
else:
    w = {'all': samples}

summary = {}
for name, frames in w.items():
    summary[name] = {
        'editor_renderer': stats(editor, frames),
        'gpu': stats(gpu, frames),
        'video_capture': stats(vcam, frames),
        'pill_preview_pages': stats(pill, frames),
        'main': stats(mainset, frames),
        'frames': len(frames),
    }
summary['pids'] = {k: v for k, v in pids.items()}
summary['marks'] = {k: v for k, v in marks.items()}
with open(os.path.join(run, 'summary.json'), 'w') as f:
    json.dump(summary, f, indent=1, ensure_ascii=False)

print(f"{'window':<10} {'editor%':>18} {'gpu%':>18} {'vcam%':>18}")
for name in summary:
    if name in ('pids', 'marks'):
        continue
    row = summary[name]
    def fmt(x):
        return f"{x['mean']}(p50 {x['p50']},max {x['max']})" if x else '—'
    print(f"{name:<10} {fmt(row['editor_renderer']):>18} {fmt(row['gpu']):>18} {fmt(row['video_capture']):>18}")
