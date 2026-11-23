"""Native runtime filesystem and download boundary; only regular archive members."""

from __future__ import annotations

import contextlib
import errno
import hashlib
import http.client
import os
import re
import shutil
import socket
import ssl
import stat
import subprocess
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

# remote_ops before remote_ops_download: the bundle's entry module loads its siblings
from localmodels import npm_transport, region, remote_ops, remote_ops_download, runtime_windows_acl

Event = Callable[[dict[str, Any]], None]


def regular_directories(path: Path) -> None:
    """Validate existing directory components without creating or repairing them."""
    for parent in [*reversed(path.parents), path]:
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Unsafe runtime root")
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("Runtime parent must be a directory")


def validate_runtime_root(root: Path) -> Path:
    if not root.is_absolute():
        raise ValueError("Runtime root must be absolute")
    if any(part == ".." for part in root.parts):
        raise ValueError("Runtime root must be normalized")
    regular_directories(root)
    if root.exists():
        private_permissions(root)
    return root


def _create_private_directory(path: Path) -> bool:
    """Create missing directories privately; return True when ``path`` itself was created."""
    if not path.is_absolute() or any(part == ".." for part in path.parts):
        raise ValueError("Runtime directory must be absolute and normalized")
    regular_directories(path)
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    if not missing:
        private_permissions(path)
        return False
    created = False
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            private_permissions(directory)
            created = False
        else:
            private_permissions(directory, created=True)
            created = True
    return created


def private_directory(path: Path) -> None:
    """Create each missing directory privately; existing state must already be private."""
    _create_private_directory(path)


def private_permissions(path: Path, *, created: bool = False) -> None:
    """Repair only new owned state. Existing broad or foreign permissions fail closed."""
    regular_directories(path.parent)
    info = path.lstat()
    if (
        stat.S_ISLNK(info.st_mode)
        or getattr(info, "st_file_attributes", 0) & 0x400
        or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode))
    ):
        raise ValueError("Unsafe runtime state type")
    if os.name == "nt":
        _windows_private(path, created)
        return
    if info.st_uid != os.getuid():
        raise ValueError("Runtime state has a foreign owner")
    if created:
        path.chmod(0o700 if stat.S_ISDIR(info.st_mode) or info.st_mode & 0o111 else 0o600)
    elif info.st_mode & 0o077:
        raise ValueError("Existing runtime state must already be private")


_windows_api = runtime_windows_acl.api
_windows_private = runtime_windows_acl.private_permissions
_private_dacl_entries = runtime_windows_acl.private_dacl_entries
_windows_sid_text = runtime_windows_acl.sid_text


def _safe_member(name: str) -> Path:
    parts = name.rstrip("/").split("/")
    if (
        not name
        or name.startswith("/")
        or "\\" in name
        or any(
            p in ("", "..")
            or ":" in p
            or p.endswith((".", " "))
            or re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", p)
            for p in parts
            if p != "."
        )
    ):
        raise ValueError("Unsafe archive path")
    return Path(*parts)


def _ensure_extract_dir(directory: Path, known: set[Path] | None) -> None:
    if known is None:
        private_directory(directory)
        return
    if directory in known:
        return
    missing: list[Path] = []
    current = directory
    while current not in known:
        if current == current.parent:
            raise ValueError("Unsafe archive path")
        missing.append(current)
        current = current.parent
    for part in reversed(missing):
        try:
            part.mkdir(mode=0o700)
        except FileExistsError as exc:
            raise ValueError("Runtime parent must be a directory") from exc
        if os.name != "nt":
            part.chmod(0o700)
        known.add(part)


def _write_extracted(source: Any, destination: Path, mode: int, *, inherited: bool) -> None:
    if inherited:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        with os.fdopen(os.open(destination, flags, mode), "wb") as output:
            shutil.copyfileobj(source, output)
        if os.name != "nt":
            destination.chmod(mode)
        return
    with destination.open("xb") as output:
        shutil.copyfileobj(source, output)
    if os.name != "nt":
        destination.chmod(mode)
    private_permissions(destination, created=True)


