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
# AI 字幕：main.js 在打包版里按 __dirname 找 scripts/asr/generate_captions.py，
# 漏拷会让打包版的 AI 字幕按钮永远置灰。
cp -R "$ROOT/scripts" "$APP_RES/scripts"
# 分割模型走 preload 的 require('@mediapipe/tasks-vision')，需要包内 node_modules 子集
mkdir -p "$APP_RES/node_modules/@mediapipe"
cp "$ROOT/node_modules/@mediapipe/tasks-vision/package.json" "$APP_RES/node_modules/@mediapipe/tasks-vision/" 2>/dev/null || true
cp "$ROOT/node_modules/@mediapipe/tasks-vision/vision_bundle.cjs" "$APP_RES/node_modules/@mediapipe/tasks-vision/" 2>/dev/null || true
cp -R "$ROOT/node_modules/@mediapipe/tasks-vision/wasm" "$APP_RES/node_modules/@mediapipe/tasks-vision/wasm" 2>/dev/null || true

# ④ 签名：默认用自签证书 "FocuSee Clone Dev"（Keychain 已信任）。
# TCC 授权（屏幕录制/摄像头/麦克风）按「签名身份」记忆：ad-hoc 签名每次重打包
# 都是全新身份，授权必掉；自签证书身份固定，重打包后授权保持不变。
# 证书创建/信任方法（一次性）：docs/codesign-selfsigned.md
SIGN_IDENTITY="${CODESIGN_IDENTITY:-FocuSee Clone Dev}"
if [ "$SIGN_IDENTITY" = "-" ]; then
  echo "④ 签名（ad-hoc，显式回退：重打包会丢 TCC 授权）…"
  codesign --force --deep --sign - "$APP" 2>/dev/null
else
  if ! security find-identity -v -p codesigning 2>/dev/null | grep -qF "\"$SIGN_IDENTITY\""; then
    echo "错误：Keychain 中没有受信任的代码签名身份 \"$SIGN_IDENTITY\"。" >&2
    echo "  首次创建/信任（一次性）：docs/codesign-selfsigned.md" >&2
    echo "  临时回退 ad-hoc（会丢 TCC 授权）：CODESIGN_IDENTITY=- $0" >&2
    exit 1
  fi
  echo "④ 签名（自签证书 \"$SIGN_IDENTITY\"，TCC 授权跨重打包稳定）…"
  codesign --force --deep --sign "$SIGN_IDENTITY" "$APP"
  codesign --verify --deep --strict "$APP" || { echo "错误：签名校验失败，打包中止" >&2; exit 1; }
fi

echo "✔ 打包完成：$APP"
echo "  打开：open \"$APP\""
