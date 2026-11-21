#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""deck-ship — the sanctioned way to move a deck into a delivery directory.

Every gate must pass before a single byte is copied; a failed gate means exit 1 and the
destination is left untouched (no partial files, no half-updated delivery).

Gates
  1. deck-lint   : 0 FAIL on the source deck (slide count / bounds / overlap / fonts / notes)
  2. fonts       : every font used must be in --require-font (catches shipping a QA-only build)
  3. cite-check  : every number in --cite-draft must be FOUND in --source, or listed in
                   --cite-allow with a written reason (E136: MISSING numbers must not ship)

Then the deck (and any --companion files) is copied atomically and
<stem>.ship-manifest.json is written next to it with hashes, gate results and tool versions.

Usage
  deck-ship DECK DEST [--as NAME] [--companion FILE[:NAME] ...]
            [--expect N] [--min-notes N] [--allow-bleed] [--require-font NAME]...
            [--cite-draft FILE --source FILE ... [--cite-allow FILE]]
            [--verify-only | --dry-run] [--evidence-dir DIR] [--context FILE] [--json]

Modes
  (default)          run gates, copy, write manifest
  --verify-only      run gates, require DEST already holds identical files, (re)write manifest.
                     Files recorded by the previous manifest but not passed now are re-checked
                     against their recorded hashes (a deck-only verify never drops the PDF)
                     and DECK may equal the delivered file (adopting an existing delivery).
  --dry-run          run gates, print the plan, copy/write nothing

Exit codes
  0 SHIPPED / VERIFIED / WOULD-SHIP
  1 BLOCKED (a gate failed; destination unchanged)
  2 usage or I/O error
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

VERSION = "1.0.0"
HOME = os.path.expanduser("~")


# ----------------------------------------------------------------------------- helpers
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, timeout=900):
    try:
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", "not found: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, "", "timeout after %ss: %s" % (timeout, " ".join(cmd[:3]))
    except OSError as exc:
        return 126, "", "%s: %s" % (type(exc).__name__, exc)


def find_tool(env_name, default_path, plain_name):
    path = os.environ.get(env_name) or default_path
    if path and os.path.exists(path):
        return path
    return shutil.which(plain_name)


def tool_cmd(path):
    # Both deck-lint and cite-check are python entry scripts; run through sys.executable so
    # the gate never depends on the shebang line surviving an archive/CI checkout.
    return [sys.executable, path] if path.endswith(".py") else [path]


def human_mb(n):
    return "%.2f MB" % (n / 1e6)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


# ------------------------------------------------------------------------------ gates
def gate_lint(deck, opts):
    tool = find_tool("DECK_LINT", os.path.join(HOME, ".local/bin/deck-lint"), "deck-lint")
    result = {"tool": tool, "cmd": None, "ok": False, "exit": None, "report": None}
    if not tool:
        result["error"] = ("deck-lint not found (set $DECK_LINT or install "
                           "~/.local/bin/deck-lint)")
        return result
    cmd = tool_cmd(tool) + [deck, "--json"]
    if opts.allow_bleed:
        cmd.append("--allow-bleed")
    if opts.expect:
        cmd += ["--expect", str(opts.expect)]
    if opts.min_notes:
        cmd += ["--min-notes", str(opts.min_notes)]
    result["cmd"] = cmd
    rc, out, err = run(cmd)
    result["exit"] = rc
    try:
        report = json.loads(out)
    except ValueError:
        result["error"] = (("deck-lint produced no JSON (exit %s): " % rc) +
                           (err.strip() or out.strip())[:400])
        return result
    result["report"] = report
    fails = [f for f in report.get("findings", []) if f.get("level") == "FAIL"]
    result["fails"] = fails
    result["ok"] = rc == 0 and not fails
    return result


def gate_fonts(lint_report, required):
    used = list((lint_report or {}).get("stats", {}).get("fonts") or [])
    if not required:
        return {"ok": True, "used": used, "required": [], "extra": [], "absent": []}
    extra = [f for f in used if f not in required]
    absent = [f for f in required if f not in used]
    ok = not extra and not absent
    return {"ok": ok, "used": used, "required": list(required),
            "extra": extra, "absent": absent}


