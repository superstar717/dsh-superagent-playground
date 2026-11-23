"""``localmodels source``: manage the active model source (local, subscription, or BYOK)."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from localmodels import (
    cli_help,
    deploy,
    hosts,
    library_convert,
    library_gateway,
    library_jobs,
    library_serve,
    library_state,
    runtime_cli,
    source_byok,
    source_byok_probe,
)
from localmodels.library_model import LibraryError
from localmodels.source_byok import ByokError, Mode, Runtime, SourceState


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-dir",
        default=deploy.DEFAULT_BASE_DIR,
        metavar="DIR",
        help="where local model weights and deployments live",
    )
    parser.add_argument(
        "--harness-root",
        type=Path,
        metavar="DIR",
        help="managed native runtime root (<home>/runtime/harness)",
    )
    parser.add_argument("--json", action="store_true", help="accepted; output is JSON")


def add_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = sub.add_parser(
        "source", help="inspect, check and switch the active model source (JSON)"
    )
    verbs = parser.add_subparsers(dest="source_command", required=True, metavar="COMMAND")

    status = verbs.add_parser("status", help="current model source and redacted BYOK metadata")
    _common(status)
    cli_help.document(
        status,
        "Print one localmodels.model-source-status/v1 document with the active mode, runtime, "
        "environment overrides and redacted BYOK configuration.",
        examples=[("%(prog)s --json", "")],
    )

    check = verbs.add_parser("check", help="verify a BYOK upstream endpoint from stdin JSON")
    check.add_argument(
        "--config-stdin",
        action="store_true",
        required=True,
        help="read BYOK configuration JSON from standard input",
    )
    check.add_argument("--json", action="store_true", help="accepted; output is JSON")
    cli_help.document(
        check,
        "Send one request in the given wire format (OpenAI chat, OpenAI responses, or "
        "Anthropic) to base URL + path + endpoint, without saving credentials or changing the "
        "active model source.",
        examples=[("%(prog)s --config-stdin --json", "")],
    )

    models = verbs.add_parser("models", help="list the models a BYOK endpoint serves")
    models.add_argument(
        "--config-stdin",
        action="store_true",
        required=True,
        help="read the BYOK endpoint and key as JSON from standard input",
    )
    models.add_argument("--json", action="store_true", help="accepted; output is JSON")
    cli_help.document(
        models,
        "List the models at base URL + path + /models, with their names and context windows "
        "when the endpoint reports them, without saving credentials.",
        examples=[("%(prog)s --config-stdin --json", "")],
    )

    apply_cmd = verbs.add_parser("apply", help="activate local, subscription or BYOK mode")
    apply_cmd.add_argument(
        "--mode",
        choices=source_byok.MODES,
        required=True,
        help="target model source mode",
    )
    apply_cmd.add_argument(
        "--runtime",
        choices=source_byok.RUNTIMES,
        help="target agent runtime (claude, codex, or pi)",
    )
    apply_cmd.add_argument(
        "--model",
        metavar="MODEL",
        help="library model ID to load when switching to local mode",
    )
    apply_cmd.add_argument(
        "--node",
        metavar="PATH",
        help="Node.js executable path when installing a missing managed runtime",
    )
    apply_cmd.add_argument(
        "--config-stdin",
        action="store_true",
        help="read BYOK configuration JSON from standard input",
    )
    _common(apply_cmd)
    cli_help.document(
        apply_cmd,
        "Switch the active model source, mounting BYOK on Bifrost or unloading local models "
        "as needed, and print the resulting localmodels.model-source-status/v1 JSON.",
        examples=[
            ("%(prog)s --mode byok --runtime claude --config-stdin --json", ""),
            ("%(prog)s --mode subscription --runtime codex --json", ""),
        ],
    )
    cli_help.document(
        parser,
        "Inspect, verify and switch between local models, native subscriptions and BYOK on Bifrost.",
        examples=[("%(prog)s status --json", "")],
    )


def _read_stdin_json() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        raise ByokError(
            "BYOK_INVALID_CONFIG", "Invalid JSON on standard input.", exit_code=2
        ) from exc
    if not isinstance(parsed, dict):
        raise ByokError("BYOK_INVALID_CONFIG", "Standard input must be a JSON object.", exit_code=2)
    return parsed


def _loaded_local_record() -> dict[str, Any] | None:
    library_convert.convert_once()
    for record in library_state.records():
        if record.get("state") == "loaded":
            return cast(dict[str, Any], record)
    return None


def _unload_loaded_local_models(base_dir: str) -> list[str]:
    library_convert.convert_once()
    unloaded: list[str] = []
    for record in list(library_state.records()):
        if record.get("state") == "loaded":
            model_id = str(record["id"])
            library_serve.unload(model_id, base_dir)
            unloaded.append(model_id)
    return unloaded


def _gateway_url() -> str | None:
    record = hosts.load_owned()["gateway"].get("bifrost")
    return f"http://{record['addr']}" if record and record.get("addr") else None


def _infer_default_state(harness_root: Path | None) -> SourceState:
    loaded = _loaded_local_record()
    if loaded is not None:
        reg = loaded.get("registration") or {}
        return {
            "schema": source_byok.SOURCE_SCHEMA,
            "mode": "local",
            "runtime": "pi",
            "runtime_model": str(reg.get("pi_model") or ""),
            "model_label": None,
            "gateway_url": _gateway_url(),
            "environment": {"PI_CODING_AGENT_DIR": str(library_gateway.pi_profile())},
        }
    chosen: Runtime = "claude"
    if harness_root is not None and harness_root.exists():
        rows = runtime_cli.inspect_runtimes(harness_root)["runtimes"]
        authed = next(
            (
                r["runtime"]
                for r in rows
                if r["runtime"] in ("claude", "codex") and r["authenticated"]
            ),
            None,
        )
        installed = next(
            (
                r["runtime"]
                for r in rows
                if r["runtime"] in ("claude", "codex", "pi") and r["installed"]
            ),
            None,
        )
        chosen = cast(Runtime, authed or installed or "claude")
    return {
        "schema": source_byok.SOURCE_SCHEMA,
        "mode": "subscription",
        "runtime": chosen,
        "runtime_model": "",
        "model_label": None,
        "gateway_url": None,
        "environment": {},
    }


def _endpoint_command(schema: str, run: Callable[[dict[str, Any]], dict[str, Any]]) -> int:
    """Run a read-only BYOK endpoint command on stdin JSON and print its one JSON document."""
    try:
        doc = {"schema": schema, "ok": True, **run(_read_stdin_json())}
    except ByokError as exc:
        doc = {"schema": schema, "ok": False, "code": exc.code, "message": str(exc)}
        print(json.dumps(doc, ensure_ascii=False))
        return exc.exit_code
    print(json.dumps(doc, ensure_ascii=False))
    return 0


def build_status(harness_root: Path | None = None) -> dict[str, Any]:
    """Build the redacted ``localmodels.model-source-status/v1`` payload."""
    state = source_byok.load_source_state() or _infer_default_state(harness_root)
    executable_paths: dict[str, str] = {}
    if harness_root is not None and harness_root.exists():
        rows = runtime_cli.inspect_runtimes(harness_root)["runtimes"]
        for row in rows:
            if row.get("installed") and row.get("executable") and not row.get("argvPrefix"):
                executable_paths[str(row["runtime"])] = str(row["executable"])
    return {
        "schema": source_byok.STATUS_SCHEMA,
        "mode": state["mode"],
        "runtime": state["runtime"],
        "runtime_model": state["runtime_model"],
        "gateway_url": state["gateway_url"],
        "environment": state["environment"],
        "runtime_paths": executable_paths,
        "byok": source_byok.credentials_summary(),
    }


def _ensure_runtime_installed(
    runtime: Runtime, harness_root: Path | None, node: str | None
) -> None:
    if harness_root is None:
        return
    status = runtime_cli.inspect_runtimes(harness_root, node=node)["runtimes"]
    row = next((item for item in status if item["runtime"] == runtime), None)
    if row and row.get("installed"):
        return
    plan = runtime_cli.build_plan(runtime, harness_root, node=node)
    runtime_cli.apply_plan(plan, str(plan["id"]))


def _stderr_event(event: dict[str, Any]) -> None:
    """One JSON line per event on stderr, written at once: stdout carries only the final
    document, which the installer parses whole."""
    sys.stderr.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stderr.flush()


def _apply_byok(args: argparse.Namespace, runtime: Runtime) -> SourceState:
    payload = _read_stdin_json() if args.config_stdin else None
    creds = source_byok_probe.probe_upstream(source_byok.resolve_endpoint(payload))
    _unload_loaded_local_models(args.base_dir)
    source_byok.save_credentials(creds)
    facts = library_jobs.probe()
    gateway_url, env = source_byok.mount_byok(creds, facts, _stderr_event)
    return source_byok.save_source_state(
        {
            "schema": source_byok.SOURCE_SCHEMA,
            "mode": "byok",
            "runtime": runtime,
            "runtime_model": source_byok.runtime_model_for_byok(runtime),
            "model_label": creds["model_id"],
            "gateway_url": gateway_url,
            "environment": env,
        }
    )


def _apply_subscription(args: argparse.Namespace, runtime: Runtime) -> SourceState:
    if runtime == "pi":
        raise ByokError(
            "BYOK_INVALID_CONFIG",
            "Subscription mode supports Claude Code or Codex.",
            exit_code=2,
        )
    _unload_loaded_local_models(args.base_dir)
    return source_byok.save_source_state(
        {
            "schema": source_byok.SOURCE_SCHEMA,
            "mode": "subscription",
            "runtime": runtime,
            "runtime_model": "",
            "model_label": None,
            "gateway_url": None,
            "environment": {},
        }
    )


def _apply_local(args: argparse.Namespace) -> SourceState:
    library_convert.convert_once()
    if args.model:
        others = [
            str(r["id"])
            for r in library_state.records()
            if r.get("state") == "loaded" and str(r["id"]) != args.model
        ]
        current = next((r for r in library_state.records() if str(r["id"]) == args.model), None)
        if current is None or current.get("state") != "loaded":
            library_serve.load(args.model, args.base_dir, others)
    loaded = _loaded_local_record()
    reg = (loaded or {}).get("registration") or {}
    return source_byok.save_source_state(
        {
            "schema": source_byok.SOURCE_SCHEMA,
            "mode": "local",
            "runtime": "pi",
            "runtime_model": str(reg.get("pi_model") or ""),
            "model_label": None,
            "gateway_url": _gateway_url(),
            "environment": {"PI_CODING_AGENT_DIR": str(library_gateway.pi_profile())},
        }
    )


def cli(args: argparse.Namespace) -> int:
    verb = args.source_command
    if verb == "status":
        try:
            doc = build_status(args.harness_root)
        except Exception as exc:  # noqa: BLE001
            print(f"error: source status failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(doc, ensure_ascii=False, indent=1))
        return 0
    if verb == "check":

        def check(payload: dict[str, Any]) -> dict[str, Any]:
            endpoint = source_byok.resolve_endpoint(payload, require_input=True)
            creds = source_byok_probe.probe_upstream(endpoint)
            return {
                "protocol": creds["protocol"],
                "url": source_byok.request_url(creds),
                "model_id": creds["model_id"],
                "context_window": creds["context_window"],
            }

        return _endpoint_command(source_byok.CHECK_SCHEMA, check)
    if verb == "models":

        def models(payload: dict[str, Any]) -> dict[str, Any]:
            endpoint = source_byok.resolve_endpoint(
                payload, require_input=True, require_model=False
            )
            listed = source_byok_probe.list_models(endpoint)
            return {"url": source_byok.models_url(endpoint), "models": listed}

        return _endpoint_command(source_byok.MODELS_SCHEMA, models)

    mode = cast(Mode, args.mode)
    current = source_byok.load_source_state()
    default_rt: Runtime = "pi" if mode == "local" else (current["runtime"] if current else "claude")
    if mode == "subscription" and default_rt == "pi":
        default_rt = "claude"
    runtime = cast(Runtime, args.runtime or default_rt)
    try:
        _ensure_runtime_installed(runtime, args.harness_root, args.node)
        if mode == "byok":
            _apply_byok(args, runtime)
        elif mode == "subscription":
            _apply_subscription(args, runtime)
        else:
            _apply_local(args)
        doc = build_status(args.harness_root)
    except ByokError as exc:
        print(
            json.dumps(
                {
                    "schema": source_byok.STATUS_SCHEMA,
                    "ok": False,
                    "code": exc.code,
                    "message": str(exc),
                },
                ensure_ascii=False,
            )
        )
        return exc.exit_code
    except LibraryError as exc:
        print(
            json.dumps(
                {
                    "schema": source_byok.STATUS_SCHEMA,
                    "ok": False,
                    "code": exc.code,
                    "message": exc.detail,
                },
                ensure_ascii=False,
            )
        )
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps(
                {
                    "schema": source_byok.STATUS_SCHEMA,
                    "ok": False,
                    "code": "SOURCE_APPLY_FAILED",
                    "message": str(exc),
                },
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(doc, ensure_ascii=False, indent=1))
    return 0
