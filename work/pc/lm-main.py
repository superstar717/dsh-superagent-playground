"""Command line: python3 -m localmodels COMMAND. HOST is "local" or a registered/SSH target."""

from __future__ import annotations

import argparse
import contextlib
import difflib
import json
import os
import sys
from collections.abc import Callable, Iterator

from localmodels import (
    __version__,
    app,
    approval,
    catalog_add,
    catalog_license,
    cli_help,
    console,
    debug_cli,
    debug_mode,
    deploy,
    desktop,
    discovery,
    gateway_cli,
    guard,
    hf_repo,
    hosts,
    install,
    library_cli,
    magpie_setup,
    memcalc_cli,
    plan_envelope,
    recommend_cli,
    runtime_cli,
    services_cli,
    setup_inspection,
    sizecalc_cli,
    source_cli,
    stack,
    stack_lifecycle,
)
from localmodels import catalog as cat
from localmodels.budget import gib
from localmodels.catalog import load_catalog_file
from localmodels.cli_parser import argument_parser as argument_parser
from localmodels.context_policy import window_k
from localmodels.probe import HostFacts
from localmodels.records import Plan, ProgressEvent
from localmodels.stack_console import Board
from localmodels.stack_plan import command

_FLAG_PREVIEW = 40


def _device(target: str) -> tuple[str, HostFacts | None]:
    """Registered device id, plus fresh facts when this call added a new SSH target. A new
    target is probed once at registration and kept only when that probe succeeds."""
    if target == hosts.LOCAL_ID or any(d["id"] == target for d in hosts.devices()):
        return target, None
    dev, facts = app.register_device(target)
    return dev["id"], facts


def _print(data: object) -> None:
    json.dump(data, sys.stdout, ensure_ascii=False, indent=1)
    sys.stdout.write("\n")


_width = console.cells


def _pad(text: str, width: int) -> str:
    return text + " " * max(2, width - _width(text))


def _shown_facts(facts: HostFacts) -> dict[str, object]:
    """Print copy of the facts: engine --help flag lists are capped; the saved facts keep all."""
    engines = []
    for engine in facts["engines"]:
        flags = engine.get("flags") or []
        engines.append(
            {**engine, "flags": [*flags[:_FLAG_PREVIEW], f"...（共 {len(flags)} 个）"]}
            if len(flags) > _FLAG_PREVIEW
            else engine
        )
    return {**facts, "engines": engines}


def _host_hint(target: str) -> str:
    """Closest registered or ssh_config device names when the operator may have mistyped."""
    names = {
        name
        for device in hosts.devices()
        for name in (device["id"], device["target"] or "")
        if name
    } | set(discovery.ssh_config_aliases())
    close = difflib.get_close_matches(target, sorted(names), n=3, cutoff=0.5)
    return f"did you mean: {', '.join(close)}?" if close else ""


def _model_hint(model_id: str) -> str:
    ids = [entry.id for entry in load_catalog_file()]
    shown = hf_repo.close_ids(model_id, ids) or ids
    return f"model ids: {', '.join(shown)} (the models command lists them all)"


def _service_hint(dev_id: str) -> str:
    names = [record["plan"]["name"] for record in hosts.records(dev_id)]
    shown = ", ".join(names) if names else "none"
    return f"deployment records on {dev_id}: {shown} (see the services command)"


def _fail(message: str, *, hint: str = "") -> int:
    print(f"error: {message}", file=sys.stderr)
    if hint:
        print(hint, file=sys.stderr)
    return 1


def _devices_list() -> int:
    for device in hosts.devices():
        facts = hosts.load_facts(device["id"])
        gpus = facts["gpus"] if facts else []
        target = device["target"] or "-"
        if device.get("port"):
            target = f"{target}:{device['port']}"
        summary = (
            f"{len(gpus)}×{gpus[0]['name']}"
            if gpus
            else (facts["gpu_vendor_class"] if facts else "-")
        )
        probed = console.local_time(facts["collected_at"]) if facts else "未探测"
        print(
            f"{_pad(device['id'], 14)}{_pad(device['label'], 12)}{_pad(target, 26)}"
            f"{_pad(probed, 18)}{summary}"
        )
    return 0


