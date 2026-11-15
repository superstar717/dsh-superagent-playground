#!/usr/bin/env python3
# summarize-run.py — aggregate one measure-take run's top.txt into per-group CPU,
# restricted to the recording window when pids.txt carries T/MS markers.
# usage: summarize-run.py <run-dir> [<run-dir> ...]
import json, re, subprocess, sys, os, statistics
from datetime import datetime

def windowserver_pid():
    try:
        return int(subprocess.run(['pgrep', '-x', 'WindowServer'], capture_output=True, text=True).stdout.split()[0])
    except Exception:
        return None

WS_PID = windowserver_pid()
ROW_RE = re.compile(r'^\s*(\d+)\s+([\d.]+)\s+(.+)$')
SYS_RE = re.compile(r'CPU usage:\s+([\d.]+)% user,\s+([\d.]+)% sys,\s+([\d.]+)% idle')
LOAD_RE = re.compile(r'Load Avg:\s+([\d.]+),\s*([\d.]+),\s*([\d.]+)')
TS_RE = re.compile(r'^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\s*$')

def parse_run(run_dir):
    top_path = os.path.join(run_dir, 'top.txt')
    if not os.path.exists(top_path):
        return None
    pids, window = set(), None
    pids_path = os.path.join(run_dir, 'pids.txt')
    if os.path.exists(pids_path):
        for line in open(pids_path):
            parts = line.split()
            if not parts:
                continue
            if parts[0] == 'T':
                window = [int(parts[1]), 0]
            elif parts[0] == 'MS' and window:
                window[1] = int(parts[1])
            elif parts[0] == 'P':
                pids.add(int(parts[1]))
            elif parts[0].isdigit():
                pids.add(int(parts[0]))
    # split into per-sample blocks at each "Processes:" line
    text = open(top_path, errors='replace').read()
    blocks = text.split('Processes:')[1:]
    samples = []       # (epoch_or_None, {pid:(cpu,comm)}, (user,sys,idle), load1)
    for b in blocks:
        ts = None
        m = TS_RE.search(b[:400])
        if m:
            try:
                ts = datetime.strptime(m.group(1), '%Y/%m/%d %H:%M:%S').timestamp()
            except Exception:
                ts = None
        rows, sysv, load1 = {}, None, None
        for line in b.splitlines():
            sm = SYS_RE.search(line)
            if sm:
                sysv = tuple(float(x) for x in sm.groups())
                continue
            lm = LOAD_RE.search(line)
            if lm:
                load1 = float(lm.group(1))
                continue
            rm = ROW_RE.match(line)
            if rm:
                rows[int(rm.group(1))] = (float(rm.group(2)), rm.group(3).strip())
        if rows:
            samples.append((ts, rows, sysv, load1))
    # sample 1 of top -l is cumulative-since-boot: drop it
    if len(samples) > 1:
        samples = samples[1:]
    # keep only samples inside the recording window when known
    in_window = samples
    if window and window[1]:
        lo, hi = window[0] - 1, window[0] + window[1] / 1000.0 + 4
        w = [s for s in samples if s[0] and lo <= s[0] <= hi]
        if w:
            in_window = w
    groups, per_pid = {}, {}
    system, loads = [], []
    for ts, rows, sysv, load1 in in_window:
        app_sum = 0.0
        for pid, (cpu, comm) in rows.items():
            if pid in pids:
                app_sum += cpu
                per_pid.setdefault(pid, []).append((cpu, comm))
            elif pid == WS_PID:
                groups.setdefault('windowserver', []).append(cpu)
            elif comm.startswith('Google Chrome'):
                groups.setdefault('chrome', []).append(cpu)
            elif comm.startswith('VDCAssistant'):
                groups.setdefault('vdcassistant_camera', []).append(cpu)
            elif comm.startswith('VTDecoder'):
                groups.setdefault('vt_decoder_xpc', []).append(cpu)
            elif comm.startswith('ffmpeg'):
                groups.setdefault('ffmpeg', []).append(cpu)
        if pids:
            groups.setdefault('app_total', []).append(app_sum)
        if sysv:
            system.append(sysv)
        if load1:
            loads.append(load1)
    out = {'dir': run_dir, 'samples_total': len(samples), 'samples_used': len(in_window)}
    def agg(vals):
        return {'mean': round(statistics.mean(vals), 1), 'max': round(max(vals), 1)}
    for g, vals in groups.items():
        out[g] = agg(vals)
    pp = {}
    for pid, vals in per_pid.items():
        pp[str(pid)] = {'comm': vals[0][1], 'mean': round(statistics.mean(v[0] for v in vals), 1), 'max': round(max(v[0] for v in vals), 1)}
    out['app_pids'] = pp
    if system:
        out['system'] = {'user_mean': round(statistics.mean(x[0] for x in system), 1),
                         'sys_mean': round(statistics.mean(x[1] for x in system), 1),
                         'idle_mean': round(statistics.mean(x[2] for x in system), 1)}
    if loads:
        out['loadavg_mean'] = round(statistics.mean(loads), 2)
    probe_path = os.path.join(run_dir, 'probe.json')
    if os.path.exists(probe_path):
        try:
            d = json.load(open(probe_path))
            st = d['streams'][0]
            out['codec'] = st.get('codec_name')
            out['profile'] = st.get('profile')
            out['size_bytes'] = int(d.get('format', {}).get('size', 0))
        except Exception:
            pass
    return out

for d in sys.argv[1:]:
    r = parse_run(d)
    print(json.dumps(r, ensure_ascii=False))
