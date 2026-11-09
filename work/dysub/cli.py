"""dysub 命令行入口：add / sync / status / doctor / ingest / asr / feed-graph"""
import argparse
import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from . import asr, browser, config, graph_feed, kb_ingest, ledger, list_fetch, probe, registry


def eprint(*a):
    print(*a, flush=True, file=sys.stderr)


# ---------- 锁 ----------

def acquire_lock() -> bool:
    config.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    lf = config.LOCK_FILE
    if lf.exists():
        try:
            pid = int(lf.read_text().strip() or 0)
            os.kill(pid, 0)
            eprint(f"[LOCK] 另一个 sync 正在运行 (pid {pid})，退出")
            return False
        except (ValueError, ProcessLookupError, PermissionError, OSError):
            pass  # 陈旧锁，接管
    lf.write_text(str(os.getpid()))
    return True


def release_lock():
    try:
        config.LOCK_FILE.unlink()
    except OSError:
        pass


# ---------- add ----------

def cmd_add(args):
    sec_uid, canon = registry.parse_creator_url(args.url)
    if not sec_uid:
        sys.exit(f"无法从 URL 解析 sec_uid（需要形如 https://www.douyin.com/user/MS4wLjAB...）：{args.url}")
    creators = registry.load_creators()
    slug = args.slug or registry.slugify(args.name or sec_uid[:16])
    name = args.name
    if not args.dry_run:
        if not name:
            if not browser.ensure_chrome():
                eprint("[ADD] 专用 Chrome 不可用，昵称抓取跳过（用 --name 指定）")
            else:
                name = asyncio.run(browser.fetch_nickname(canon)) or None
        name = name or slug
    if args.dry_run:
        print(json.dumps({"dry_run": True, "slug": slug, "sec_uid": sec_uid,
                          "url": canon, "name": name or "(将由 CDP 抓取昵称)"},
                         ensure_ascii=False, indent=1))
        return
    if slug in creators and not args.force:
        sys.exit(f"博主已注册：{slug}（--force 覆盖）")
    c = registry.register(slug, name, sec_uid, canon, asr_dir=args.asr_dir,
                          kb_root=args.kb_root, kb_source=args.kb_source, creators=creators)
    for d in (c["data_dir"], c["inbox_dir"]):
        d.mkdir(parents=True, exist_ok=True)
    print(json.dumps({"registered": slug, "name": name, "url": canon,
                      "data_dir": str(c["data_dir"]), "asr_dir": str(c["asr_dir"]),
                      "kb_root": str(c["kb_root"]) if c["kb_root"] else None},
                     ensure_ascii=False, indent=1))


# ---------- sync ----------