def _devices_remove(dev_id: str) -> int:
    if dev_id == hosts.LOCAL_ID:
        return _fail("本机不能移除")
    hosts.get_device(dev_id)
    hosts.remove_device(dev_id)
    print(f"已移除 {dev_id}；其缓存事实与部署记录仍在 {hosts.state_dir()}")
    return 0


_TASK_LABELS = {
    "llm": "Strata LLM 配方，用于 stack plan --llm",
    "decision": "决策模型",
    "embedding": "向量",
    "reranker": "重排",
    "stt": "语音转写",
    "tts": "语音合成（调试用）",
    "privacy-span": "隐私识别（guard）",
}


def _status_label(entry: cat.CatalogEntry) -> str:
    return recommend_cli.status_label(entry.status, entry.validated_on)


def _discover() -> int:
    """Candidates as an aligned table (CJK names included), then how to register one."""
    found = discovery.discover()
    if not found:
        print("没有找到候选设备：~/.ssh/config、Tailscale 和 mDNS 都没有给出主机。")
        print(f"已知地址时直接登记：{command()} probe 用户名@地址（只读探测并登记）")
        return 0
    online = {True: "在线", False: "离线", None: "?"}
    rows = [["名称", "地址", "SSH 别名", "系统", "在线", "来源"]] + [
        [
            c.label,
            f"{c.address}:{c.port}",
            c.ssh_target or "-",
            c.os or "-",
            online[c.online],
            ",".join(c.sources),
        ]
        for c in found
    ]
    print("\n".join(console.columns(rows)))
    print(
        f"登记一台：{command()} probe <SSH 别名，或 用户名@地址>，只读探测后它会出现在 devices 里；"
        "本命令不登记任何设备"
    )
    return 0


def _models_list() -> int:
    print("主 LLM（默认 llama.cpp；MLX 候选仅用于显式 macos-mlx-preview）")
    rows = [["id", "名称", "量化", "最小下载", "上下文", "状态", "许可", "特性"]]
    for entry in load_catalog_file():
        features = "、".join(
            label
            for flag, label in ((entry.mmproj is not None, "视觉"), (entry.mtp_capable, "MTP"))
            if flag
        )
        smallest = min(entry.download_bytes(variant) for variant in entry.variants)
        rows.append(
            [
                entry.id,
                entry.display_name,
                "、".join(variant.quant for variant in entry.variants),
                gib(smallest),
                window_k(entry.n_ctx_train),
                _status_label(entry),
                entry.license or "-",
                f"{entry.runtime} {features}".strip(),
            ]
        )
    print("\n".join(console.columns(rows, frozenset({3, 4}))))
    recipes = cat.components()
    groups = [(t, [r for r in recipes if r["task"] == t]) for t in cat.TASKS]
    groups = [(t, rs) for t, rs in groups if rs]
    table = [["id", "runtime", "版本", "下载", "状态", "许可"]] + [
        [
            r["id"],
            r["runtime"],
            r["version"],
            gib(sum(f["size_bytes"] for f in r["files"])),
            recommend_cli.status_label(str(r.get("status", ""))),
            catalog_license.license_label(r),
        ]
        for _, rs in groups
        for r in rs
    ]
    lines = iter(console.columns(table, frozenset({3})))  # one width across every task's rows
    print(f"\n任务组件（stack plan 按任务装入）\n  {next(lines)}")
    for task, rs in groups:
        print(f"\n任务组件 {task} · {_TASK_LABELS.get(task, task)}")
        for _ in rs:
            print(f"  {next(lines)}")
    return 0


def _services_list(host: str) -> int:
    dev = hosts.get_device(host)
    records = hosts.records(dev["id"])
    if not records:
        print(
            f"{dev['id']} 无部署记录。单个模型：{command()} deploy {dev['id']} <模型 id>"
            f"（models 列出可选）；整套 Agent 套件：{command()} install"
        )
        return 0
    for record in records:
        plan = record["plan"]
        print(
            f"{_pad(plan['name'], 28)}{_pad(plan['model']['display_name'], 20)}"
            f"{_pad(plan['endpoint']['base_url'], 28)}{_pad('ok' if record['ok'] else '失败', 8)}"
            f"{record.get('finished_at') or record['started_at']}"
        )
    return 0