def parse_allow(path):
    """Allowlist lines are `key  # reason` (reason mandatory). Returns {key: reason}."""
    allow = {}
    errors = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue
            if "#" not in raw:
                errors.append("%s:%d missing '#' reason: %r" % (os.path.basename(path), n, raw))
                continue
            key, reason = raw.split("#", 1)
            key, reason = key.strip(), reason.strip()
            if not key or not reason:
                errors.append("%s:%d empty key or reason: %r" % (os.path.basename(path), n, raw))
                continue
            if key in allow:
                errors.append("%s:%d duplicate key %r" % (os.path.basename(path), n, key))
                continue
            allow[key] = reason
    return allow, errors


def gate_cite(draft, sources, allow_file):
    tool = find_tool("CITE_CHECK", os.path.join(HOME, ".local/bin/cite-check"), "cite-check")
    result = {"tool": tool, "ok": False, "report": None, "allowed": [],
              "blocking": [], "stale_allow": [], "error": None}
    if not tool:
        result["error"] = "cite-check not found (set $CITE_CHECK or install ~/.local/bin/cite-check)"
        return result
    cmd = tool_cmd(tool) + ["--json", "--draft", draft]
    for s in sources:
        cmd += ["--source", s]
    rc, out, err = run(cmd)
    try:
        report = json.loads(out)
    except ValueError:
        result["error"] = (("cite-check produced no JSON (exit %s): " % rc) +
                           (err.strip() or out.strip())[:400])
        return result
    result["report"] = report
    missing = [c for c in report.get("checked", []) if c.get("status") == "MISSING"]
    allow = {}
    if allow_file:
        allow, errors = parse_allow(allow_file)
        if errors:
            result["error"] = "bad cite allowlist: " + "; ".join(errors[:5])
            return result
    missing_keys = [c["key"] for c in missing]
    result["allowed"] = [{"key": k, "reason": allow[k]} for k in missing_keys if k in allow]
    result["blocking"] = [c for c in missing if c["key"] not in allow]
    result["stale_allow"] = [k for k in allow if k not in missing_keys]
    result["ok"] = not result["blocking"]
    return result


# ------------------------------------------------------------------------- ship action
def parse_companions(values):
    out = []
    for v in values:
        name = None
        if ":" in v:
            head, tail = v.rsplit(":", 1)
            # treat as PATH:NAME only when the tail can be a bare file name
            if tail and "/" not in tail and os.path.exists(head):
                v, name = head, tail
        out.append((v, name))
    return out


def plan_files(deck, dest, as_name, companions):
    items = [(deck, as_name or os.path.basename(deck), "deck")]
    for path, name in companions:
        if not os.path.isfile(path):
            raise SystemExit("companion not found: %s" % path)
        items.append((path, name or os.path.basename(path), "companion"))
    seen = set()
    for _, name, _ in items:
        if name in seen:
            raise SystemExit("duplicate destination file name: %s" % name)
        if os.sep in name or (os.altsep and os.altsep in name) or name in (".", ".."):
            raise SystemExit("destination file name must be a plain name: %r" % name)
        seen.add(name)
    return items