def _extract_archive(archive: Path, target: Path) -> None:
    """Validate the complete member list before writing; never materialize links."""
    # A freshly created target has a protected OICI DACL on Windows, so new subdirectories and
    # files beneath it inherit owner-only access without per-file SetNamedSecurityInfoW calls.
    fresh = _create_private_directory(target)
    known = {target} if fresh else None
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as stream:
            members = stream.infolist()
            for member in members:
                _safe_member(member.filename)
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode) or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError("Unsafe archive member")
            for member in members:
                destination = target / _safe_member(member.filename)
                if member.is_dir():
                    _ensure_extract_dir(destination, known)
                else:
                    _ensure_extract_dir(destination.parent, known)
                    with stream.open(member) as source:
                        _write_extracted(source, destination, 0o600, inherited=fresh)
        return
    with tarfile.open(archive) as tar:
        # npm tarballs may repeat a/b as a/./b; the last wins, as with tar (scripts/pin_pi.py
        # refuses a pinned Pi archive whose repeats differ).
        entries_all = tar.getmembers()
        for entry in entries_all:  # every member, before a repeat could hide a link or device
            _safe_member(entry.name)
            if not (entry.isfile() or entry.isdir()):
                raise ValueError("Unsafe archive member")
        entries = list({_safe_member(e.name): e for e in entries_all}.values())
        for entry in entries:
            destination = target / _safe_member(entry.name)
            if entry.isdir():
                _ensure_extract_dir(destination, known)
                continue
            _ensure_extract_dir(destination.parent, known)
            tar_source = tar.extractfile(entry)
            if tar_source is None:
                raise ValueError("Unsafe archive member")
            with tar_source:
                _write_extracted(
                    tar_source, destination, 0o700 if entry.mode & 0o111 else 0o600, inherited=fresh
                )


DOWNLOAD_ATTEMPTS = 5
# One timeout covers the connection, the response headers and each read: a retry resumes the
# kept bytes, so a stalled connection is cheap to replace and needs no separate read timeout.
DOWNLOAD_TIMEOUT_S = 15
# A host that delivers less than SLOW_BYTES_PER_S over a whole SLOW_WINDOW_S window is left for
# another host serving the same file, when one is still worth trying (see ``download``).
SLOW_BYTES_PER_S = 512 * 1024
SLOW_WINDOW_S = 15
_RETRY_HTTP = frozenset({408, 425, 429, 500, 502, 503, 504})


class RuntimeDownloadError(ValueError):
    """A pinned artifact could not be downloaded. The message names only the host, the file,
    a fixed reason and the bytes kept: no URL query, header or response body."""

    def __init__(
        self, url: str, reason: str, kept: int, *, retryable: bool, slow: bool = False
    ) -> None:
        parts = urllib.parse.urlsplit(url)
        self.host = parts.hostname or "the download host"
        self.file = parts.path.rsplit("/", 1)[-1] or "artifact"
        self.reason = reason
        self.kept = kept
        self.retryable = retryable
        self.slow = slow  # the host was left for being too slow, not for failing
        message = f"Download of {self.file} from {self.host} failed: {reason}."
        if kept:
            message += f" {kept} bytes are kept; a retry resumes from there."
        if retryable:
            message += (
                f" Check that this computer can reach {self.host} (network, proxy or firewall),"
                " then retry."
            )
        super().__init__(message)


class _TransferError(Exception):
    def __init__(self, reason: str, *, retryable: bool = True, slow: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable
        self.slow = slow


def _network_reason(exc: BaseException) -> tuple[str, bool]:
    """A fixed description of a network failure, and whether trying again can help."""
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}", exc.code in _RETRY_HTTP
    if isinstance(exc, npm_transport.UnsafeRedirect):
        return "the server redirected to a URL without HTTPS or with credentials", False
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, BaseException):
        exc = exc.reason
    if isinstance(exc, ssl.SSLCertVerificationError):
        return "the server's TLS certificate is not trusted", False
    if isinstance(exc, socket.gaierror):
        return "host name lookup failed", True
    if isinstance(exc, TimeoutError):
        return "timed out", True
    if isinstance(exc, ConnectionRefusedError):
        return "connection refused", True
    if isinstance(exc, ConnectionResetError):
        return "connection reset", True
    if isinstance(exc, ssl.SSLError):
        return "TLS connection failed", True
    if isinstance(exc, http.client.IncompleteRead | http.client.RemoteDisconnected):
        return "connection closed before the download finished", True
    if isinstance(exc, http.client.HTTPException):
        return "invalid HTTP response", True
    return f"network error ({type(exc).__name__})", True


_NETWORK_ERRORS = (OSError, http.client.HTTPException)


