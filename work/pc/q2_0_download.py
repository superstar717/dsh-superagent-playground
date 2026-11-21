#!/usr/bin/env python3
"""Resumable download of Qwen3.8-Flash-Next GSQ-RCO-Q2_0 (2 shards, 66.42 GB) from ModelScope.

Why not setup.py: this ticket only resumes the download; the install (packing, config, start)
stays paused per the operator's routing note.  The layout matches what setup.py expects, so a
later `setup.py --family qwen --model Q2_0` sees the files as already downloaded:
    D:\\AI\\PolyStrata-data\\models\\Q2_0\\<shard>.gguf (+ <shard>.gguf.done mark)
Partial files are <shard>.gguf.part, resumed by HTTP Range - the same convention setup.py uses.

Behaviour:
  * one shard at a time (the 100 Mbps wired link is the bottleneck, not the connection count)
  * Range resume, re-resolving ModelScope's 302 on every attempt, 8 MiB chunks
  * stall/error -> reconnect and continue; gives up only after MAX_ATTEMPTS
  * after the last byte: size check, SHA-256 check against ModelScope's published hash,
    rename .part -> .gguf, write the .done mark (same mark setup.py writes)
  * safe to re-run: finished shards are skipped, partial ones resume
  * keeps the machine awake while it runs (in-process only, no power-plan change)
"""
import ctypes
import hashlib
import os
import sys
import time
import urllib.request

REPO = "ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF"
SUB = "Q2_0"
BASE = f"https://www.modelscope.cn/models/{REPO}/resolve/master/{SUB}/"
DEST = r"D:\AI\PolyStrata-data\models\Q2_0"
LOGDIR = r"F:\AI\logs"

# (file name, size in bytes, sha256 published by ModelScope, also served as X-Linked-Etag)
FILES = [
    ("Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00001-of-00002.gguf", 37_623_740_192,
     "69820c02ec7d0b45ef2ebb19d6620299db749fe2aded7f39f93c6b88b199b720"),
    ("Qwen3.8-Flash-Next-GSQ-RCO-Q2_0-00002-of-00002.gguf", 28_800_138_432,
     "316b46f3a2dbd68c900f43136ab9449f9dcc3725dfd8c794847c204bc161e113"),
]
CHUNK = 8 << 20
PROGRESS_EVERY = 15.0          # seconds between progress lines
READ_TIMEOUT = 90              # seconds without a byte -> reconnect
MAX_ATTEMPTS = 400             # each attempt is a Range resume, so this is generous on purpose


def log(msg, path=None):
    line = time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg
    print(line, flush=True)
    if path:
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def keep_awake():
    """ES_CONTINUOUS | ES_SYSTEM_REQUIRED: no sleep while this process runs. Reverted on exit."""
    try:
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001))
    except Exception:
        return False


def free_gb(path):
    try:
        return round(__import__("shutil").disk_usage(path).free / 1e9, 1)
    except OSError:
        return -1.0


def head_size(name):
    url = BASE + name
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "strata-setup"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return int(r.headers.get("Content-Length", 0)), r.headers.get("X-Linked-Etag", "")


def sha256_of(path, total=None, on_progress=None):
    h = hashlib.sha256()
    n = 0
    last = time.time()
    with open(path, "rb") as f:
        while True:
            b = f.read(16 << 20)
            if not b:
                break
            h.update(b)
            n += len(b)
            if on_progress and time.time() - last >= 15:
                on_progress(n, total or n)
                last = time.time()
    return h.hexdigest(), n