def _recommend(target: str, *, refresh: bool = False, all_models: bool = False) -> int:
    dev_id, first_facts = _device(target)
    if first_facts is not None:
        print("首次登记已完成探测，以下读取已保存的硬件快照。")
    result = app.catalog(dev_id, fresh=refresh and first_facts is None)
    facts = result["facts"]
    source = (
        "缓存" if result["facts_source"] == "cache" else "刷新探测" if refresh else "探测（无缓存）"
    )
    when = facts["collected_at"]
    print(f"硬件快照：{source}；采集时间 {console.local_time(when)}（本地时间；{when}）")
    print(
        f"  观测系统 RAM 可用 {gib(facts['ram']['available_bytes'])} / "
        f"总量 {gib(facts['ram']['total_bytes'])}。"
    )
    for gpu in facts.get("gpus") or []:
        print(
            f"  GPU {gpu['index']} {gpu['name']}：快照空闲显存 {gib(gpu['free_bytes'])} / "
            f"总量 {gib(gpu['total_bytes'])}。"
        )
    if facts.get("gpus"):
        print("  空闲显存不等于获准共用；整栈计划会重新探测。")
    placements = {str(p["id"]): p for p in result["placements"]}
    recommend_cli.show_stack(result["facts"], dev_id, all_models=all_models)
    if not all_models:
        print(f"完整目录、替代选项与证据：{command()} recommend {target} --all")
        return 0

    def tag(placement_id: str) -> str:
        placement = placements.get(placement_id) or {}
        return placement_id + ("·占用中" if placement.get("busy") else "")

    print("LLM 容量参考（全部目录；按总容量估算，不是当前整栈默认）：")
    for m in result["models"]:
        verdict = (
            recommend_cli.fit_label(m.get("fit_reason", ""))
            if not m["fits"]
            else "使用系统内存"
            if m.get("spilled")
            else "CPU + 内存"
            if placements.get(str(m.get("placement", {}).get("id")), {}).get("backend") == "cpu"
            else "驻留设备内存"
        )
        where = tag(str(m.get("placement", {}).get("id", "-")))
        print(
            f"  {_pad(m['id'], 20)} [{m.get('status', 'unknown')}] "
            f"{_pad(m['display_name'], 20)}{m['size_label']:>9}  "
            f"{_pad(verdict, 16)}{_pad(where, 20)}{m['fit_summary']}"
        )
        if m.get("validated_on"):
            print("    已验证平台：" + "、".join(m["validated_on"]))
        if "predicted_decode_tok_s" in m:
            print(
                f"    解码估算 {m['predicted_decode_tok_s']:g} tok/s；"
                f"{m.get('decode_basis_text', '带宽估算')}，不是本机推理实测。"
            )
    disk = result["facts"]["disk"]
    free = disk.get("free_bytes")
    busy = [pid for pid, placement in placements.items() if placement.get("busy")]
    if busy:
        print(
            f"注意：{'、'.join(busy)} 在快照中有占用或空闲显存不足；适配按总容量计价，"
            "plan/deploy 会按实时空闲重新计价。"
        )
    if free is not None:
        over = [
            m["id"] for m in result["models"] if m.get("fits") and m.get("size_bytes", 0) > free
        ]
        if over:
            print(
                f"注意：磁盘 {disk.get('path', '?')} 剩余 {gib(free)}；"
                f"{'、'.join(over)} 的下载量超出剩余，plan 会拒绝。"
            )
    measured = result["facts"].get("memory_bandwidth")
    if measured:
        spilled = [m["id"] for m in result["models"] if m.get("decode_basis") == "host-measured"]
        print(
            f"主机内存带宽：本机实测 {measured['measured_gbps']:g} GB/s"
            f"（{measured['measured_at']}）；溢出模型的速度估算用它代替"
            f"{cat.DECODE_BASES['host-class']}"
            + (f"：{'、'.join(spilled)}" if spilled else "，当前没有溢出的模型")
        )
    return 0