async def sync_one(creator: dict, args) -> dict:
    from . import downloader
    slug = creator["slug"]
    print(f"\n===== {creator['name']}（{slug}）=====", flush=True)
    summary = {"slug": slug, "new": 0, "downloaded": 0, "asr": 0, "ingested": 0,
               "failed": 0, "skipped": 0}

    # 0. --month 解析：逗号分隔 YYYY-MM → [(y, m), ...]（主页日期筛选按月确定性抓取）
    months = None
    if getattr(args, "month", None):
        try:
            months = [tuple(map(int, m.split("-"))) for m in args.month.split(",")]
            assert all(len(t) == 2 and 1 <= t[1] <= 12 for t in months)
        except (ValueError, AssertionError):
            sys.exit(f"--month 格式应为 YYYY-MM 或逗号分隔的多个，如 2025-01,2025-02：{args.month}")
        print(f"[SYNC] 按月确定性抓取：{[f'{y}-{m:02d}' for y, m in months]}", flush=True)

    # 1. 浏览器与登录态（一次性取登录检查 + cookies 导出）
    if not browser.ensure_chrome():
        raise RuntimeError("专用 Chrome 不可用（检查 CHROME_BIN / CHROME_PROFILE）")
    cookies_json = None
    b, own = await browser.connect()
    try:
        login = await browser.login_state(b.contexts[0])
        if login["logged_in"] and config.USE_MEDIACRAWLER:
            cookies_json = str(config.DATA_ROOT / "cookies_mc.json")
            await browser.dump_cookies_json(b.contexts[0], cookies_json)
    finally:
        await b.close()
        if own:
            await browser.pw_stop(own)
    if not login["logged_in"]:
        if config.HEADLESS:
            # 无头实例弹不了扫码窗——切回有头窗口供扫码，本次失败下次重试
            browser._relaunch_headed_for_login()
        login_hint = (f"dysub：{creator['name']} 的抖音登录态已失效，每日自动同步无法执行。"
                      f"请在 Mac 上打开专用 Chrome（profile：{config.CHROME_PROFILE}）扫码登录。")
        browser.notify(f"{creator['name']}：抖音登录态失效，请在弹出的专用 Chrome 窗口扫码", "dysub")
        browser.feishu_notify(login_hint)
        raise RuntimeError("抖音未登录：请在专用 Chrome（profile " + str(config.CHROME_PROFILE) +
                           "）扫码登录后重试（退出码 2）")

    # 2. 列表（策略链）
    rows, strategy = await list_fetch.fetch(creator, cookies_json, months=months)
    if args.since:
        before = len(rows)
        rows = list_fetch.filter_since(rows, args.since)
        print(f"[SYNC] --since {args.since}: {before} → {len(rows)} 条", flush=True)
    # 抖音风控会让列表深度波动（实测同 URL 65 条/8 条往返），显著缩水时提示
    latest = creator["list_dir"] / "latest.jsonl"
    prev_count = sum(1 for l in (latest.read_text(encoding="utf-8").splitlines() if latest.exists() else []) if l.strip())
    list_fetch.save_list(creator, rows, strategy)
    print(f"[SYNC] 列表策略={strategy}，共 {len(rows)} 条", flush=True)
    if prev_count and len(rows) < max(3, int(prev_count * 0.5)):
        eprint(f"[SYNC-WARN] 本次列表仅 {len(rows)} 条，上一份为 {prev_count} 条"
               f"——可能被抖音风控降级，稍后重跑 sync 可补齐")

    # 3. 增量筛选
    state = ledger.load_state(creator["ledger_file"])
    done = ledger.done_ids(creator["ledger_file"])
    todo = [r for r in rows if r.get("aweme_id") and r["aweme_id"] not in done]
    for r in todo:
        ledger.append(creator["ledger_file"], {"aweme_id": r["aweme_id"],
                                               "stage": "listed", "title": r.get("title", "")})
    print(f"[SYNC] 已入库 {len(done)} 条，本轮待处理 {len(todo)} 条", flush=True)
    summary["new"] = len(todo)
    if args.limit and len(todo) > args.limit:
        todo = todo[:args.limit]
        print(f"[SYNC] --limit 截断为 {len(todo)} 条", flush=True)

    # 4. 下载
    if todo:
        dl = await downloader.download_pending(creator, todo, ledger.load_state(creator["ledger_file"]))
        summary["downloaded"] = dl["downloaded"]
        summary["failed"] = dl["failed"]
        summary["skipped"] = dl["skipped"]

    # 5. 转写
    state = ledger.load_state(creator["ledger_file"])
    manifest = asr.build_manifest(creator, rows, state)
    if manifest:
        print(f"[SYNC] 待转写 {len(manifest)} 条，启动 SenseVoice（独立进程）", flush=True)
        res = asr.run_asr(manifest)
        readable = {o["aweme_id"]: o["out"] for o in res["outputs"]}
        for o in res["outputs"]:
            ledger.append(creator["ledger_file"], {
                "aweme_id": o["aweme_id"], "stage": "asr_done",
                "out_txt": o["out"], "chars": o.get("chars", 0)})
        for err in res["errors"]:
            ledger.append(creator["ledger_file"], {"aweme_id": err["aweme_id"],
                                                   "stage": "asr_failed", "error": err["error"]})
        summary["asr"] = res["done"]
        summary["failed"] += res["failed"]
    else:
        readable = {}

    # 6. 入知识库（本轮产出的可读命名 txt）
    if not args.no_ingest and creator["kb_root"] is not None and readable:
        txts = [p for p in readable.values() if not Path(p).stem.isdigit()]
        if txts:
            kres = kb_ingest.ingest_txts(creator, txts)
            summary["ingested"] = kres["ingested"]
            for err in kres["errors"]:
                eprint(f"[KB-ERR] {err['file']}: {err['error']}")
            for aid, p in readable.items():
                if Path(p).stem.isdigit():
                    continue
                ledger.append(creator["ledger_file"], {"aweme_id": aid,
                                                       "stage": "ingested", "out_txt": p})

    # 6.5 喂图（GraphMind 文档上传 + 增量索引；失败隔离，不阻塞同步主流程）
    if not args.no_graph and creator.get("graph_dataset") and readable:
        try:
            txts_all = list(readable.values())
            gres = graph_feed.feed_txts(creator, txts_all)
            summary["graph_fed"] = gres["fed"]
            summary["graph_quarantined"] = gres["quarantined"]
            if gres["errors"]:
                for err in gres["errors"][:5]:
                    eprint(f"[GRAPH-ERR] {err}")
            if gres["index_status"]:
                print(f"[GRAPH] 索引状态: {gres['index_status']}（+{gres['fed']} 篇 → {gres['dataset']}）", flush=True)
        except Exception as e:  # 喂图任何异常都不影响同步结果
            eprint(f"[GRAPH-ERR] {e!r}")

    # 7. 清理媒体（默认转写成功即删 mp4 释放磁盘；--keep-media 可保留）
    if not args.keep_media and readable:
        freed = 0
        for aid in readable:
            p = creator["media_dir"] / f"{aid}.mp4"
            try:
                freed += p.stat().st_size
                p.unlink(missing_ok=True)
            except OSError:
                pass
        if freed:
            print(f"[CLEAN] 已删除 {len(readable)} 个已转写 mp4，释放 {freed // 1048576}MB", flush=True)

    ls = ledger.summary(creator["ledger_file"])
    print(f"[SYNC] {creator['name']} 结果：新 {summary['new']} / 下载 {summary['downloaded']} / "
          f"转写 {summary['asr']} / 入库 {summary['ingested']} / 失败 {summary['failed']} / "
          f"外来跳过 {summary.get('foreign', 0)}; "
          f"台账累计 done={ls['done']} pending={ls['pending']} foreign={ls['foreign']} "
          f"failed={ls['failed']}", flush=True)
    # 有产出或有失败的夜晚也发飞书结果摘要；完全无变化的夜晚不发（防噪音）。
    # 连续多晚既无消息又无新内容时，应主动跑 dysub status 核查定时任务本身。
    if summary["new"] or summary["asr"] or summary["failed"]:
        digest = (f"{creator['name']} 同步结果：新 {summary['new']}，转写 {summary['asr']}，"
                  f"入库 {summary['ingested']}，外来拦截 {ls.get('foreign', 0)}，失败 {summary['failed']}")
        browser.notify(digest, "dysub")
        browser.feishu_notify(digest)
    return summary