def perform_ship(items, dest, verify_only, dry_run, previous=None):
    results = []
    if not dry_run and not verify_only:
        os.makedirs(dest, exist_ok=True)
    for src, name, role in items:
        src = os.path.abspath(src)
        dst = os.path.join(dest, name)
        src_hash, src_size = sha256(src), os.path.getsize(src)
        rec = {"name": name, "role": role, "source": src, "dest": dst,
               "sha256": src_hash, "bytes": src_size, "action": None, "previous_sha256": None}
        if verify_only:
            if src == os.path.abspath(dst):
                # adopting the already-delivered artifact: gates ran on this exact file
                rec["action"] = "verified"
                rec["dest_sha256"] = src_hash
                results.append(rec)
                continue
            if not os.path.isfile(dst):
                rec["action"] = "missing"
                results.append(rec)
                continue
            dst_hash = sha256(dst)
            rec["action"] = "verified" if dst_hash == src_hash else "MISMATCH"
            rec["dest_sha256"] = dst_hash
        elif dry_run:
            rec["action"] = "would-copy"
            if os.path.isfile(dst):
                rec["previous_sha256"] = sha256(dst)
        else:
            tmp = os.path.join(dest, ".%s.tmp.%d" % (name, os.getpid()))
            try:
                shutil.copyfile(src, tmp)
                with open(tmp, "rb") as fh:
                    os.fsync(fh.fileno())
                if sha256(tmp) != src_hash:
                    raise IOError("copy hash mismatch for %s" % name)
                if os.path.isfile(dst):
                    rec["previous_sha256"] = sha256(dst)
                os.replace(tmp, dst)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            final = sha256(dst)
            rec["dest_sha256"] = final
            rec["action"] = "copied" if final == src_hash else "CORRUPT"
        results.append(rec)

    # --verify-only with a subset (e.g. only the deck) must not silently drop the other
    # files a previous manifest recorded: verify them against their recorded hashes.
    if verify_only and previous:
        provided = {r["name"] for r in results}
        for old in previous.get("files", []):
            name = old.get("name")
            if not name or name in provided:
                continue
            path = os.path.join(dest, name)
            rec = {"name": name, "role": old.get("role", "companion"),
                   "source": old.get("source"), "dest": path,
                   "sha256": old.get("sha256"), "bytes": old.get("bytes"),
                   "action": None, "dest_sha256": None}
            if not os.path.isfile(path):
                rec["action"] = "MISSING"
            else:
                digest = sha256(path)
                rec["dest_sha256"] = digest
                rec["action"] = "kept" if digest == old.get("sha256") else "CHANGED"
            results.append(rec)
    return results


