"""BYOK upstream validation, live probing, Bifrost mounting and isolated client profiles."""

from __future__ import annotations

import contextlib
import copy
import ipaddress
import json
import os
import re
import urllib.parse
from pathlib import Path
from typing import Any, Literal, TypedDict

from localmodels import (
    bifrost_config,
    bifrost_datasheet,
    bifrost_models,
    bifrost_provider,
    gateway_bifrost,
    harness,
    hosts,
    library_gateway,
    runtime_io,
)
from localmodels.probe import HostFacts

Protocol = Literal["openai-chat", "openai-responses", "anthropic"]
Mode = Literal["local", "subscription", "byok"]
Runtime = Literal["claude", "codex", "pi"]

PROTOCOLS: tuple[Protocol, ...] = ("openai-chat", "openai-responses", "anthropic")
# Where each wire format is served under an API root such as https://host/v1.
PROTOCOL_ENDPOINTS: dict[Protocol, str] = {
    "openai-chat": "/chat/completions",
    "openai-responses": "/responses",
    "anthropic": "/messages",
}
# The Bifrost request types each wire format serves. Claude Code's Messages calls arrive as
# responses requests and Pi's as chat completions, so an Anthropic upstream takes both.
_BYOK_REQUESTS: dict[Protocol, tuple[str, ...]] = {
    "openai-chat": ("chat_completion", "chat_completion_stream"),
    "openai-responses": ("responses", "responses_stream"),
    "anthropic": ("chat_completion", "chat_completion_stream", "responses", "responses_stream"),
}
MODES: tuple[Mode, ...] = ("local", "subscription", "byok")
RUNTIMES: tuple[Runtime, ...] = ("claude", "codex", "pi")

BYOK_PROVIDER = bifrost_config.BYOK_PROVIDER
BYOK_MODEL = BYOK_PROVIDER
BYOK_PI_MODEL = f"{gateway_bifrost.PI_PROVIDER}/{BYOK_MODEL}"
DEFAULT_CONTEXT_WINDOW = bifrost_models.DEFAULT_CONTEXT
MAX_CONTEXT_WINDOW = 2_147_483_647
MODEL_ID_PATTERN = re.compile(r"^[-a-zA-Z0-9_./:@]{1,256}$")
# A path or endpoint is empty or whole segments each led by one slash, so appending it to
# the base URL can only extend the path, never change the host, query or fragment.
URL_PATH_PATTERN = re.compile(r"^(?:/[^/?#\s\\]+)*$")
MAX_URL_PATH = 256

CREDENTIALS_SCHEMA = "localmodels.byok-credentials/v2"
_V1_CREDENTIALS_SCHEMA = "localmodels.byok-credentials/v1"
SOURCE_SCHEMA = "localmodels.model-source/v1"
STATUS_SCHEMA = "localmodels.model-source-status/v1"
CHECK_SCHEMA = "localmodels.byok-check/v1"
MODELS_SCHEMA = "localmodels.byok-models/v1"


class ByokEndpoint(TypedDict):
    # Requests go to base_url + path + endpoint and models are listed at
    # base_url + path + /models; protocol is the wire format the caller chose.
    base_url: str
    path: str
    endpoint: str
    protocol: Protocol
    api_key: str
    model_id: str
    context_window: int


class ByokCredentials(TypedDict):
    schema: str
    protocol: Protocol
    base_url: str
    path: str
    endpoint: str
    api_key: str
    model_id: str
    context_window: int
    key_saved: bool


class ByokSummary(TypedDict):
    configured: bool
    protocol: Protocol | None
    base_url: str | None
    path: str | None
    endpoint: str | None
    model_id: str | None
    context_window: int | None
    key_saved: bool


class SourceState(TypedDict):
    schema: str
    mode: Mode
    runtime: Runtime
    runtime_model: str
    # The BYOK model ID as entered, which the Computer shows in place of the gateway route.
    model_label: str | None
    gateway_url: str | None
    environment: dict[str, str]