def _deploy_board(plan: Plan) -> Board:
    """Single-model deploy as a one-row progress board (the stack's live view)."""
    model = plan["model"]
    title = f"部署 {model['display_name']} {model['quant']}".rstrip()
    return Board([("model", plan["name"])], title)


def _deploy_events(board: Board) -> Callable[[str, ProgressEvent], None]:
    def seen(step: str, event: ProgressEvent) -> None:
        if event.get("event") != "progress":
            message = event.get("message") or json.dumps(event, ensure_ascii=False)
            board(f"[model:{step}] {message}")
            return
        done, total = event.get("done"), event.get("total")
        counted = isinstance(done, int) and isinstance(total, int)
        board.progress(
            {
                "event": "progress",
                "component": "model",
                "step": step,
                "phase": str(event.get("phase") or step),
                "done": done if counted else None,
                "total": total if counted else None,
            }
        )

    return seen


def _commands(args: argparse.Namespace, scope: list[str]) -> int:
    """``commands`` and ``stack commands``: the argument tree as text or JSON."""
    node = argument_parser()
    for name in scope:
        found = cli_help.subcommands(node)
        if found is None or name not in found.choices:
            return _fail(
                f"no command {' '.join(scope)}", hint=f"{command()} commands lists every command"
            )
        node = found.choices[name]
    tree = list(cli_help.walk(node, scope))
    if args.json:
        _print({"schema": cli_help.SCHEMA, "version": __version__, "commands": tree})
    else:
        print(cli_help.listing(tree, command()))
    return 0


def _completion(args: argparse.Namespace) -> int:
    tree = list(cli_help.walk(argument_parser()))
    sys.stdout.write(cli_help.completion(tree, "localmodels", args.shell))
    return 0


@contextlib.contextmanager
def _english_system_messages() -> Iterator[None]:
    """While the block runs, programs this process starts (systemctl, nvidia-smi, ssh...) print
    their messages in English whatever the user's locale, so ``stack`` output stays English when
    it quotes them. The character set the locale names is kept: LC_ALL moves to LANG."""
    names = ("LC_ALL", "LANG", "LANGUAGE", "LC_MESSAGES")
    saved = {name: os.environ.get(name) for name in names}
    lc_all = os.environ.pop("LC_ALL", None)
    if lc_all:
        os.environ["LANG"] = lc_all
    os.environ.pop("LANGUAGE", None)
    os.environ["LC_MESSAGES"] = "C"
    try:
        yield
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _stack(args: argparse.Namespace) -> int:
    with _english_system_messages():
        if args.stack_command == "install":
            return install.cli(args)
        if args.stack_command == "commands":
            return _commands(args, ["stack"])
        return stack.cli(args)


def _run(args: argparse.Namespace) -> int:
    commands: dict[str, Callable[[argparse.Namespace], int]] = {
        "guard": guard.cli,
        "stack": _stack,
        "magpie": magpie_setup.cli,
        "memcalc": memcalc_cli.cli,
        "sizecalc": sizecalc_cli.cli,
        "catalog": catalog_add.cli,
        "install": install.cli,
        "harness": runtime_cli.cli,
        "gateway": gateway_cli.cli,
        "setup": setup_inspection.cli,
        "foundations": services_cli.cli,
        "library": library_cli.cli,
        "source": source_cli.cli,
        "debug": debug_cli.cli,
        "commands": lambda parsed: _commands(parsed, list(parsed.path)),
        "completion": _completion,
    }
    if args.command in commands:
        return commands[args.command](args)
    if args.command == "devices":
        return _devices_remove(args.id) if args.devices_command == "remove" else _devices_list()
    if args.command == "models":
        return _models_list()
    if args.command == "services":
        return _services_list(args.host)
    if args.command == "desktop-snapshot":
        desktop_result = desktop.snapshot(refresh=args.refresh)
        _print(desktop_result)
        if not desktop_result["ok"] and desktop_result["observation"].get("state") == "unknown":
            print("提示：尚无本机快照；加 --refresh 运行一次只读本机探测。", file=sys.stderr)
        return 0 if desktop_result["ok"] else 1
    if args.command == "discover":
        return _discover()
    if args.command == "probe":
        with console.status(f"探测 {args.host}…"):
            dev_id, fresh = _device(args.host)
            if args.measure_bandwidth:
                fresh = app.probe(dev_id, measure_bandwidth=True)
            facts = fresh or app.probe(dev_id)
        _print(_shown_facts(facts))
        return 0
    if args.command == "recommend":
        return _recommend(args.host, refresh=args.refresh, all_models=args.all_models)
    if args.command == "serve":
        app.serve(args.port)
        return 0
    if args.command == "tui":
        from localmodels import tui

        return tui.run()
    if args.command == "service":
        return _service(args)
    return _plan_or_deploy(args)


