"""GraphMind 喂图：同步产出 txt → 本地校验 → 上传数据集 → 增量索引（③ 配套自动化）。

设计约定（2026-11-10，复用 2026-11-08 feed-graph.sh 已验证的管线语义）：
- 上传 POST /api/datasets/{id}/documents（20 个/请求分块），LightRAG 按内容哈希
  幂等去重，重复喂入自动跳过——本地 sha1 台账只是省流量的第一层。
- 索引 POST /api/datasets/{id}/index（增量，空 body），后端异步执行，默认只短轮询
  GRAPH_INDEX_POLL_S 秒即返回（索引可能跑数小时，绝不阻塞 sync 主流程）。
- 喂图前本地校验非空/可解码/大小上限（防上轮 Parsing failed 整轮报废）。
- 单文件失败隔离：一个坏文件不影响本批其余文件，更不影响下月。
- 数据集 ID 单点：creators.json `graph_dataset` 直接存完整 ID；新博主可存短名，
  首次喂图自动建数据集并把解析出的 ID 缓存到博主 data_dir/graph_feed_state.json。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from . import config

GRAPH_BASE = os.environ.get("DYSUB_GRAPH_BASE", "http://127.0.0.1:8777").rstrip("/")
UPLOAD_CHUNK = 20            # 每请求文件数（与 feed-graph.sh 一致）
MAX_TXT_BYTES = 1_000_000    # 单文件上限 1MB
MIN_TXT_CHARS = 30           # 喂图前非空校验：去空白后至少 30 字符
INDEX_POLL_S = int(os.environ.get("DYSUB_GRAPH_INDEX_POLL", "90"))
UPLOAD_TIMEOUT = 120
STATE_FILE = "graph_feed_state.json"


def _api(path: str, timeout: int = 30):
    req = urllib.request.Request(f"{GRAPH_BASE}{path}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _post_json(path: str, body: dict, timeout: int = 60):
    req = urllib.request.Request(
        f"{GRAPH_BASE}{path}", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def _post_files(path: str, files: list[Path], timeout: int = UPLOAD_TIMEOUT):
    """multipart/form-data 上传（stdlib 实现，不引入 requests）。"""
    boundary = f"----dysub{uuid.uuid4().hex}"
    buf = bytearray()
    for f in files:
        buf += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
                f"filename=\"{f.name}\"\r\nContent-Type: text/plain\r\n\r\n").encode("utf-8")
        buf += f.read_bytes()
        buf += b"\r\n"
    buf += f"--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(
        f"{GRAPH_BASE}{path}", data=bytes(buf), method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        return {"ok": False, "error": str(e)}


def sha1_of(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --- 状态（幂等台账，per-creator） ---

def _state_file(creator: dict) -> Path:
    return creator["data_dir"] / STATE_FILE


def _load_state(creator: dict) -> dict:
    sf = _state_file(creator)
    if sf.exists():
        try:
            return json.loads(sf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {}


def _save_state(creator: dict, st: dict) -> None:
    sf = _state_file(creator)
    sf.parent.mkdir(parents=True, exist_ok=True)
    tmp = sf.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, sf)


# --- 数据集解析：完整 ID 直用；短名首次自动建 + 缓存 ---

def _sanitize(name: str) -> str:
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in name)


def resolve_dataset(creator: dict, st: dict) -> tuple[str | None, dict]:
    """返回 (dataset_id, 更新后的 state)。失败返回 (None, state)。"""
    ds = creator.get("graph_dataset") or ""
    if not ds:
        return None, st
    # 已缓存且健康 → 直用
    cached = st.get("_dataset_id")
    if cached and cached.startswith(ds):
        info = _api(f"/api/datasets/{cached}", timeout=15)
        if info and isinstance(info, dict) and info.get("id"):
            return cached, st
    # 完整 ID 直接验证
    info = _api(f"/api/datasets/{ds}", timeout=15)
    if info and isinstance(info, dict) and info.get("id") == ds:
        st["_dataset_id"] = ds
        return ds, st
    # 短名 → 建数据集（后端 ID = sanitize(name)_hex6）
    created = _post_json("/api/datasets", {"name": ds}, timeout=30)
    if created and isinstance(created, dict) and created.get("id"):
        st["_dataset_id"] = created["id"]
        return created["id"], st
    return None, st


# --- 校验与喂图主流程 ---

def validate_txt(path: Path) -> tuple[bool, str]:
    """喂图前本地校验：存在/可解码/非空/大小上限（防 Parsing failed 整轮报废）。"""
    try:
        if not path.exists() or path.stat().st_size == 0:
            return False, "empty"
        if path.stat().st_size > MAX_TXT_BYTES:
            return False, f"too large ({path.stat().st_size}B)"
        text = path.read_text(encoding="utf-8")  # 严格解码，失败即隔离
    except (OSError, UnicodeDecodeError) as e:
        return False, f"unreadable: {e}"
    if len(text.strip()) < MIN_TXT_CHARS:
        return False, f"too short ({len(text.strip())} chars)"
    return True, ""


def pending_txts(creator: dict, max_n: int = 0) -> list[Path]:
    """asr_dir 里尚未喂过图的 txt（按 sha1 台账），最旧优先，max_n=0 不限。

    同一视频常有「数字名 + 可读名」两份同内容文件（sync 双输出），按内容 sha1
    去重，优先保留可读名（文档名在图谱里可读性更好）。
    """
    st = _load_state(creator)
    out: list[Path] = []
    seen_sha: set[str] = set()
    asr_dir = creator.get("asr_dir")
    if not asr_dir or not Path(asr_dir).is_dir():
        return out
    files = sorted(Path(asr_dir).glob("*.txt"),
                   key=lambda x: (x.stem.isdigit(), x.stat().st_mtime))  # 可读名优先，再按时间
    for p in files:
        s = sha1_of(p)
        if s in seen_sha:
            continue
        if st.get(s, {}).get("status") in ("fed", "quarantined"):
            seen_sha.add(s)
            continue
        out.append(p)
        seen_sha.add(s)
        if max_n and len(out) >= max_n:
            break
    return out


def feed_txts(creator: dict, txts: list[Path], poll_index: bool = True) -> dict:
    """喂一批 txt：校验→分块上传→触发增量索引→短轮询。失败隔离，不抛异常。"""
    res = {"fed": 0, "failed": 0, "quarantined": 0, "errors": [],
           "index_status": None, "dataset": None}
    if not txts:
        return res
    st = _load_state(creator)
    ds, st = resolve_dataset(creator, st)
    res["dataset"] = ds
    if not ds:
        res["errors"].append("dataset 不可用（后端未就绪或创建失败）")
        _save_state(creator, st)
        return res

    valid: list[Path] = []
    seen_sha: set[str] = set()
    for p in txts:
        ok, reason = validate_txt(p)
        s = sha1_of(p)
        if ok:
            if s in seen_sha or st.get(s, {}).get("status") == "fed":  # 同内容重复/已喂过（幂等）
                continue
            seen_sha.add(s)
            valid.append(p)
        else:
            res["quarantined"] += 1
            res["errors"].append(f"{p.name}: {reason}")
            st[s] = {"status": "quarantined", "file": p.name,
                     "reason": reason, "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # 分块上传，单请求失败只记该块，不打断整批
    for i in range(0, len(valid), UPLOAD_CHUNK):
        chunk = valid[i:i + UPLOAD_CHUNK]
        resp = _post_files(f"/api/datasets/{ds}/documents", chunk)
        if resp and resp.get("ok") is False:
            res["errors"].append(f"chunk {i // UPLOAD_CHUNK}: {resp.get('error', 'upload failed')[:120]}")
            continue  # 该块文件不标记，下轮重试
        for p in chunk:
            st[sha1_of(p)] = {"status": "fed", "file": p.name,
                              "ts": time.strftime("%Y-%m-%dT%H:%M:%S")}
            res["fed"] += 1

    _save_state(creator, st)

    # 触发增量索引（LightRAG 内容哈希幂等，重复文档自动跳过）
    if res["fed"]:
        idx = _post_json(f"/api/datasets/{ds}/index", {}, timeout=60)
        if poll_index:
            deadline = time.time() + INDEX_POLL_S
            terminal = ("idle", "complete", "completed", "success", "done",
                        "failed", "error", "cancel", "cancelled")
            while time.time() < deadline:
                stat = _api(f"/api/datasets/{ds}/index/status", timeout=15)
                if isinstance(stat, dict):
                    s = stat.get("status", "")
                    res["index_status"] = s
                    if s in terminal:
                        break
                time.sleep(15)
        elif isinstance(idx, dict):
            res["index_status"] = "triggered"
    return res