def cmd_sync(args):
    creators = registry.load_creators()
    if not creators:
        sys.exit("尚无注册博主，先 dysub add <主页URL>")
    if args.all:
        slugs = list(creators)
    elif args.names:
        slugs = []
        for n in args.names:
            if n in creators:
                slugs.append(n)
            else:
                matches = [s for s, e in creators.items()
                           if creators[s].get("name") == n or s.startswith(n)]
                if not matches:
                    sys.exit(f"未注册博主：{n}（已注册：{', '.join(creators)}）")
                slugs.extend(matches)
    else:
        sys.exit("指定博主名或 --all（已注册：" + ", ".join(creators) + "）")

    if not probe.gate():
        sys.exit(3)
    if not acquire_lock():
        sys.exit(5)
    results = []
    code = 0
    try:
        for slug in slugs:
            c = registry.resolve(slug, creators[slug])
            try:
                results.append(asyncio.run(sync_one(c, args)))
            except RuntimeError as e:
                code = 2 if "未登录" in str(e) else 1
                eprint(f"[SYNC-FAIL] {slug}: {e}")
                browser.notify(f"{slug} 同步失败：{str(e)[:80]}", "dysub")
                if "未登录" not in str(e):  # 登录失效已在 sync_one 内发过飞书提醒，不重复
                    browser.feishu_notify(f"dysub：{slug} 同步失败——{str(e)[:120]}\n"
                                          f"排查：bin/dysub doctor；日志：~/.local/share/dysub/logs/")
                results.append({"slug": slug, "error": str(e)[:120]})
    finally:
        release_lock()
    print("\n===== 汇总 =====")
    print(json.dumps(results, ensure_ascii=False, indent=1))
    sys.exit(code)