def _service(args: argparse.Namespace) -> int:
    dev_id = _device(args.host)[0]
    if args.action != "remove":
        if args.purge or args.yes:
            return _fail("--purge 与 --yes 只用于 remove")
        result = app.service_action(dev_id, args.name, args.action)
        _print(result)
        return 1 if result.get("event") == "error" else 0
    removed = stack_lifecycle.service_remove(dev_id, args.name, args.purge, args.yes)
    if removed is None:
        return 1
    _print(removed)
    return 1 if removed.get("event") == "error" else 0


def _plan_or_deploy(args: argparse.Namespace) -> int:
    entries = load_catalog_file()
    if (
        not any(args.model_id in (entry.id, entry.variants[-1].model_id) for entry in entries)
        and hf_repo.spec_parts(args.model_id) is None
    ):
        return _fail(f"目录中没有模型 {args.model_id}", hint=_model_hint(args.model_id))
    options = deploy.PlanOptions(
        model_id=args.model_id,
        placement_id=args.placement,
        port=args.port,
        bind=args.bind,
        hf_download_endpoint=args.hf_endpoint,
        hf_api_endpoint=args.hf_endpoint,
        engine_path=args.engine_path,
    )
    dev_id, _ = _device(args.host)
    if args.command == "deploy" and args.approve:
        return _deploy_approved(args, dev_id, options)
    built = app.plan(dev_id, options)["plan"]
    _print(built)
    print(f"许可：{catalog_license.license_note(built['model']['id'])}", file=sys.stderr)
    if args.command == "deploy" and args.yes:
        print(
            "提示：--yes 已弃用：它重新生成计划并立即执行；"
            "改用 deploy 打印的 --approve 命令执行你看过的计划",
            file=sys.stderr,
        )
        facts = hosts.load_facts(dev_id)
        if facts is not None:
            approval.require_free_gpus(built, facts, share_gpu=args.share_gpu)
        return _execute(dev_id, built)
    plan_id = approval.save_deployment(dev_id, built, options)
    print(
        f"未执行；将下载 {gib(built['model']['download_bytes'])}。"
        f"确认后执行：{_approve_command(args, plan_id)}",
        file=sys.stderr,
    )
    return 0


def _approve_command(args: argparse.Namespace, plan_id: str) -> str:
    """The deploy command that executes plan ``plan_id``, with the options it was planned with."""
    flags = [
        f"--{name.replace('_', '-')} {value}"
        for name, default in (
            ("placement", "auto"),
            ("port", deploy.DEFAULT_PORT),
            ("bind", "127.0.0.1"),
            ("hf_endpoint", deploy.HF_API),
            ("engine_path", None),
        )
        if (value := getattr(args, name)) != default
    ]
    words = [command(), "deploy", args.host, args.model_id, *flags, "--approve", plan_id]
    return " ".join(words)


def _deploy_approved(args: argparse.Namespace, dev_id: str, options: deploy.PlanOptions) -> int:
    """Execute the saved plan ``--approve`` names, after the gate in approval.py."""
    try:
        plan, saved = approval.load_deployment(dev_id, args.approve)
    except KeyError:
        return _fail(
            f"{dev_id} 上没有确认码为 {args.approve} 的已保存计划",
            hint=f"先运行 {command()} deploy {args.host} {args.model_id}，再用它打印的命令执行",
        )
    if saved != options:
        return _fail("命令行选项与确认的计划不同；按计划打印的命令执行，或重新生成计划")
    try:
        app.check_approved(dev_id, plan, saved, share_gpu=args.share_gpu)
    except approval.PlanChangedError as exc:
        _print(exc.fresh)
        fresh_id = approval.save_deployment(dev_id, exc.fresh, saved)
        return _fail(
            str(exc), hint=f"检查上面的新计划；确认后执行：{_approve_command(args, fresh_id)}"
        )
    except approval.BusyGpuError as exc:
        return _fail(str(exc), hint="确认可以与它共用后，加 --share-gpu 重新执行同一条命令")
    return _execute(dev_id, plan)