class Rate:
    """The download rate over the last full second, and the seconds left at it: optional
    ``bytesPerSecond`` and ``etaSeconds`` of a progress event, absent for the first second."""

    def __init__(self, completed: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self.mark, self.marked = clock(), completed
        self.rate: int | None = None

    def fields(self, completed: int, total: int | None) -> dict[str, int]:
        now = self.clock()
        if now - self.mark >= 1.0:
            self.rate = max(0, int((completed - self.marked) / (now - self.mark)))
            self.mark, self.marked = now, completed
        if self.rate is None:
            return {}
        found = {"bytesPerSecond": self.rate}
        if total is not None and self.rate > 0:
            found["etaSeconds"] = -(-max(0, total - completed) // self.rate)
        return found


def _transfer(
    url: str,
    part: Path,
    limit: int,
    event: Event,
    *,
    retry_missing: bool,
    slow_abort: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """One request for the rest of ``part``; network failures raise _TransferError. With
    ``slow_abort``, a whole SLOW_WINDOW_S below SLOW_BYTES_PER_S raises one marked ``slow``."""
    have = part.stat().st_size
    request = urllib.request.Request(url, headers={"User-Agent": "localmodels-runtime"})
    if have:
        request.add_header("Range", f"bytes={have}-")
    try:
        # Redirects stay on HTTPS without credentials, as for every npm download of this tool.
        source = npm_transport.https_opener().open(request, timeout=DOWNLOAD_TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and retry_missing:
            raise _TransferError("HTTP 404") from None
        if exc.code == 416 and have:
            part.write_bytes(b"")  # the kept part no longer matches; start over
            raise _TransferError("the server could not resume the download") from None
        raise _interrupted(exc) from None
    except _NETWORK_ERRORS as exc:
        raise _interrupted(exc) from None
    with source:
        resumed = (
            have > 0
            and source.status == 206
            and str(source.headers.get("Content-Range", "")).startswith(f"bytes {have}-")
        )
        completed = have if resumed else 0
        length = source.headers.get("Content-Length")
        total = completed + int(length) if length and length.isdigit() else None
        rate = Rate(completed)
        window, window_bytes = clock(), 0
        with part.open("ab" if resumed else "wb") as output:
            while True:
                try:
                    chunk = source.read(1024 * 1024)
                except _NETWORK_ERRORS as exc:
                    raise _interrupted(exc) from None
                if not chunk:
                    break
                completed += len(chunk)
                if completed > limit:
                    output.truncate(0)
                    raise ValueError("Runtime artifact exceeds size limit")
                output.write(chunk)
                window_bytes += len(chunk)
                elapsed = clock() - window
                # The rest arriving within one window at the floor is not worth another host
                # (it also keeps a finished file from being left on its last read).
                near_done = (
                    total is not None and total - completed <= SLOW_BYTES_PER_S * SLOW_WINDOW_S
                )
                if slow_abort and elapsed >= SLOW_WINDOW_S and not near_done:
                    if window_bytes < SLOW_BYTES_PER_S * elapsed:
                        raise _TransferError("the download is too slow", slow=True)
                    window, window_bytes = window + elapsed, 0
                event(
                    {
                        "kind": "progress",
                        "stage": "download",
                        "completed": completed,
                        "total": total,
                        "unit": "bytes",
                        **rate.fields(completed, total),
                    }
                )
    if total is not None and completed < total:
        raise _TransferError("connection closed before the download finished")


def _interrupted(exc: BaseException) -> _TransferError:
    reason, retryable = _network_reason(exc)
    return _TransferError(reason, retryable=retryable)


def download_urls(url: str) -> list[str]:
    """``url`` and the other hosts serving the same file (the npm mirror for the npm registry
    and nodejs.org), in the download region's order. A URL with no other host does not resolve
    the region."""
    source: remote_ops.Source = {"source": "", "url": url}
    every = [url, *(s["url"] for s in remote_ops_download.alternates(source))]
    if len(every) == 1:
        return every
    cn = [u for u in every if remote_ops_download.side(u) == "cn"]
    return region.prefer(region.current_region(), [u for u in every if u not in cn], cn)


def _host(url: str) -> str:
    """The host name of ``url`` alone: events never carry a path, query or credentials."""
    return urllib.parse.urlsplit(url).hostname or ""


def download(
    artifact: dict[str, Any],
    destination: Path,
    event: Event,
    *,
    attempts: int = DOWNLOAD_ATTEMPTS,
    pause: Callable[[float], None] = time.sleep,
    retry_missing: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    """Fetch a pinned artifact into ``destination``, which must not exist. Network failures are
    retried with backoff and each retry resumes ``destination.part``; a part left by an earlier
    call is resumed too, also from another host, since the bytes are pinned by digest. Only
    content matching the pinned digest is published.

    The hosts serving the same file (``download_urls``) are tried in turn. A host that fails
    every retry is dropped. A host slower than SLOW_BYTES_PER_S is left once for the next host
    and queued again last, never to be left for slowness again; only a host followed by one not
    yet left for slowness may be left, so a uniformly slow network switches once and the last
    host always finishes. A success on the other region's side after a failure on the preferred
    side switches the region."""
    urls = deque(download_urls(artifact["url"]))
    preferred = remote_ops_download.side(urls[0])
    failed_preferred = False
    slow: set[str] = set()  # hosts already left once for slowness
    while urls:
        url = urls.popleft()
        try:
            _download_from(
                url,
                artifact,
                destination,
                event,
                attempts=attempts,
                pause=pause,
                retry_missing=retry_missing,
                slow_abort=url not in slow and any(u not in slow for u in urls),
                clock=clock,
            )
        except RuntimeDownloadError as exc:
            if exc.slow:
                slow.add(url)
                urls.append(url)
            else:
                # Only a failure moves the region: the region also picks model hubs, so a slow
                # npm mirror must not send a cn user's model downloads to huggingface.co.
                failed_preferred = failed_preferred or remote_ops_download.side(url) == preferred
            if not urls:
                raise
            event(
                {
                    "kind": "stage",
                    "stage": "download",
                    "state": "switching",
                    "from": _host(url),
                    "to": _host(urls[0]),
                    "reason": "slow" if exc.slow else exc.reason,
                    "completed": exc.kept,
                }
            )
            continue
        used = remote_ops_download.side(url)
        if failed_preferred and used and used != preferred:
            region.fallback_to(used)
        return


def _download_from(
    url: str,
    artifact: dict[str, Any],
    destination: Path,
    event: Event,
    *,
    attempts: int,
    pause: Callable[[float], None],
    retry_missing: bool,
    slow_abort: bool = False,
    clock: Callable[[], float] = time.monotonic,
) -> None:
    part = destination.with_name(destination.name + ".part")
    if destination.exists() or destination.is_symlink():
        raise ValueError("Runtime download destination exists")
    if part.exists() or part.is_symlink():
        private_permissions(part)
        if part.stat().st_size > artifact["maxBytes"]:
            part.write_bytes(b"")
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        os.close(os.open(part, flags, 0o600))
        private_permissions(part, created=True)
    # Bytes kept by an earlier call: they may be another version's when the pin changed.
    resumed = part.stat().st_size > 0
    if resumed and _matches(part, artifact):
        _publish(part, destination)
        return
    while True:
        attempt = 0
        while True:
            attempt += 1
            event(
                {
                    "kind": "stage",
                    "stage": "download",
                    "state": "connecting",
                    "host": _host(url),
                    "attempt": attempt,
                    "attempts": attempts,
                }
            )
            try:
                _transfer(
                    url,
                    part,
                    artifact["maxBytes"],
                    event,
                    retry_missing=retry_missing,
                    slow_abort=slow_abort,
                    clock=clock,
                )
                break
            except _TransferError as exc:
                kept = part.stat().st_size
                if exc.slow:  # not retried here: the caller moves to another host
                    raise RuntimeDownloadError(
                        url, exc.reason, kept, retryable=True, slow=True
                    ) from None
                if not exc.retryable or attempt >= attempts:
                    raise RuntimeDownloadError(
                        url, exc.reason, kept, retryable=exc.retryable
                    ) from None
                wait = min(30, 2**attempt)
                event(
                    {
                        "kind": "stage",
                        "stage": "download",
                        "state": "retrying",
                        "attempt": attempt,
                        "attempts": attempts,
                        "reason": exc.reason,
                        "completed": kept,
                        "waitSeconds": wait,
                    }
                )
                pause(wait)
        if _matches(part, artifact):
            break
        if resumed:  # restart once from zero on this host rather than blame it
            part.write_bytes(b"")
            resumed = False
            continue
        part.unlink()
        raise RuntimeDownloadError(
            url, "the content does not match the pinned digest", 0, retryable=True
        )
    _publish(part, destination)


def _matches(part: Path, artifact: dict[str, Any]) -> bool:
    digest = hashlib.new(artifact["algorithm"])
    with part.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return bool(digest.hexdigest() == artifact["digest"])


def _publish(part: Path, destination: Path) -> None:
    part.rename(destination)
    private_permissions(destination)


def _extract_binary(archive: Path, member_name: str, destination: Path) -> None:
    """Extract one pinned regular executable from vendor archives containing other links."""
    _safe_member(member_name)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zip_stream:
            for member in zip_stream.infolist():
                _safe_member(member.filename)
            entry = zip_stream.getinfo(member_name)
            if stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG) or entry.is_dir():
                raise ValueError("Unsafe archive executable")
            with zip_stream.open(entry) as source, destination.open("xb") as output:
                shutil.copyfileobj(source, output)
    else:
        with tarfile.open(archive) as tar:
            for entry_tar in tar.getmembers():
                _safe_member(entry_tar.name)
            member_tar = tar.getmember(member_name)
            if not member_tar.isfile():
                raise ValueError("Unsafe archive executable")
            tar_source = tar.extractfile(member_tar)
            if tar_source is None:
                raise ValueError("Unsafe archive executable")
            with tar_source, destination.open("xb") as output:
                shutil.copyfileobj(tar_source, output)
    destination.chmod(0o700)
    private_permissions(destination, created=True)


def cached_download(
    cache: Path, artifact: dict[str, Any], event: Event, fetch: Callable[..., None]
) -> Path:
    """The verified copy of ``artifact`` kept in ``cache``, downloading (or resuming) it with
    ``fetch`` when missing or changed."""
    algorithm, digest = str(artifact["algorithm"]), str(artifact["digest"])
    if algorithm not in ("sha256", "sha512"):
        raise ValueError("Invalid runtime artifact digest")
    sha = hashlib.new(algorithm)  # npm artifacts (Codex) pin sha512, the rest sha256
    if not re.fullmatch(f"[0-9a-f]{{{sha.digest_size * 2}}}", digest):
        raise ValueError("Invalid runtime artifact digest")
    private_directory(cache)
    kept = cache / digest
    if kept.exists() or kept.is_symlink():
        private_permissions(kept)
        with kept.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                sha.update(chunk)
        if sha.hexdigest() == digest:
            event({"kind": "stage", "stage": "download", "state": "reused"})
            return kept
        kept.unlink()
    fetch(artifact, kept, event)
    return kept


def error_cause(error: BaseException) -> str:
    """What went wrong, without native tool output or anything read from the network."""
    if isinstance(error, RuntimeDownloadError):
        return str(error).removesuffix(".")
    if isinstance(error, OSError):
        name = errno.errorcode.get(error.errno or 0, type(error).__name__)
        where = f" at {error.filename}" if error.filename else ""
        return f"{error.strerror or type(error).__name__} ({name}){where}"
    if isinstance(error, KeyError):
        return f"missing field {error.args[0]!r}" if error.args else "missing field"
    if isinstance(error, subprocess.SubprocessError):
        return type(error).__name__
    text = str(error)
    # This tool's own errors are fixed sentences; other text (int(), parsers) may quote input.
    if type(error) is ValueError and re.fullmatch(r"[A-Z][\w ,;()/.-]{0,160}", text):
        return text
    return type(error).__name__


def extract_archive(archive: Path, target: Path) -> None:
    """Unpack only regular files and directories; a damaged archive is a ValueError."""
    with _archive_errors():
        _extract_archive(archive, target)


def extract_binary(archive: Path, member_name: str, destination: Path) -> None:
    """Extract one pinned regular executable from vendor archives containing other links."""
    with _archive_errors():
        _extract_binary(archive, member_name, destination)


@contextlib.contextmanager
def _archive_errors() -> Any:
    try:
        yield
    except (tarfile.TarError, zipfile.BadZipFile, EOFError) as exc:
        raise ValueError("Invalid runtime archive") from exc


def write_private_json(path: Path, value: object) -> None:
    """Atomically replace owner-only controller state without following an existing link."""
    import json
    import tempfile

    private_directory(path.parent)
    if path.exists() or path.is_symlink():
        private_permissions(path)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    staged = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        private_permissions(staged, created=True)
        os.replace(staged, path)
    finally:
        staged.unlink(missing_ok=True)


@contextlib.contextmanager
def private_lock(path: Path, *, blocking: bool = True) -> Any:
    """Cross-platform advisory lock for one owned controller, never a PID-only lease."""
    private_directory(path.parent)
    if path.exists() or path.is_symlink():
        private_permissions(path)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        private_permissions(path, created=True)
        if os.name == "nt":
            import msvcrt

            if os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            os.lseek(descriptor, 0, 0)
            cast(Any, msvcrt).locking(
                descriptor,
                cast(Any, msvcrt).LK_LOCK if blocking else cast(Any, msvcrt).LK_NBLCK,
                1,
            )
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield
    finally:
        os.close(descriptor)