class ByokError(ValueError):
    """Structured BYOK failure with a closed error code and CLI exit status."""

    def __init__(self, code: str, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def _credentials_path() -> Path:
    return hosts.state_dir().resolve() / "byok.json"


def _source_path() -> Path:
    return hosts.state_dir().resolve() / "model-source.json"


def byok_home() -> Path:
    """Isolated client configuration root for BYOK, separate from native and stack profiles."""
    return hosts.state_dir().resolve() / "byok-home"


def _is_tailscale(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return isinstance(address, ipaddress.IPv4Address) and address in ipaddress.ip_network(
        "100.64.0.0/10"
    )


def _classify_host(hostname: str) -> bool:
    """Return whether ``hostname`` is loopback or private LAN; reject metadata/link-local hosts."""
    lowered = hostname.lower().rstrip(".")
    if not lowered:
        raise ByokError("BYOK_INVALID_CONFIG", "Endpoint URL requires a hostname.", exit_code=2)
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        if lowered == "metadata.google.internal":
            raise ByokError(
                "BYOK_INVALID_CONFIG", "Metadata endpoints are not allowed.", exit_code=2
            ) from None
        return lowered == "localhost" or lowered.endswith(".local") or "." not in lowered
    if address.is_link_local or address.is_multicast or address.is_unspecified:
        raise ByokError(
            "BYOK_INVALID_CONFIG",
            "Link-local, multicast and unspecified addresses are not allowed.",
            exit_code=2,
        )
    return bool(address.is_loopback or address.is_private or _is_tailscale(address))


def validate_url(raw: object) -> tuple[str, bool]:
    """Validate an upstream endpoint URL and report whether it targets loopback or private LAN."""
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 2048:
        raise ByokError("BYOK_INVALID_CONFIG", "Endpoint URL is required.", exit_code=2)
    value = raw.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(value)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ByokError(
            "BYOK_INVALID_CONFIG", "Endpoint URL port is invalid.", exit_code=2
        ) from exc
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ByokError("BYOK_INVALID_CONFIG", "Endpoint URL format is invalid.", exit_code=2)
    private = _classify_host(parsed.hostname)
    if parsed.scheme == "http" and not private:
        raise ByokError(
            "BYOK_INVALID_CONFIG",
            "Plain HTTP is allowed only for localhost and private network endpoints.",
            exit_code=2,
        )
    return value, private


def validate_url_path(raw: object, label: str) -> str:
    """Validate an optional path or endpoint appended to the base URL."""
    if not isinstance(raw, str) or len(raw) > MAX_URL_PATH or not URL_PATH_PATTERN.fullmatch(raw):
        raise ByokError(
            "BYOK_INVALID_CONFIG",
            f"{label} must be empty or a path such as /v1.",
            exit_code=2,
        )
    return raw


def request_url(endpoint: ByokEndpoint | ByokCredentials) -> str:
    """The one address the endpoint's requests are sent to."""
    return endpoint["base_url"] + endpoint["path"] + endpoint["endpoint"]


def models_url(endpoint: ByokEndpoint | ByokCredentials) -> str:
    """The address that lists the endpoint's models."""
    return endpoint["base_url"] + endpoint["path"] + "/models"


def _from_v1(raw: dict[str, Any]) -> dict[str, Any]:
    """A v1 file sent its requests to upstream_url + /v1 + the wire format's endpoint, so it
    converts to v2 exactly."""
    return {
        **raw,
        "schema": CREDENTIALS_SCHEMA,
        "base_url": raw.get("upstream_url"),
        "path": "/v1",
        "endpoint": PROTOCOL_ENDPOINTS[raw["protocol"]],
    }


def load_credentials() -> ByokCredentials | None:
    """Read saved BYOK credentials from private state, or None when absent."""
    path = _credentials_path()
    if not path.exists() and not path.is_symlink():
        return None
    runtime_io.private_permissions(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("protocol") not in PROTOCOLS:
        raise ByokError("BYOK_INVALID_CONFIG", "Saved BYOK credentials are invalid.")
    converted = raw.get("schema") == _V1_CREDENTIALS_SCHEMA
    if converted:
        raw = _from_v1(raw)
    if raw.get("schema") != CREDENTIALS_SCHEMA:
        raise ByokError("BYOK_INVALID_CONFIG", "Saved BYOK credentials are invalid.")
    url, _ = validate_url(raw.get("base_url"))
    model_id = str(raw.get("model_id") or "")
    if not MODEL_ID_PATTERN.fullmatch(model_id):
        raise ByokError("BYOK_INVALID_CONFIG", "Saved BYOK model ID is invalid.")
    key = raw.get("api_key", "")
    if not isinstance(key, str):
        raise ByokError("BYOK_INVALID_CONFIG", "Saved BYOK key is invalid.")
    window = int(raw.get("context_window") or DEFAULT_CONTEXT_WINDOW)
    try:
        url_path = validate_url_path(raw.get("path"), "Path")
        endpoint = validate_url_path(raw.get("endpoint"), "Endpoint")
    except ByokError:
        raise ByokError("BYOK_INVALID_CONFIG", "Saved BYOK credentials are invalid.") from None
    creds: ByokCredentials = {
        "schema": CREDENTIALS_SCHEMA,
        "protocol": raw["protocol"],
        "base_url": url,
        "path": url_path,
        "endpoint": endpoint,
        "api_key": key,
        "model_id": model_id,
        "context_window": window if 1 <= window <= MAX_CONTEXT_WINDOW else DEFAULT_CONTEXT_WINDOW,
        "key_saved": bool(key),
    }
    if converted:
        save_credentials(creds)
    return creds


def save_credentials(creds: ByokCredentials) -> None:
    """Persist BYOK credentials in a 0600 private file."""
    state = hosts.state_dir().resolve()
    runtime_io.private_directory(state)
    runtime_io.write_private_json(_credentials_path(), creds)


def credentials_summary(creds: ByokCredentials | None = None) -> ByokSummary:
    """Redacted BYOK metadata safe to expose across RPC and UI boundaries."""
    loaded = creds if creds is not None else load_credentials()
    if loaded is None:
        return {
            "configured": False,
            "protocol": None,
            "base_url": None,
            "path": None,
            "endpoint": None,
            "model_id": None,
            "context_window": None,
            "key_saved": False,
        }
    return {
        "configured": True,
        "protocol": loaded["protocol"],
        "base_url": loaded["base_url"],
        "path": loaded["path"],
        "endpoint": loaded["endpoint"],
        "model_id": loaded["model_id"],
        "context_window": loaded["context_window"],
        "key_saved": loaded["key_saved"],
    }


def _resolve_key(payload: dict[str, Any], saved: ByokCredentials | None, private: bool) -> str:
    raw_key = payload.get("apiKey")
    if isinstance(raw_key, str) and raw_key != "":
        if len(raw_key) > 4096 or any(ord(c) <= 32 or ord(c) == 127 for c in raw_key):
            raise ByokError("BYOK_INVALID_CONFIG", "API key format is invalid.", exit_code=2)
        return raw_key
    if raw_key is None and saved is not None and saved["key_saved"]:
        return saved["api_key"]
    if raw_key == "" and saved is not None and saved["key_saved"] and payload.get("reuseSavedKey"):
        return saved["api_key"]
    if private and (raw_key == "" or raw_key is None):
        return ""
    raise ByokError("BYOK_INVALID_CONFIG", "An API key is required for this endpoint.", exit_code=2)


def resolve_endpoint(
    payload: dict[str, Any] | None, *, require_input: bool = False, require_model: bool = True
) -> ByokEndpoint:
    """Validate incoming BYOK input, falling back to saved credentials when omitted.

    Listing models needs only the address and key, so ``require_model`` false allows no
    model ID.
    """
    saved = load_credentials()
    if not payload:
        if require_input or saved is None:
            raise ByokError("BYOK_INVALID_CONFIG", "BYOK configuration is required.", exit_code=2)
        return {
            "base_url": saved["base_url"],
            "path": saved["path"],
            "endpoint": saved["endpoint"],
            "protocol": saved["protocol"],
            "api_key": saved["api_key"],
            "model_id": saved["model_id"],
            "context_window": saved["context_window"],
        }
    allowed = {
        "baseUrl",
        "path",
        "endpoint",
        "protocol",
        "apiKey",
        "modelId",
        "contextWindow",
        "reuseSavedKey",
    }
    if not isinstance(payload, dict) or set(payload) - allowed:
        raise ByokError(
            "BYOK_INVALID_CONFIG", "BYOK configuration fields are invalid.", exit_code=2
        )
    base_url, private = validate_url(payload.get("baseUrl"))
    protocol = payload.get("protocol")
    if protocol not in PROTOCOLS:
        raise ByokError("BYOK_INVALID_CONFIG", "Wire format is invalid.", exit_code=2)
    model_raw = payload.get("modelId") or (saved["model_id"] if saved and require_model else "")
    if not isinstance(model_raw, str) or (
        (require_model or model_raw) and not MODEL_ID_PATTERN.fullmatch(model_raw.strip())
    ):
        raise ByokError("BYOK_INVALID_CONFIG", "Model ID is invalid.", exit_code=2)
    window_raw = payload.get("contextWindow")
    if window_raw is None:
        window = saved["context_window"] if saved else DEFAULT_CONTEXT_WINDOW
    elif type(window_raw) is int and 1 <= window_raw <= MAX_CONTEXT_WINDOW:
        window = window_raw
    else:
        raise ByokError(
            "BYOK_INVALID_CONFIG", "Context window must be a positive integer.", exit_code=2
        )
    return {
        "base_url": base_url,
        "path": validate_url_path(payload.get("path"), "Path"),
        "endpoint": validate_url_path(payload.get("endpoint"), "Endpoint"),
        "protocol": protocol,
        "api_key": _resolve_key(payload, saved, private),
        "model_id": model_raw.strip(),
        "context_window": window,
    }


def render_byok_provider(creds: ByokCredentials) -> dict[str, Any]:
    """Render the Bifrost provider entry for ``localmodels-byok``.

    Every allowed request type gets an absolute URL: Bifrost sends an empty override to its
    own /v1/... path, so only a full URL reaches a base URL that is already the whole address.
    """
    key = creds["api_key"] or gateway_bifrost.CALLER_KEY
    model = creds["model_id"]
    entry = bifrost_provider.render("llm", creds["base_url"], model, key, BYOK_PROVIDER)
    entry["network_config"]["base_url"] = creds["base_url"]
    first = entry["keys"][0]
    first["models"] = [model] if model == BYOK_MODEL else [model, BYOK_MODEL]
    first["aliases"] = {BYOK_MODEL: model}
    url = request_url(creds)
    overrides = {name: url for name in _BYOK_REQUESTS[creds["protocol"]]}
    overrides["list_models"] = models_url(creds)
    custom = entry["custom_provider_config"]
    if creds["protocol"] == "anthropic":
        custom["base_provider_type"] = "anthropic"
        overrides["count_tokens"] = f"{url}/count_tokens"
    custom["allowed_requests"] = dict.fromkeys(overrides, True)
    custom["request_path_overrides"] = overrides
    return entry


def _write_codex_profile(root: Path, addr: str, facts: bifrost_models.LlmFacts) -> str:
    codex_dir = root / ".codex"
    runtime_io.private_directory(codex_dir)
    catalog_path = codex_dir / "localmodels-models.json"
    catalog_doc = bifrost_models.codex_catalog(facts, BYOK_MODEL)
    runtime_io.write_private_json(catalog_path, catalog_doc)
    config_toml = "\n".join(
        [
            f'model = "{BYOK_MODEL}"',
            f'model_provider = "{gateway_bifrost.PI_PROVIDER}"',
            f"model_catalog_json = {json.dumps(str(catalog_path))}",
            "",
            f"[model_providers.{gateway_bifrost.PI_PROVIDER}]",
            'name = "localmodels (Bifrost BYOK)"',
            f'base_url = "http://{addr}/v1"',
            'wire_api = "responses"',
            "requires_openai_auth = false",
            "",
        ]
    )
    target = codex_dir / "config.toml"
    tmp = codex_dir / ".config.toml.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(config_toml)
    os.replace(tmp, target)
    runtime_io.private_permissions(target, created=True)
    return str(codex_dir)


def _write_claude_profile(root: Path, addr: str, context: int) -> str:
    claude_dir = root / ".claude"
    runtime_io.private_directory(claude_dir)
    settings = {"env": bifrost_models.claude_env(BYOK_MODEL, f"http://{addr}", context)}
    runtime_io.write_private_json(claude_dir / "settings.json", settings)
    return str(claude_dir)


def _write_pi_profile(root: Path, addr: str, facts: bifrost_models.LlmFacts) -> str:
    pi_dir = root / ".pi" / "agent"
    runtime_io.private_directory(pi_dir)
    models_doc = {
        "providers": {
            gateway_bifrost.PI_PROVIDER: bifrost_models.pi_provider(
                facts, BYOK_MODEL, f"http://{addr}"
            )
        }
    }
    settings_doc = {
        "defaultProvider": gateway_bifrost.PI_PROVIDER,
        "defaultModel": BYOK_MODEL,
    }
    runtime_io.write_private_json(pi_dir / "models.json", models_doc)
    runtime_io.write_private_json(pi_dir / "settings.json", settings_doc)
    return str(pi_dir)


def write_byok_profiles(addr: str, creds: ByokCredentials) -> dict[str, str]:
    """Write isolated Codex, Claude Code and Pi profiles pointed at Bifrost's BYOK route."""
    root = byok_home()
    runtime_io.private_directory(root)
    facts: bifrost_models.LlmFacts = {
        "display": creds["model_id"],
        "context": creds["context_window"],
        "efforts": ["low", "medium", "high"],
        "defaultEffort": "medium",
        "vision": False,
    }
    return {
        "CODEX_HOME": _write_codex_profile(root, addr, facts),
        "CLAUDE_CONFIG_DIR": _write_claude_profile(root, addr, creds["context_window"]),
        "PI_CODING_AGENT_DIR": _write_pi_profile(root, addr, facts),
    }


def mount_byok(
    creds: ByokCredentials, facts: HostFacts, event: runtime_io.Event = lambda _: None
) -> tuple[str, dict[str, str]]:
    """Mount ``localmodels-byok`` onto owned Bifrost and generate isolated client profiles;
    ``event`` receives the download events of a Bifrost installed on the way."""
    with library_gateway.gateway_locked():
        try:
            record = library_gateway.ensure_instance(facts, event)
            if record is None:
                raise ByokError("BYOK_GATEWAY_FAILED", "Bifrost gateway could not be prepared.")
            app = Path(record["app_dir"])
            config = gateway_bifrost.read_config(app)
            before, before_sheet = copy.deepcopy(config), library_gateway.read_sheet(app)
            providers = config.setdefault("providers", {})
            providers[BYOK_PROVIDER] = render_byok_provider(creds)
            governance = config.setdefault("governance", {})
            rules = [
                r
                for r in (governance.get("routing_rules") or [])
                if r.get("id") != bifrost_config.BYOK_RULE
            ]
            rules.append(bifrost_config.byok_rule(creds["model_id"]))
            governance["routing_rules"] = rules
            names = (
                [creds["model_id"]]
                if creds["model_id"] == BYOK_MODEL
                else [creds["model_id"], BYOK_MODEL]
            )
            prefix = f"{BYOK_PROVIDER}/"
            kept_sheet = {k: v for k, v in before_sheet.items() if not k.startswith(prefix)}
            sheet = (
                kept_sheet
                | bifrost_datasheet.sheets(BYOK_PROVIDER, names, creds["context_window"])[
                    bifrost_datasheet.DATASHEET
                ]
            )
            library_gateway.apply_config(record, config, sheet)
            try:
                expected = f"{BYOK_PROVIDER}/{BYOK_MODEL}"
                if expected not in bifrost_models.listed(record["addr"]):
                    raise ByokError("BYOK_GATEWAY_FAILED", f"Bifrost did not list {expected}.")
            except BaseException:
                with contextlib.suppress(Exception):
                    library_gateway.apply_config(record, before, before_sheet)
                raise
            env = write_byok_profiles(record["addr"], creds)
            return f"http://{record['addr']}", env
        except ByokError:
            raise
        except (harness.HarnessError, OSError, ValueError, KeyError) as exc:
            raise ByokError("BYOK_GATEWAY_FAILED", str(exc)) from None


def runtime_model_for_byok(runtime: Runtime) -> str:
    """Return the model identifier each Runtime uses for the Bifrost BYOK route."""
    return BYOK_PI_MODEL if runtime == "pi" else BYOK_MODEL


def load_source_state() -> SourceState | None:
    """Read the persisted active model-source state, or None when not yet written."""
    path = _source_path()
    if not path.exists() and not path.is_symlink():
        return None
    runtime_io.private_permissions(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(raw, dict)
        or raw.get("schema") != SOURCE_SCHEMA
        or raw.get("mode") not in MODES
        or raw.get("runtime") not in RUNTIMES
    ):
        return None
    env = raw.get("environment")
    return {
        "schema": SOURCE_SCHEMA,
        "mode": raw["mode"],
        "runtime": raw["runtime"],
        "runtime_model": str(raw.get("runtime_model") or ""),
        "model_label": str(raw["model_label"]) if raw.get("model_label") else None,
        "gateway_url": str(raw["gateway_url"]) if raw.get("gateway_url") else None,
        "environment": {str(k): str(v) for k, v in env.items()} if isinstance(env, dict) else {},
    }


def save_source_state(state: SourceState) -> SourceState:
    """Atomically write the active model-source state."""
    root = hosts.state_dir().resolve()
    runtime_io.private_directory(root)
    runtime_io.write_private_json(_source_path(), state)
    return state
