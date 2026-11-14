#!/usr/bin/env bash
# Packages FocuSee Clone as a standalone macOS app bundle:
#   build/FocuSee Clone.app
#
# Why: running `electron .` from node_modules leaves the app with Electron's
# generic identity ("Electron"), which both looks wrong and — after a capture
# session is torn down mid-recording on macOS — can leave the bundle in a state
# where ScreenCaptureKit refuses new sessions ("Timeout starting video source").
# A named, separately signed bundle gets a fresh identity.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="FocuSee Clone"
BUNDLE_ID="com.focuseeclone.app"
BUILD_DIR="$ROOT/build"
APP="$BUILD_DIR/$APP_NAME.app"
SRC_ELECTRON="$ROOT/node_modules/electron/dist/Electron.app"

[ -d "$SRC_ELECTRON" ] || { echo "electron not installed — run: npm install"; exit 1; }

rm -rf "$APP"
mkdir -p "$BUILD_DIR"
echo "① 复制 Electron 壳…"
cp -R "$SRC_ELECTRON" "$APP"
xattr -cr "$APP" 2>/dev/null || true

echo "② 写入应用身份（Info.plist）…"
PLIST="$APP/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName $APP_NAME" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName $APP_NAME" "$PLIST" 2>/dev/null || \
  /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string $APP_NAME" "$PLIST"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier $BUNDLE_ID" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :LSApplicationCategoryType string public.app-category.video" "$PLIST" 2>/dev/null || true
# NOTE: keep CFBundleExecutable as "Electron" and every helper untouched.
# Renaming the executable (or helpers) breaks the nested code seals — macOS
# then treats the bundle as tampered and screen capture silently fails
# ("Timeout starting video source"). The Finder/dock name comes from
# CFBundleName/DisplayName, which is enough.

echo "③ 放入应用代码…"
APP_RES="$APP/Contents/Resources/app"
mkdir -p "$APP_RES"
cp "$ROOT"/package.json "$ROOT"/main.js "$ROOT"/preload.js "$APP_RES/"
cp -R "$ROOT/renderer" "$APP_RES/renderer"
cp -R "$ROOT/assets" "$APP_RES/assets"

echo "④ 本地签名（ad-hoc）…"
codesign --force --deep --sign - "$APP" 2>/dev/null

echo "✔ 打包完成：$APP"
echo "  打开：open \"$APP\""