def _execute(dev_id: str, plan: Plan) -> int:
    board = _deploy_board(plan)
    with board:
        record = app.run_deploy(dev_id, plan, on_event=_deploy_events(board))
        detail = plan["endpoint"]["base_url"] if record["ok"] else record.get("error", "")
        board.stage(
            None,
            [
                {
                    "component": "model",
                    "status": "ok" if record["ok"] else "failed",
                    "detail": detail,
                }
            ],
        )
    print(("部署完成：" if record["ok"] else "部署失败：") + detail, file=sys.stderr)
    return 0 if record["ok"] else 1


def owner_only_writes() -> None:
    """Never write a group- or world-writable file, whatever the login umask. Ubuntu gives new
    users umask 0002, and the ownership checks (the Bifrost unit, deployment records) refuse
    such files, so the gateway this tool had just started was never proven ready (aws-l4,
    2026-11-09)."""
    os.umask(os.umask(0o022) | 0o022)


def main(argv: list[str] | None = None) -> int:
    owner_only_writes()
    if sys.platform == "win32" and "PYTHONIOENCODING" not in os.environ:
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if callable(reconfigure):
                reconfigure(encoding="utf-8")
    args = argument_parser().parse_args(argv)
    if args.region:  # resolved lazily by the first download (region.py)
        os.environ["SIMPLEX_REGION"] = args.region
    if args.command != "debug" and (args.command, getattr(args, "stack_command", None)) != (
        "stack",
        "mcp",
    ):
        debug_mode.activate()
    try:
        code = _reported(args)
        sys.stdout.flush()  # a closed pipe surfaces here for buffered output, not at exit
    except KeyboardInterrupt:
        # Ctrl-C at any point; code that must clean up does so on the way out (finally).
        print("interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:
        # The reader left (`| head`): stop writing quietly, exit as SIGPIPE would.
        with contextlib.suppress(OSError, ValueError):
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 141
    return code


def _given_file(args: argparse.Namespace, missing: object) -> str | None:
    """The option or argument whose value is the file that does not exist, if the user named it."""
    if missing is None:
        return None
    for name, value in vars(args).items():
        if isinstance(value, str | os.PathLike) and os.fspath(value) == os.fspath(str(missing)):
            return name.replace("_", " ")
    return None


def _reported(args: argparse.Namespace) -> int:
    """Run the command; the errors a user can act on become one message and an exit code."""
    try:
        return _run(args)
    except BrokenPipeError:
        raise
    except FileNotFoundError as exc:
        if (given := _given_file(args, exc.filename)) is None:
            return _fail(str(exc), hint=_host_hint(getattr(args, "host", "")))
        print(f"error: {given} file not found: {exc.filename}", file=sys.stderr)
        return 2
    except app.ProbeError as exc:
        return _fail(f"probe failed: {exc}", hint=_host_hint(getattr(args, "host", "")))
    except plan_envelope.PlanError as exc:
        hint = ""
        if "catalog has no model" in str(exc):
            hint = _model_hint(getattr(args, "model_id", ""))
        elif getattr(args, "host", ""):
            hint = _host_hint(args.host)
        return _fail(str(exc), hint=hint)
    except KeyError as exc:
        missing = str(exc.args[0]) if exc.args else str(exc)
        known = {d["id"] for d in hosts.devices()}
        host = getattr(args, "host", "")
        hint = (
            _service_hint(host)
            if args.command == "service" and host in known
            else _host_hint(missing)
        )
        return _fail(f"not found: {missing}", hint=hint)
    except (OSError, ValueError) as exc:
        return _fail(str(exc), hint=_host_hint(getattr(args, "host", "")))


if __name__ == "__main__":
    sys.exit(main())
