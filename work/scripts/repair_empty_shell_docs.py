#!/usr/bin/env python3
"""Repair GraphMind "empty-shell processed" documents with a targeted re-feed.

Background: on 2026-11-13 two documents were marked ``processed`` with
``content_length=0`` / ``chunks_count=0`` because a failed insert was later
re-recorded as a duplicate (see the KB audit §2.5).  The file content is on
disk but absent from the index, so retrieval silently misses it.

The reliable repair (verified against ``backend/app/services/indexing_service.py``
and LightRAG 1.5.4 ``pipeline.py``) is:

1. stop the GraphMind service (the JSON storages must not be written while we
   edit them);
2. delete every ``doc_status`` record whose ``file_path`` equals the target
   filename -- both the empty ``doc-*`` record and its ``dup-*`` siblings,
   because LightRAG's filename dedup blocks a re-feed while ANY same-name
   record exists;
3. delete the target's entry from ``data/<dataset>/.indexed_files.json``
   (otherwise the sha256 skip check runs before the doc_status check);
4. restart the service and POST ``/api/datasets/<id>/index`` -- the scan
   re-processes just these files and skips the other ~936 by content hash;
5. verify ``status=processed``, ``content_length>0``, ``chunks_count>0`` and
   that the chunk rows exist in the KV + vector storage.

This script performs steps 2-3 with backups, and can verify step 5's result.
It only touches the documents listed in TARGETS; exact ``file_path`` match.

Usage::

    python3 work/scripts/repair_empty_shell_docs.py            # dry-run
    python3 work/scripts/repair_empty_shell_docs.py --apply    # requires service down
    python3 work/scripts/repair_empty_shell_docs.py --verify   # post-index checks
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
import time
from collections import Counter
from pathlib import Path

DATA_ROOT = Path(
    os.environ.get("GRAPHMIND_DATA_ROOT", "~/graphmind-replica/data")
).expanduser()
BACKUP_ROOT = Path(
    os.environ.get("GRAPHMIND_BACKUP_ROOT", "~/graphmind-replica/backups")
).expanduser()
API_HOST, API_PORT = "127.0.0.1", 8777

# dataset id -> exact input filename (file_path stored in doc_status)
TARGETS: dict[str, str] = {
    "jianghushu-methodology_b0607c": "20200602_推荐大家参照以下几条线思考：种子用户 势能 裂变.txt",
    "ligongzi_9c54ca": "20230622_地域优势，.txt",
}


def storage_dir(dataset: str) -> Path:
    return DATA_ROOT / dataset / "rag_storage" / dataset


def dump_json(path: Path, data: object) -> None:
    """Match LightRAG's ``write_json`` format exactly (indent=2, UTF-8)."""
    tmp = path.with_name(path.name + f".tmp-repair-{os.getpid()}")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def port_open(host: str = API_HOST, port: int = API_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def find_records(doc_status: dict, filename: str) -> list[tuple[str, dict]]:
    return [(doc_id, doc) for doc_id, doc in doc_status.items()
            if doc.get("file_path") == filename]


def chunk_ids_for(doc_id: str, doc_status: dict, text_chunks: dict) -> list[str]:
    doc = doc_status.get(doc_id) or {}
    listed = doc.get("chunks_list") or []
    if listed:
        return list(listed)
    return [chunk_id for chunk_id in text_chunks
            if str(chunk_id).startswith(f"{doc_id}-chunk-")]


def inspect(dataset: str, filename: str) -> dict:
    """Collect the pre-state facts we assert on at every step."""
    base = storage_dir(dataset)
    doc_status = load_json(base / "kv_store_doc_status.json")
    full_docs = load_json(base / "kv_store_full_docs.json")
    text_chunks = load_json(base / "kv_store_text_chunks.json")
    vdb_chunks = load_json(base / "vdb_chunks.json")
    vdb_rows = vdb_chunks.get("data", []) if isinstance(vdb_chunks, dict) else vdb_chunks
    hash_index = load_json(DATA_ROOT / dataset / ".indexed_files.json")

    records = find_records(doc_status, filename)
    empty = [doc_id for doc_id, doc in records
             if doc.get("status") == "processed"
             and int(doc.get("content_length") or 0) == 0
             and int(doc.get("chunks_count") or 0) == 0]
    real = [doc_id for doc_id, doc in records
            if doc.get("status") == "processed"
            and int(doc.get("content_length") or 0) > 0
            and int(doc.get("chunks_count") or 0) > 0]
    stale_ids = [doc_id for doc_id, _ in records]
    chunk_hits = [cid for doc_id in stale_ids
                  for cid in chunk_ids_for(doc_id, doc_status, text_chunks)]
    vdb_hits = [row.get("__id__") for row in vdb_rows
                if row.get("__id__") in set(chunk_hits)]
    full_docs_hits = [doc_id for doc_id in stale_ids if doc_id in full_docs]

    return {
        "dataset": dataset,
        "filename": filename,
        "record_count": len(doc_status),
        "status_counts": dict(Counter(doc.get("status") for doc in doc_status.values())),
        "records": [
            {
                "doc_id": doc_id,
                "status": doc.get("status"),
                "content_length": doc.get("content_length"),
                "chunks_count": doc.get("chunks_count"),
                "content_hash": doc.get("content_hash"),
                "is_duplicate": (doc.get("metadata") or {}).get("is_duplicate"),
            }
            for doc_id, doc in records
        ],
        "empty_ids": empty,
        "real_ids": real,
        "full_docs_hits": full_docs_hits,
        "chunk_hits": chunk_hits,
        "vdb_hits": vdb_hits,
        "hash_index_has_entry": filename in hash_index,
        "hash_index_count": len(hash_index),
        "all_chunk_rows": len(text_chunks),
        "all_vdb_rows": len(vdb_rows),
    }


def print_state(tag: str, state: dict) -> None:
    print(f"\n== {tag}: {state['dataset']} / {state['filename']}")
    print(f"   doc_status records: {state['record_count']} {state['status_counts']}")
    print(f"   records for file: {len(state['records'])}")
    for rec in state["records"]:
        print("     {doc_id}  status={status} len={content_length} chunks={chunks_count} "
              "hash={content_hash} dup={is_duplicate}".format(**rec))
    print(f"   empty shell ids: {state['empty_ids']}")
    print(f"   full_docs hits: {state['full_docs_hits'] or 'none'}")
    print(f"   text_chunk hits: {state['chunk_hits'] or 'none'}")
    print(f"   vdb hits: {state['vdb_hits'] or 'none'}")
    print(f"   .indexed_files entry: {state['hash_index_has_entry']} "
          f"(count={state['hash_index_count']})")


def assert_repairable(state: dict) -> bool:
    """Return True when the state is already clean, False when a repair is needed."""
    if not state["records"]:
        return True  # already repaired
    if len(state["real_ids"]) == 1 and not state["empty_ids"]:
        return True  # already repaired: one real processed record
    if len(state["empty_ids"]) != 1:
        raise SystemExit(
            f"expected exactly 1 empty processed record, got {state['empty_ids']}")
    if state["real_ids"]:
        raise SystemExit(
            "both an empty shell and a real processed record exist; manual review needed: "
            f"empty={state['empty_ids']} real={state['real_ids']}")
    if state["full_docs_hits"] or state["chunk_hits"] or state["vdb_hits"]:
        raise SystemExit(
            "stale index artifacts exist for the target doc_ids; refusing to delete "
            "doc_status without clearing chunks/graph first: "
            f"full_docs={state['full_docs_hits']} chunks={state['chunk_hits']} "
            f"vdb={state['vdb_hits']}")
    for rec in state["records"]:
        if rec["doc_id"] in state["empty_ids"]:
            continue
        if not rec["is_duplicate"]:
            raise SystemExit(f"unexpected non-duplicate record: {rec}")
    return False


def apply_repair(state: dict, backup_dir: Path) -> dict:
    dataset, filename = state["dataset"], state["filename"]
    base = storage_dir(dataset)
    doc_status_path = base / "kv_store_doc_status.json"
    hash_index_path = DATA_ROOT / dataset / ".indexed_files.json"

    already_clean = assert_repairable(state)
    if already_clean:
        if not state["records"] and state["hash_index_has_entry"]:
            # Half-applied state: rows were deleted but the sha256 entry was
            # left behind.  Drop it so the next scan re-feeds the file.
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(hash_index_path,
                         backup_dir / f"{dataset}__{hash_index_path.name}")
            hash_index = load_json(hash_index_path)
            hash_index.pop(filename, None)
            dump_json(hash_index_path, hash_index)
            print("   half-applied state: removed stale .indexed_files entry")
            return inspect(dataset, filename)
        print("   already repaired; no change")
        return state

    backup_dir.mkdir(parents=True, exist_ok=True)
    for src in (doc_status_path, hash_index_path):
        shutil.copy2(src, backup_dir / f"{dataset}__{src.name}")
    print(f"   backed up to {backup_dir}")

    doc_status = load_json(doc_status_path)
    removed = [doc_id for doc_id, doc in find_records(doc_status, filename)]
    for doc_id in removed:
        del doc_status[doc_id]
    if removed:
        dump_json(doc_status_path, doc_status)

    hash_index = load_json(hash_index_path)
    had_entry = filename in hash_index
    hash_index.pop(filename, None)
    if had_entry:
        dump_json(hash_index_path, hash_index)

    print(f"   removed doc_status rows: {removed}")
    print(f"   removed .indexed_files entry: {had_entry}")
    return inspect(dataset, filename)


def verify(state: dict) -> bool:
    ok = True
    checks = [
        (len(state["records"]) == 1, f"exactly 1 record for file (got {len(state['records'])})"),
        (not state["empty_ids"], f"no empty processed record (got {state['empty_ids']})"),
        (len(state["real_ids"]) == 1, f"1 real processed record (got {state['real_ids']})"),
        (bool(state["chunk_hits"]), f"text chunks present (got {len(state['chunk_hits'])})"),
        (bool(state["vdb_hits"]), f"vector rows present (got {len(state['vdb_hits'])})"),
        (state["hash_index_has_entry"], "re-indexed file is back in .indexed_files.json"),
    ]
    print(f"\n== verify: {state['dataset']} / {state['filename']}")
    for passed, label in checks:
        print(f"   [{'PASS' if passed else 'FAIL'}] {label}")
        ok = ok and passed
    if state["records"]:
        rec = state["records"][0]
        print(f"   record: {rec['doc_id']} len={rec['content_length']} "
              f"chunks={rec['chunks_count']} hash={rec['content_hash']}")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true",
                        help="edit doc_status + .indexed_files.json (service must be stopped)")
    parser.add_argument("--verify", action="store_true",
                        help="check the post-index state instead of repairing")
    parser.add_argument("--force", action="store_true",
                        help="allow --apply while port 8777 is open (NOT recommended)")
    args = parser.parse_args()

    if not DATA_ROOT.is_dir():
        print(f"data root not found: {DATA_ROOT}", file=sys.stderr)
        return 2

    states = [inspect(ds, fn) for ds, fn in TARGETS.items()]

    if args.verify:
        return 0 if all(verify(state) for state in states) else 1

    for state in states:
        print_state("pre", state)

    if not args.apply:
        for state in states:
            assert_repairable(state)
        print("\nDry-run only. Re-run with --apply after stopping the GraphMind service.")
        return 0

    if port_open() and not args.force:
        print(f"port {API_PORT} is still open; stop the service first "
              "(launchctl bootout gui/$(id -u)/com.huweixing.graphmind)", file=sys.stderr)
        return 2

    backup_dir = BACKUP_ROOT / time.strftime("empty-shell-repair-%Y%m%d-%H%M%S")
    for state in states:
        print_state("apply-before", state)
        after = apply_repair(state, backup_dir)
        print_state("apply-after", after)

    print(f"\nBackups: {backup_dir}")
    print("Next: restart the service and POST /api/datasets/<id>/index for both datasets,")
    print("then run this script with --verify.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
