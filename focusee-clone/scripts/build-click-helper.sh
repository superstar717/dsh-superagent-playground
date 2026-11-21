#!/usr/bin/env bash
# Builds the macOS global click-tap helper as a universal binary.
#
#   native/click-tap/main.swift -> build/focusee-click-tap
#
# Universal (arm64 + x86_64) so the helper runs on any Mac the app is packaged
# on. Requires the Xcode Command Line Tools (swiftc); if they are missing the
# script exits non-zero and the app simply stays on the dwell fallback — the
# helper is an enhancement, never a hard dependency of recording.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/native/click-tap/main.swift"
OUT="$ROOT/build/focusee-click-tap"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

command -v swiftc >/dev/null || { echo "swiftc not found — install Xcode Command Line Tools"; exit 3; }

mkdir -p "$ROOT/build"

# Both slices always: swiftc cross-compiles the non-host arch fine for this
# pure-Swift tool, so the helper runs natively on Apple Silicon and Intel.
ARCHS=(arm64 x86_64)

OBJECTS=()
for arch in "${ARCHS[@]}"; do
  BIN="$TMP/focusee-click-tap-$arch"
  echo "swiftc ($arch)…"
  swiftc -O -target "${arch}-apple-macos10.15" "$SRC" -o "$BIN"
  OBJECTS+=("$BIN")
done

if [ "${#OBJECTS[@]}" -eq 2 ]; then
  lipo -create -output "$OUT" "${OBJECTS[@]}"
else
  cp "${OBJECTS[0]}" "$OUT"
fi

# Ad-hoc signature keeps Gatekeeper quiet for direct (dev) execution; the
# packaged app re-signs the helper with the app's own identity.
codesign --force --sign - "$OUT" 2>/dev/null || true
chmod +x "$OUT"

echo "built: $OUT"
file "$OUT"