# ---------- status ----------

def cmd_status(args):
    creators = registry.load_creators()
    if not creators:
        sys.exit("尚无注册博主，先 dysub add <主页URL>")
    slugs = args.names or list(creators)
    rows = []
    for slug in slugs:
        if slug not in creators:
            matches = [s for s in creators if s.startswith(slug) or creators[s].get("name") == slug]
            if not matches:
                sys.exit(f"未注册博主：{slug}")
            slug = matches[0]
        c = registry.resolve(slug, creators[slug])
        s = ledger.summary(c["ledger_file"])
        state = ledger.load_state(c["ledger_file"])
        last = max((v.get("last_ts") or v.get("first_ts") or "" for v in state.values()), default="")
        s.update({"slug": slug, "name": c["name"], "last_sync": last,
                  "asr_dir": str(c["asr_dir"]),
                  "kb_pending": len(kb_ingest.pending_txts(c)) if c["kb_root"] else None})
        rows.append(s)
    print(json.dumps(rows, ensure_ascii=False, indent=1))


# ---------- ingest ----------

def cmd_ingest(args):
    creators = registry.load_creators()
    slug = args.name
    if slug not in creators:
        matches = [s for s in creators if s.startswith(slug) or creators[s].get("name") == slug]
        if not matches:
            sys.exit(f"未注册博主：{slug}")
        slug = matches[0]
    c = registry.resolve(slug, creators[slug])
    if c["kb_root"] is None:
        sys.exit(f"博主 {slug} 未配置 kb_root，无法入库")
    if args.dir:
        txts = [p for p in sorted(Path(args.dir).expanduser().glob("*.txt"))
                if not p.stem.isdigit()]
    elif args.all:
        txts = kb_ingest.pending_txts(c)
    else:
        sys.exit("指定 --dir <目录> 或 --all（扫 asr_dir 中未入库文件）")
    print(f"[INGEST] 待入库 {len(txts)} 个 txt → {c['kb_root']}")
    res = kb_ingest.ingest_txts(c, txts)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    if res["errors"]:
        sys.exit(1)


# ---------- asr ----------

def cmd_asr(args):
    """单文件快速转写（不走下载/台账）。"""
    media = Path(args.media).expanduser().resolve()
    if not media.exists():
        sys.exit(f"文件不存在：{media}")
    out_dir = str(media.parent)
    row = {"aweme_id": media.stem, "media": str(media), "title": media.stem,
           "create_time": None, "out_dir": out_dir}
    res = asr.run_asr([row])
    if res["done"]:
        # worker 断点续传可能命中已有 {stem}.txt（如历史批次的旧转写），两个候选取存在的
        for o in res["outputs"]:
            for cand in (o["out"], o.get("out_id")):
                if cand and Path(cand).exists():
                    print(f"已转写 → {cand}")
                    print(Path(cand).read_text(encoding="utf-8")[:500])
                    return
        sys.exit(f"转写完成但输出文件缺失：{res['outputs']}")
    sys.exit(f"转写失败：{res['errors']}")


# ---------- feed-graph ----------

def cmd_feed_graph(args):
    """补喂：扫 asr_dir 未喂图的 txt（幂等台账），分批上传 GraphMind 并触发索引。

    用于：①已跑完的回填月份补喂 ②同步轮里喂图失败后的重试。
    单次最多 --max 个（launchd 每晚排队消化，失败自动隔离不串批）。
    """
    creators = registry.load_creators()
    slug = args.name
    if slug not in creators:
        matches = [s for s in creators if s.startswith(slug) or creators[s].get("name") == slug]
        if not matches:
            sys.exit(f"未注册博主：{slug}")
        slug = matches[0]
    entry = creators[slug]
    if not entry.get("graph_dataset"):
        sys.exit(f"博主 {slug} 未配置 graph_dataset，无法喂图")
    c = registry.resolve(slug, entry)
    txts = graph_feed.pending_txts(c, max_n=args.max or 0)
    if args.dry_run:
        print(f"[DRY] {c['name']} 待喂 {len(txts)} 个 txt → {entry['graph_dataset']}")
        for p in txts[:10]:
            print(f"  - {p.name}")
        return
    if not txts:
        print(f"[FEED] {c['name']} 无待喂 txt")
        return
    print(f"[FEED] {c['name']} 待喂 {len(txts)} 个 txt → {entry['graph_dataset']}", flush=True)
    res = graph_feed.feed_txts(c, txts)
    print(json.dumps({k: v for k, v in res.items() if k != "errors"}, ensure_ascii=False))
    for err in res["errors"][:10]:
        eprint(f"[FEED-ERR] {err}")
    # 有产出或有问题都发飞书摘要，完全无变化不发（防噪音）
    if res["fed"] or res["errors"]:
        browser.feishu_notify(
            f"dysub 喂图：{c['name']} +{res['fed']} 篇 → {res['dataset']}，"
            f"索引 {res.get('index_status') or '已触发'}，隔离 {res['quarantined']}，错误 {len(res['errors'])}")