def write_evidence(evidence_dir, lint, cite):
    os.makedirs(evidence_dir, exist_ok=True)
    files = []
    if lint.get("report"):
        path = os.path.join(evidence_dir, "deck-lint.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(lint["report"], f, ensure_ascii=False, indent=2)
        files.append({"name": os.path.basename(path), "sha256": sha256(path)})
    if cite.get("report"):
        path = os.path.join(evidence_dir, "cite-check.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cite["report"], f, ensure_ascii=False, indent=2)
        files.append({"name": os.path.basename(path), "sha256": sha256(path)})
    return files


def print_blocked(lint, fonts, cite, dest):
    print("deck-ship: BLOCKED")
    if lint is not None:
        if lint.get("error"):
            print("  lint: ERROR %s" % lint["error"])
        else:
            rep = lint["report"]
            fails = lint.get("fails", [])
            print("  lint: %d fail / %d warn  (%s slides)"
                  % (len(fails), len(rep.get("findings", [])) - len(fails), rep.get("slides")))
            for f in fails:
                loc = "p%s" % f.get("slide") if f.get("slide") else "-"
                print("    FAIL %-6s %-14s %s" % (loc, f.get("code"), f.get("msg")))
    if fonts is not None and not fonts.get("ok"):
        print("  fonts: required %s, used %s (extra=%s, absent=%s)"
              % (fonts.get("required"), fonts.get("used"), fonts.get("extra"), fonts.get("absent")))
    if cite is not None:
        if cite.get("error"):
            print("  cite: ERROR %s" % cite["error"])
        else:
            rep = cite["report"]
            print("  cite: %d claims, %d MISSING (%d allowlisted, %d blocking)"
                  % (rep.get("total", 0), rep.get("n_missing", 0),
                     len(cite.get("allowed", [])), len(cite.get("blocking", []))))
            for c in cite.get("blocking", [])[:20]:
                print("    MISSING %-10s <- %s" % (c.get("key"), c.get("ctx", "")[:70]))
    if dest:
        print("  destination unchanged: %s" % dest)


def main(argv):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("deck")
    ap.add_argument("dest")
    ap.add_argument("--as", dest="as_name")
    ap.add_argument("--companion", action="append", default=[])
    ap.add_argument("--expect", type=int)
    ap.add_argument("--min-notes", type=int, dest="min_notes")
    ap.add_argument("--allow-bleed", action="store_true", dest="allow_bleed")
    ap.add_argument("--require-font", action="append", default=[], dest="require_font")
    ap.add_argument("--cite-draft", dest="cite_draft")
    ap.add_argument("--source", action="append", default=[])
    ap.add_argument("--cite-allow", dest="cite_allow")
    ap.add_argument("--verify-only", action="store_true", dest="verify_only")
    ap.add_argument("--dry-run", action="store_true", dest="dry_run")
    ap.add_argument("--evidence-dir", dest="evidence_dir")
    ap.add_argument("--context")
    ap.add_argument("--json", action="store_true")
    opts = ap.parse_args(argv[1:])

    deck = os.path.abspath(opts.deck)
    dest = os.path.abspath(opts.dest)
    emit_json = opts.json

    def bail(msg, code=2):
        if emit_json:
            print(json.dumps({"status": "ERROR", "error": msg}, ensure_ascii=False))
        else:
            print("deck-ship: ERROR %s" % msg, file=sys.stderr)
        return code

    if not os.path.isfile(deck):
        return bail("deck not found: %s" % deck)
    if opts.cite_draft and not opts.source:
        return bail("--cite-draft requires at least one --source")
    if opts.cite_draft and not os.path.isfile(opts.cite_draft):
        return bail("cite draft not found: %s" % opts.cite_draft)
    for s in opts.source:
        if not os.path.isfile(s):
            return bail("cite source not found: %s" % s)
    if opts.cite_allow and not os.path.isfile(opts.cite_allow):
        return bail("cite allowlist not found: %s" % opts.cite_allow)
    try:
        items = plan_files(deck, dest, opts.as_name, parse_companions(opts.companion))
    except SystemExit as exc:
        return bail(str(exc))

    lint = gate_lint(deck, opts)
    fonts = gate_fonts(lint.get("report"), opts.require_font)
    cite = gate_cite(opts.cite_draft, opts.source, opts.cite_allow) if opts.cite_draft else None

    gates_ok = bool(lint.get("ok")) and bool(fonts.get("ok")) and (cite is None or cite["ok"])
    result = {"tool": "deck-ship", "version": VERSION, "at": now_iso(), "deck": deck,
              "dest": dest, "mode": "verify" if opts.verify_only else
                                   ("dry-run" if opts.dry_run else "ship"),
              "gates_ok": gates_ok}

    if not gates_ok:
        result["status"] = "BLOCKED"
        result["lint"] = {"ok": lint.get("ok"), "error": lint.get("error"),
                          "fail": len(lint.get("fails", [])), "exit": lint.get("exit")}
        result["fonts"] = fonts
        if cite is not None:
            result["cite"] = {"ok": cite["ok"], "error": cite.get("error"),
                              "blocking": [c.get("key") for c in cite.get("blocking", [])],
                              "allowed": [a["key"] for a in cite.get("allowed", [])]}
        if emit_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print_blocked(lint, fonts if opts.require_font else None, cite, dest)
        return 1

    previous = None
    if opts.verify_only:
        manifest_name = os.path.splitext(items[0][1])[0] + ".ship-manifest.json"
        manifest_path = os.path.join(dest, manifest_name)
        if os.path.isfile(manifest_path):
            try:
                with open(manifest_path, encoding="utf-8") as fh:
                    previous = json.load(fh)
            except (OSError, ValueError):
                previous = None

    try:
        files = perform_ship(items, dest, opts.verify_only, opts.dry_run, previous)
    except SystemExit as exc:
        return bail(str(exc))
    except OSError as exc:
        return bail("%s: %s" % (type(exc).__name__, exc), code=2)
    bad = [f for f in files if f["action"] in ("MISSING", "MISMATCH", "CHANGED", "CORRUPT")]
    if bad:
        if emit_json:
            print(json.dumps({"status": "BLOCKED", "files": files}, ensure_ascii=False, indent=2))
        else:
            print("deck-ship: BLOCKED — %d file(s) failed verification" % len(bad))
            for f in bad:
                print("  %-9s %s" % (f["action"], f["name"]))
            print("  destination unchanged: %s" % dest)
        return 1

    if opts.verify_only:
        status = "VERIFIED"
    elif opts.dry_run:
        status = "WOULD-SHIP"
    else:
        status = "SHIPPED"

    lint_rep = lint.get("report") or {}
    n_fail = len(lint.get("fails", []))
    n_warn = len([f for f in lint_rep.get("findings", []) if f.get("level") == "WARN"])
    manifest = {
        "tool": "deck-ship", "version": VERSION, "status": status, "at": now_iso(),
        "source": {"deck": deck, "bytes": os.path.getsize(deck), "sha256": sha256(deck)},
        "dest": dest,
        "files": files,
        "lint": {
            "tool": lint.get("tool"), "exit": lint.get("exit"),
            "slides": lint_rep.get("slides"), "size_in": lint_rep.get("size_in"),
            "fail": n_fail, "warn": n_warn,
            "findings": lint_rep.get("findings", []),
            "stats": lint_rep.get("stats", {}),
        },
        "fonts": fonts,
        "cite": None,
        "context": None,
        "evidence": [],
    }
    if cite is not None:
        cite_rep = cite.get("report") or {}
        manifest["cite"] = {
            "tool": cite.get("tool"),
            "draft": {"path": opts.cite_draft, "sha256": sha256(opts.cite_draft)},
            "sources": cite_rep.get("sources", []),
            "total": cite_rep.get("total"),
            "found": cite_rep.get("total", 0) - cite_rep.get("n_missing", 0),
            "missing": cite_rep.get("n_missing"),
            "allowed": cite.get("allowed", []),
            "stale_allow": cite.get("stale_allow", []),
        }
    if opts.context:
        with open(opts.context, encoding="utf-8") as f:
            manifest["context"] = json.load(f)
    if opts.evidence_dir:
        manifest["evidence"] = write_evidence(opts.evidence_dir, lint, cite or {})

    manifest_name = os.path.splitext(os.path.basename(items[0][1]))[0] + ".ship-manifest.json"
    manifest_path = os.path.join(dest, manifest_name)
    if not opts.dry_run:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    result.update({"status": status, "files": files,
                   "manifest": None if opts.dry_run else manifest_path,
                   "lint": {"fail": n_fail, "warn": n_warn, "slides": lint_rep.get("slides")},
                   "fonts": fonts})
    if cite is not None:
        result["cite"] = {"total": cite["report"]["total"],
                          "missing": cite["report"]["n_missing"],
                          "allowed": [a["key"] for a in cite.get("allowed", [])],
                          "stale_allow": cite.get("stale_allow", [])}

    if emit_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        verb = {"SHIPPED": "SHIPPED", "VERIFIED": "VERIFIED",
                "WOULD-SHIP": "WOULD SHIP"}[status]
        print("deck-ship: %s — %d file(s) at %s" % (verb, len(files), dest))
        for f in files:
            extra = ""
            if f.get("previous_sha256") and f["previous_sha256"] != f["sha256"]:
                extra = "  (replaced %s…)" % f["previous_sha256"][:10]
            print("  %-9s %-12s %-60s %s%s"
                  % (f["role"], f["action"], f["name"], human_mb(f["bytes"]), extra))
        print("  lint: %d fail / %d warn  (%s slides)" % (n_fail, n_warn, lint_rep.get("slides")))
        if opts.require_font:
            print("  fonts: %s (required %s)" % (fonts["used"], fonts["required"]))
        if cite is not None:
            print("  cite: %d claims, %d allowed, 0 blocking%s"
                  % (cite["report"]["total"], len(cite.get("allowed", [])),
                     (" (stale allowlist entries: %s)" % cite["stale_allow"])
                     if cite.get("stale_allow") else ""))
        if opts.dry_run:
            print("  dry-run: nothing copied, no manifest written")
        else:
            print("  manifest: %s" % manifest_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