def fetch(name, total, sha, logpath):
    dst = os.path.join(DEST, name)
    mark = dst + ".done"
    part = dst + ".part"

    if os.path.exists(dst) and os.path.exists(mark):
        log(f"[skip] {name}: already complete (finish mark present)", logpath)
        return True
    if os.path.exists(dst) and os.path.getsize(dst) == total and not os.path.exists(part):
        log(f"[verify] {name}: full size already on disk, checking SHA-256", logpath)
        digest, _ = sha256_of(dst)
        if digest == sha:
            open(mark, "w", encoding="utf-8").write(time.strftime("%Y-%m-%d %H:%M"))
            log(f"[ok] {name}: SHA-256 matches, finish mark written", logpath)
            return True
        log(f"[warn] {name}: SHA-256 mismatch on the existing file, deleting it", logpath)
        os.unlink(dst)

    url = BASE + name
    attempt = 0
    while True:
        attempt += 1
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if have >= total:
            break
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "strata-setup",
                                                       "Range": f"bytes={have}-"})
            with urllib.request.urlopen(req, timeout=READ_TIMEOUT) as r, \
                    open(part, "ab" if have else "wb") as f:
                if have and r.status != 206:
                    log(f"[warn] {name}: server ignored Range (HTTP {r.status}), restarting the file", logpath)
                    f.seek(0)
                    f.truncate()
                    have = 0
                started = time.time()
                last = started
                last_bytes = have
                while True:
                    b = r.read(CHUNK)
                    if not b:
                        break
                    f.write(b)
                    have += len(b)
                    now = time.time()
                    if now - last >= PROGRESS_EVERY:
                        rate = (have - last_bytes) / max(now - last, 1e-6)        # bytes/s
                        eta_min = (total - have) / max(rate, 1.0) / 60 if rate > 0 else float("inf")
                        log(f"[prog] {name}: {have/1e9:.2f}/{total/1e9:.2f} GB "
                            f"({100*have/total:.1f}%) {rate/1e6:.1f} MB/s ETA {eta_min:.0f} min", logpath)
                        last, last_bytes = now, have
            if have >= total:
                break
            log(f"[warn] {name}: connection ended at {have:,} bytes "
                f"(attempt {attempt}); resuming in 10 s", logpath)
            time.sleep(10)
        except Exception as e:                                    # noqa: BLE001 - any transport error resumes
            log(f"[warn] {name}: {type(e).__name__}: {e} (attempt {attempt}); resuming in 15 s", logpath)
            time.sleep(15)
        if attempt > MAX_ATTEMPTS:
            log(f"[fail] {name}: {MAX_ATTEMPTS} attempts exhausted", logpath)
            return False

    size = os.path.getsize(part)
    if size != total:
        log(f"[fail] {name}: {size:,} bytes on disk, expected {total:,}", logpath)
        return False
    log(f"[verify] {name}: computing SHA-256 over {size/1e9:.2f} GB", logpath)
    digest, _ = sha256_of(part, total,
                          on_progress=lambda n, t: log(f"[hash] {name}: {n/1e9:.1f}/{t/1e9:.1f} GB", logpath))
    if digest != sha:
        log(f"[fail] {name}: SHA-256 {digest} != expected {sha}; kept as .part for inspection", logpath)
        return False
    os.replace(part, dst)
    open(mark, "w", encoding="utf-8").write(time.strftime("%Y-%m-%d %H:%M"))
    log(f"[ok] {name}: downloaded, SHA-256 verified ({digest[:16]}...)", logpath)
    return True


def main():
    os.makedirs(DEST, exist_ok=True)
    os.makedirs(LOGDIR, exist_ok=True)
    logpath = os.path.join(LOGDIR, "q2_0-download.log")
    lock = open(os.path.join(DEST, ".q2_0-download.lock"), "w")
    try:
        import msvcrt
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)         # second copy exits here
    except OSError:
        log("[skip] another downloader instance holds the lock; exiting")
        return 0

    log("=" * 70, logpath)
    log(f"start: python={sys.version.split()[0]} user={os.environ.get('USERNAME')} "
        f"dest={DEST} free_D={free_gb(DEST)} GB", logpath)
    keep_awake()
    expect = 0
    for name, total, sha in FILES:
        try:
            got, etag = head_size(name)
        except Exception as e:                                     # noqa: BLE001
            log(f"[fail] preflight HEAD failed for {name}: {type(e).__name__}: {e}", logpath)
            return 2
        expect += total
        on_disk = os.path.getsize(os.path.join(DEST, name)) if os.path.exists(os.path.join(DEST, name)) else 0
        part_disk = os.path.getsize(os.path.join(DEST, name + ".part")) if os.path.exists(
            os.path.join(DEST, name + ".part")) else 0
        log(f"[preflight] {name}: HEAD size={got:,} etag={etag[:16]}... "
            f"(final={on_disk:,} part={part_disk:,})", logpath)
        if got and got != total:
            log(f"[fail] preflight: HEAD says {got:,} but {total:,} is expected - source changed?", logpath)
            return 2
        if etag and etag.lower() != sha:
            log(f"[warn] preflight: X-Linked-Etag {etag} != pinned sha {sha}", logpath)
    log(f"[preflight] total model bytes to have on disk: {expect/1e9:.2f} GB", logpath)
    if free_gb(DEST) < 3:
        log("[fail] destination drive has no free space", logpath)
        return 2

    t0 = time.time()
    for name, total, sha in FILES:
        if not fetch(name, total, sha, logpath):
            log(f"[fail] stopped at {name}", logpath)
            return 1
    log(f"[done] both shards complete in {(time.time()-t0)/60:.0f} min; "
        f"free_D={free_gb(DEST)} GB", logpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