# ---------- doctor ----------

def _check(label, ok, detail=""):
    mark = "✓" if ok else "✗"
    print(f"  {mark} {label}" + (f" — {detail}" if detail else ""), flush=True)
    return ok


def cmd_doctor(args):
    import subprocess as sp
    ok = True
    print("== dysub doctor ==")
    ok &= _check("包目录", config.DYSUB_HOME.is_dir(), str(config.DYSUB_HOME))
    ok &= _check("creators.json", config.CREATORS_FILE.exists(),
                 f"{len(registry.load_creators())} 个博主" if config.CREATORS_FILE.exists() else "未注册博主")
    ok &= _check("Chrome 专用 profile", config.CHROME_PROFILE.is_dir(), str(config.CHROME_PROFILE))
    ok &= _check("Chrome 可执行", Path(config.CHROME_BIN).exists(), config.CHROME_BIN)

    import socket
    with socket.socket() as s:
        s.settimeout(1.0)
        try:
            s.connect(("127.0.0.1", config.CDP_PORT))
            cdp_up = True
        except OSError:
            cdp_up = False
    ok &= _check("CDP 端口（未开时 sync 会自动拉起）", True,
                 f"127.0.0.1:{config.CDP_PORT} " + ("在线" if cdp_up else "离线"))
    if cdp_up:
        async def _login():
            b, own = await browser.connect()
            try:
                return await browser.login_state(b.contexts[0])
            finally:
                await b.close()
                if own:
                    await browser.pw_stop(own)
        try:
            login = asyncio.run(_login())
            ok &= _check("抖音登录态", login["logged_in"],
                         f"{login['cookie_count']} cookies" + ("" if login["logged_in"] else "（请在专用 Chrome 扫码）"))
        except Exception as e:
            ok &= _check("CDP 连接", False, f"{type(e).__name__}: {str(e)[:80]}")

    def _py(python, module, timeout=90):
        try:
            return sp.run([str(python), "-c", f"import {module}"],
                          capture_output=True, timeout=timeout).returncode == 0
        except sp.TimeoutExpired:
            return False

    ok &= _check("列表/下载解释器", Path(config.BROWSER_PY).exists() and _py(config.BROWSER_PY, "playwright")
                 and _py(config.BROWSER_PY, "yt_dlp"), str(config.BROWSER_PY))
    modelscope_cache = Path.home() / ".cache/modelscope"
    sv = list(modelscope_cache.glob("**/*SenseVoiceSmall*")) if modelscope_cache.is_dir() else []
    vad = list(modelscope_cache.glob("**/*fsmn*vad*")) if modelscope_cache.is_dir() else []
    asr_env_ok = Path(config.ASR_PY).exists() and bool(sv) and bool(vad)
    detail = (f"funasr({'导入ok' if _py(config.ASR_PY, 'funasr') else '导入失败'}) "
              f"SenseVoice缓存{'ok' if sv else '缺失'} vad缓存{'ok' if vad else '缺失'}")
    ok &= _check("ASR 环境（funasr + SenseVoice 缓存）", asr_env_ok, f"{config.ASR_PY} · {detail}")
    ok &= _check("ffmpeg", Path(config.FFMPEG).exists(), config.FFMPEG)
    ok &= _check("kb_para 解释器", Path(config.KB_PY).exists() and _py(config.KB_PY, "kb_para"), str(config.KB_PY))

    # 定时同步静默失效检测：launchd 没跑/Mac 睡死/任务被卸载时不会有任何报错，
    # 唯一痕迹是台账时间戳停滞（README 软规则「连续多晚无消息应核查」的机制化，2026-11-09）
    import datetime
    for slug, raw in registry.load_creators().items():
        c = registry.resolve(slug, raw)
        lf = Path(c["ledger_file"])
        rows_l = [json.loads(l) for l in open(lf)] if lf.exists() else []
        last_ts = max((r.get("ts") or "" for r in rows_l), default="")
        if not last_ts:
            continue  # 从未跑过，不算失效
        try:
            age_h = (datetime.datetime.now() - datetime.datetime.fromisoformat(last_ts)).total_seconds() / 3600
        except ValueError:
            continue
        stale = age_h > 36
        ok &= _check(f"定时同步时效[{c.get('name', slug)}]", not stale,
                     f"距上次活动 {age_h:.0f}h"
                     + ("——超 36h，疑似定时任务静默失效，检查 launchctl list | grep dysub" if stale else ""))

    pr = probe.probe()
    for k, v in pr.items():
        print(f"  {'✓' if v['ok'] else '✗'} 网络 {k} — {v['code']} {v['speed_bps'] // 1024}KB/s")
    ok &= pr.get("douyin", {}).get("ok", False)
    print("\n结论：" + ("环境就绪" if ok else "存在 ✗ 项，按提示处理后重试"))
    sys.exit(0 if ok else 1)


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(prog="dysub", description="抖音博主订阅转写插件")
    ap.add_argument("--version", action="version", version=f"dysub {__import__('dysub').__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="注册新博主（解析 sec_uid）")
    p.add_argument("url")
    p.add_argument("--name", help="博主昵称（缺省从页面抓取）")
    p.add_argument("--slug", help="注册标识（缺省由昵称生成）")
    p.add_argument("--asr-dir", help="转写 txt 落盘目录（缺省 <data_dir>/asr）")
    p.add_argument("--kb-root", help="kb_para 项目根（配置后才自动入库）")
    p.add_argument("--kb-source", help="capture source 标签（缺省 slug）")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_add)

    p = sub.add_parser("sync", help="增量同步：列表→下载→转写→入库")
    p.add_argument("names", nargs="*", help="博主 slug 或昵称")
    p.add_argument("--all", action="store_true")
    p.add_argument("--since", help="只处理 YYYY-MM-DD 之后（含当天）的视频")
    p.add_argument("--month", help="按月确定性抓取：YYYY-MM，逗号分隔多月（主页「日期筛选」，不受列表随机注入影响）")
    p.add_argument("--limit", type=int, help="本轮最多处理条数")
    p.add_argument("--no-ingest", action="store_true", help="跳过知识库入库")
    p.add_argument("--no-graph", action="store_true", help="跳过喂图（GraphMind 上传+索引）")
    p.add_argument("--no-notify", action="store_true", help="不发 macOS 通知")
    p.add_argument("--keep-media", action="store_true", help="保留已转写的 mp4（默认转写成功即删，释放磁盘）")
    p.set_defaults(fn=cmd_sync)

    p = sub.add_parser("status", help="各博主台账状态")
    p.add_argument("names", nargs="*")
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("doctor", help="环境自检")
    p.set_defaults(fn=cmd_doctor)

    p = sub.add_parser("ingest", help="把已有转写 txt 入知识库")
    p.add_argument("name")
    p.add_argument("--dir", help="指定 txt 目录（默认扫博主 asr_dir 的未入库文件用 --all）")
    p.add_argument("--all", action="store_true")
    p.set_defaults(fn=cmd_ingest)

    p = sub.add_parser("asr", help="单文件快速转写（SenseVoice）")
    p.add_argument("media")
    p.set_defaults(fn=cmd_asr)

    p = sub.add_parser("feed-graph", help="补喂：asr_dir 未喂图 txt 上传 GraphMind（幂等，失败隔离）")
    p.add_argument("name", help="博主 slug 或昵称")
    p.add_argument("--max", type=int, default=30, help="本轮最多喂入个数（默认 30，launchd 每晚排队消化）")
    p.add_argument("--dry-run", action="store_true", help="只列出待喂文件，不上传")
    p.set_defaults(fn=cmd_feed_graph)

    args = ap.parse_args()
    if getattr(args, "no_notify", False):
        browser.notify = lambda *a, **k: None
    args.fn(args)


if __name__ == "__main__":
    main()
