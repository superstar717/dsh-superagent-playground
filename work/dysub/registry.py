"""博主注册表（creators.json）与目录布局。

creators.json 结构（slug → 条目）：
{
  "jianghushuo": {
    "name": "姜胡说",
    "sec_uid": "MS4wLjABAAAA...",
    "url": "https://www.douyin.com/user/MS4w...?from_tab_name=main",
    "asr_dir": "~/姜胡说/asr",          # 转写 txt 落盘目录（缺省 <data_dir>/asr）
    "kb_root": "~/姜胡说/kb_para",      # kb_para 项目根（缺省 None = 不自动入库）
    "kb_source": "asr",                # capture --source 标签（缺省 slug）
    "created": "2026-11-08T..."
  }
}
"""
import json
import re
import time
from pathlib import Path

from . import config

SEC_UID_RE = re.compile(r"douyin\.com/user/([A-Za-z0-9_-]{20,})")


def slugify(name: str) -> str:
    s = re.sub(r"\s+", "-", name.strip()).lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff_-]", "", s)
    return s or f"creator-{int(time.time())}"


def parse_creator_url(url: str):
    """从主页 URL 解析 sec_uid。返回 (sec_uid, 规范化 url) 或 (None, None)。"""
    m = SEC_UID_RE.search(url)
    if not m:
        return None, None
    sec_uid = m.group(1)
    canon = f"https://www.douyin.com/user/{sec_uid}?from_tab_name=main"
    return sec_uid, canon


def load_creators() -> dict:
    if not config.CREATORS_FILE.exists():
        return {}
    with open(config.CREATORS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_creators(creators: dict) -> None:
    config.CREATORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(config.CREATORS_FILE, "w", encoding="utf-8") as f:
        json.dump(creators, f, ensure_ascii=False, indent=2)
        f.write("\n")


def resolve(slug: str, entry: dict) -> dict:
    """补全条目的派生路径，返回带绝对 Path 的运行时视图。"""
    data_dir = Path(entry.get("data_dir") or (config.DATA_ROOT / slug)).expanduser()
    asr_dir = Path(entry.get("asr_dir") or (data_dir / "asr")).expanduser()
    kb_root = Path(entry["kb_root"]).expanduser() if entry.get("kb_root") else None
    return {
        "slug": slug,
        "name": entry.get("name") or slug,
        "sec_uid": entry.get("sec_uid", ""),
        "url": entry.get("url", ""),
        "data_dir": data_dir,
        "list_dir": data_dir / "list",
        "media_dir": data_dir / "media",
        "meta_dir": data_dir / "meta",
        "inbox_dir": data_dir / "inbox",   # 手动兜底 jsonl 放这里（策略 c）
        "ledger_file": data_dir / "ledger.jsonl",
        "asr_dir": asr_dir,
        "kb_root": kb_root,
        "kb_source": entry.get("kb_source") or slug,
        "graph_dataset": entry.get("graph_dataset", ""),  # GraphMind 数据集（完整 ID 或短名，空=不喂图）
        "created": entry.get("created", ""),
    }


def register(slug: str, name: str, sec_uid: str, url: str, *, asr_dir=None, kb_root=None,
             kb_source=None, creators=None) -> dict:
    creators = creators if creators is not None else load_creators()
    entry = {
        "name": name,
        "sec_uid": sec_uid,
        "url": url,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if asr_dir:
        entry["asr_dir"] = str(asr_dir)
    if kb_root:
        entry["kb_root"] = str(kb_root)
    if kb_source:
        entry["kb_source"] = kb_source
    creators[slug] = entry
    save_creators(creators)
    return resolve(slug, entry)
