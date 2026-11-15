#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# focusee-clone 真机交付门（ship gate）—— PR #32–#36 复盘结论的机制化
#
# 背景：2026-11-15 复盘（work/项目复盘-focusee复刻.md / LESSONS E159）认定——
#   「单测全绿 ≠ 真机可用」：复刻全程 6 次用户往返里 4 次致命缺陷（teardown 崩溃、
#   二次停止、拖动窗口崩溃、横幅相机烘焙裁剪）单测结构上测不到。
#   本门是唯一交付入口：不过门 = 不可交付（安装包不更新、PR 不报 ready）。
#
# 门内步骤（③ 起全部基于【打包应用】，不是源码目录直跑——历史缺陷里
# 「control.html 缺失」「e2e 产物写入应用包」都是打包才暴露的）：
#   ① 单元测试（含 tripwire：跨窗口 executeJavaScript / renderer 引用
#      mainWindow / 事件回调读全局状态 / 闩锁复位）
#   ② 打包 build/FocuSee Clone.app（--app 可指向已有包）
#   ③ 打包应用真机 e2e：摄像头 + 连续 3 段 + 第 2 段走取消路径 + 真实拖动
#      预览窗回归（默认 battery：--e2e-rec-takes=3 --e2e-rec-cancel-take=2
#      --e2e-rec-cam；独立临时数据目录，产物不进应用包）
#   ④ e2e 报告全步校验：任何一步 FAIL 即拦；另校验段数/取消不落盘/画中画已烘焙
#   ⑤ 成片断言：每个已保存项目的 recording.webm 时长 > 1s 且
#      帧数 ≥ 12fps×时长（拦「静帧幻灯片」与隐藏窗口节流回归）
#   ⑥ manifest：全过才写 artifacts/ship-gate/manifest.json（git 修订、
#      包代码聚合哈希、e2e 参数、逐步结果），并归档 e2e 报告
#
# 失败行为：exit 1、不写 manifest、不视为可交付；数据与日志留在数据目录供排查
# （脚本最后会打印路径）。
#
# 用法：
#   scripts/ship-gate.sh                      # 完整门
#   scripts/ship-gate.sh --app <已有.app>     # 跳过打包，验已有包
#   scripts/ship-gate.sh --skip-unit          # 仅排查 e2e 时用（verdict 仍按未过门算）
#   scripts/ship-gate.sh --e2e-args "--e2e-rec-two"   # 旧构建回归（负向验证用）
# ---------------------------------------------------------------------------
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="FocuSee Clone"
APP="$ROOT/build/$APP_NAME.app"
GATE_OUT="$ROOT/artifacts/ship-gate"
USE_APP=""
SKIP_UNIT=0
# 注意：--e2e-rec 是精确匹配的入口开关（main.js isE2E_REC），takes/cancel/cam 是它的
# 修饰参数，缺了入口开关应用会以普通 GUI 模式启动并撞单实例锁。
# --focusee-user-data 由脚本在每个运行临时注入（隔离已安装应用的单实例锁——
# main.js 头注释记录的历史坑：锁被占用时 e2e 静默退出）。
E2E_ARGS="--e2e-rec --e2e-rec-takes=3 --e2e-rec-cancel-take=2 --e2e-rec-cam"

while [ $# -gt 0 ]; do
  case "$1" in
    --app) USE_APP="$2"; shift 2 ;;
    --skip-unit) SKIP_UNIT=1; shift ;;
    --e2e-args) E2E_ARGS="$2"; shift 2 ;;
    *) echo "[gate] 未知参数: $1（用法见文件头）"; exit 2 ;;
  esac
done

STEP_NAMES=(); STEP_OKS=(); STEP_DETAILS=()
gate_step() { STEP_NAMES+=("$1"); STEP_OKS+=("$2"); STEP_DETAILS+=("$3"); }
# record 的正式定义在 e2e 段之前不可用——它与 STEP_PREFIX/LAST_FAIL 联动，
# 统一用下方单一实现（避免两份定义漂移）。
LAST_FAIL=0
STEP_PREFIX=""
record() { # record <name> <ok:0|1> <detail>
  gate_step "${STEP_PREFIX}$1" "$2" "$3"
  if [ "$2" = "0" ]; then
    LAST_FAIL=0
    echo "[gate] ok   ${STEP_PREFIX}$1 — $3"
  else
    LAST_FAIL=1
    echo "[gate] FAIL ${STEP_PREFIX}$1 — $3"
  fi
}

GIT_REV="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "[gate] ===== focusee-clone 真机交付门 @ $GIT_REV ====="
echo "[gate] e2e battery: $E2E_ARGS"

# ── ① 单元测试（含 tripwire） ────────────────────────────────────────────────
UNIT_LOG="${TMPDIR:-/tmp}/gate-unit.$$.log"
if [ "$SKIP_UNIT" = 1 ]; then
  record "unit-tests" 1 "SKIP（--skip-unit：verdict 按未过门处理，不可交付）"
else
  if (cd "$ROOT" && npm test) >"$UNIT_LOG" 2>&1; then
    record "unit-tests" 0 "npm test 全过（含 tripwire）"
  else
    record "unit-tests" 1 "npm test 失败，日志: $UNIT_LOG"
    tail -20 "$UNIT_LOG" || true
  fi
fi

# ── ② 打包 ──────────────────────────────────────────────────────────────────
mkdir -p "$GATE_OUT"   # 打包日志落这里；失败路径不写 manifest
if [ -n "$USE_APP" ]; then
  APP="$USE_APP"
fi
if [ ! -d "$APP" ]; then
  if (cd "$ROOT" && npm run package) >"$GATE_OUT.package.log" 2>&1; then
    record "package" 0 "打包完成: $APP"
  else
    record "package" 1 "打包失败，日志: $GATE_OUT.package.log"
    tail -20 "$GATE_OUT.package.log" || true
  fi
else
  record "package" 0 "使用已有包: $APP"
fi

# ── ③④⑤ 真机 e2e + 报告全步校验 + 成片断言（瞬态失败自动重试一次） ─────────
# 重试的理由：摄像头/采集设备被其它应用（如正在运行的已装 FocuSee）瞬态占用时，
# 流获取可能慢于 harness 的等待窗——上次退出码 0、这次步骤挂，属设备竞争不是代码回归。
BIN="$APP/Contents/MacOS/Electron"
BLOCK_FAIL=0
DATA_DIR=""
REPORT_JSON=""

run_e2e_battery() { # $1 = attempt no.
  STEP_PREFIX="a$1/"
  BLOCK_FAIL=0
  DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/focusee-gate.XXXXXX")"
  local E2E_LOG="$DATA_DIR/e2e.log"
  REPORT_JSON="$DATA_DIR/artifacts/e2e-rec-report.json"
  if [ ! -x "$BIN" ]; then
    record "e2e-run" 1 "打包应用不可执行: $BIN"
    BLOCK_FAIL=1
    return 0
  fi
  echo "[gate] e2e 运行中（第 $1 次，数据目录 ${DATA_DIR}）…"
  env FOCUSEE_DATA_DIR="$DATA_DIR" "$BIN" $E2E_ARGS --focusee-user-data "$DATA_DIR/user-data" >"$E2E_LOG" 2>&1 &
  local pid=$!
  local exit_code=""
  local deadline=$((SECONDS + 480))
  while [ $SECONDS -lt $deadline ]; do
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid"; exit_code=$?
      break
    fi
    sleep 2
  done
  if [ -z "$exit_code" ]; then
    kill -9 "$pid" 2>/dev/null || true
    record "e2e-run" 1 "超时 8 分钟未退出（权限弹窗/挂死？），日志: $E2E_LOG"
  else
    record "e2e-run" "$( [ "$exit_code" = 0 ] && echo 0 || echo 1 )" \
      "退出码 ${exit_code}（日志 ${E2E_LOG}）"
  fi
  BLOCK_FAIL=$((BLOCK_FAIL + LAST_FAIL))

  # ── ④ e2e 报告全步校验 ──
  if [ -f "$REPORT_JSON" ]; then
    VERIFY_JSON="$(python3 - "$REPORT_JSON" <<'PYEOF'
import json, sys
r = json.load(open(sys.argv[1]))
steps = r.get("steps", [])
bad = [s for s in steps if not s.get("ok")]
if bad:
    print(json.dumps({"ok": False, "why": "FAIL 步: " + "; ".join(f"{s['name']}({s.get('extra','')})" for s in bad)}, ensure_ascii=False))
    raise SystemExit
# 期望的 take 标签齐全（takes=N 中每段都要有停止/取消证据）
takes = r.get("takes") or 1
cancel = r.get("cancelTake") or 0
for t in range(1, takes + 1):
    tag = f"take{t}"
    names = [s["name"] for s in steps if s["name"].startswith(tag + ":")]
    if not names:
        print(json.dumps({"ok": False, "why": f"{tag} 没有任何步骤记录"}, ensure_ascii=False)); raise SystemExit
# 取消段必须不落盘、非取消段都必须落盘
saved = r.get("projects") or []
expect = takes - (1 if cancel else 0)
if len(saved) != expect:
    print(json.dumps({"ok": False, "why": f"落盘项目数 {len(saved)} ≠ 期望 {expect}: {saved}"}, ensure_ascii=False)); raise SystemExit
# 摄像头段：画中画必须真的烘焙进帧（历史上两次「画中画缺失」都发生在这一步）
if r.get("withCamera"):
    pips = []
    for s in steps:
        if s["name"].endswith("bake-debug") and s.get("extra"):
            try: pips.append(json.loads(s["extra"]).get("pipDrawn", 0))
            except Exception: pass
    if not pips or min(pips) <= 0:
        print(json.dumps({"ok": False, "why": f"bake 阶段画中画未绘制: {pips}"}, ensure_ascii=False)); raise SystemExit
print(json.dumps({"ok": True, "why": f"{len(steps)} 步全过, 落盘 {len(saved)} 段, pipDrawn 校验通过"}, ensure_ascii=False))
PYEOF
)"
    if python3 -c "import json,sys; sys.exit(0 if json.loads(sys.argv[1])['ok'] else 1)" "$VERIFY_JSON"; then
      record "e2e-report" 0 "$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['why'])" "$VERIFY_JSON")"
    else
      record "e2e-report" 1 "$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['why'])" "$VERIFY_JSON")"
    fi
  else
    record "e2e-report" 1 "找不到 e2e 报告: ${REPORT_JSON}（应用未进 e2e 模式？看 ${E2E_LOG}）"
  fi
  BLOCK_FAIL=$((BLOCK_FAIL + LAST_FAIL))

  # ── ⑤ 成片断言（解码帧数） ──
  # 为什么不断言容器时长：MediaRecorder 直出的 WebM 没有时长头（LESSONS E163），
  # 且应用按设计在「首次编辑器加载」时才用 seek-to-end 解析时长并回写 project.json
  # （renderer/app.js load 路径）——e2e 刚存完的落盘时长就是 0，属正常。
  # 所以门检的是物理事实：解码帧数 ≥30 帧/段（正常段 ~70+ 帧；历史「静帧幻灯片」
  # 缺陷只有 2–3 帧——隐藏窗口节流回归在这里必拦）。
  MEDIA_JSON="$(python3 - "$DATA_DIR" <<'PYEOF'
import json, os, subprocess, sys
def verdict(ok, why):
    print(json.dumps({"ok": ok, "why": why}, ensure_ascii=False))
root = sys.argv[1]
pdir = os.path.join(root, "projects")
bad, checked = [], 0
if not os.path.isdir(pdir):
    verdict(False, "无 projects 目录"); raise SystemExit
for name in sorted(os.listdir(pdir)):
    pj = os.path.join(pdir, name, "project.json")
    if not os.path.isfile(pj): continue
    meta = json.load(open(pj))
    if meta.get("id") == "sample": continue  # 自带示例项目不是录制产物
    webm = os.path.join(pdir, name, "recording.webm")
    if not os.path.isfile(webm):
        bad.append(f"{name}: 缺 recording.webm"); continue
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_frames", "-of", "json", webm],
            capture_output=True, text=True, timeout=120).stdout
        frames = int(json.loads(out)["streams"][0].get("nb_read_frames") or 0)
    except Exception as e:
        bad.append(f"{name}: ffprobe 失败 {e}"); continue
    checked += 1
    if frames < 30:
        bad.append(f"{name}: 解码帧 {frames} < 30（静帧/节流回归）")
if bad:
    verdict(False, "; ".join(bad)); raise SystemExit
verdict(True, f"{checked} 个录制产物达标（解码帧数 ≥30/段）")
PYEOF
)"
  if python3 -c "import json,sys; sys.exit(0 if json.loads(sys.argv[1])['ok'] else 1)" "$MEDIA_JSON"; then
    record "media-assert" 0 "$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['why'])" "$MEDIA_JSON")"
  else
    record "media-assert" 1 "$(python3 -c "import json,sys; print(json.loads(sys.argv[1])['why'])" "$MEDIA_JSON")"
  fi
  BLOCK_FAIL=$((BLOCK_FAIL + LAST_FAIL))
}

ATTEMPT=1
while :; do
  run_e2e_battery "$ATTEMPT"
  [ "$BLOCK_FAIL" = 0 ] && break
  [ "$ATTEMPT" -ge 3 ] && break
  ATTEMPT=$((ATTEMPT + 1))
  echo "[gate] e2e 第 $((ATTEMPT - 1)) 次未过，45 秒后重试（让 ScreenCaptureKit/摄像头服务恢复；频繁重启捕获会触发系统级启动超时）…"
  sleep 45
done

# ── 裁决 ─────────────────────────────────────────────────────────────────────
echo "[gate] ===== 裁决 ====="
have_fail=0
i=0
while [ $i -lt ${#STEP_NAMES[@]} ]; do
  if [ "${STEP_OKS[$i]}" != "ok" ]; then have_fail=1; fi
  i=$((i + 1))
done
if [ "$have_fail" = 0 ]; then
  mkdir -p "$GATE_OUT"
  BUNDLE_HASH="$(cd "$APP/Contents/Resources/app" && find . -type f -not -path './node_modules/*' -print0 | sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)"
  STEPS_TSV="$GATE_OUT/.steps.tsv"
  : >"$STEPS_TSV"
  i=0
  while [ $i -lt ${#STEP_NAMES[@]} ]; do
    printf '%s\t%s\t%s\n' "${STEP_NAMES[$i]}" "${STEP_OKS[$i]}" "${STEP_DETAILS[$i]}" >>"$STEPS_TSV"
    i=$((i + 1))
  done
  python3 - "$GATE_OUT/manifest.json" "$GIT_REV" "$BUNDLE_HASH" "$APP" "$E2E_ARGS" "$STEPS_TSV" <<'PYEOF'
import json, sys, datetime
out, rev, bh, app, args, tsv = sys.argv[1:7]
steps = []
with open(tsv, encoding="utf-8") as f:
    for line in f:
        name, verd, detail = line.rstrip("\n").split("\t", 2)
        steps.append({"name": name, "verdict": verd, "detail": detail})
json.dump({
    "verdict": "PASS", "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    "git_rev": rev, "bundle": {"path": app, "app_code_sha256": bh},
    "e2e_args": args.split(), "steps": steps,
}, open(out, "w"), ensure_ascii=False, indent=1)
PYEOF
  rm -f "$STEPS_TSV"
  cp "$REPORT_JSON" "$GATE_OUT/e2e-rec-report.json" 2>/dev/null || true
  echo "[gate] ✔ SHIP GATE PASSED — manifest: $GATE_OUT/manifest.json"
  echo "[gate] 可交付：安装包更新/PR 报 ready 前的唯一凭据即本 manifest。"
  exit 0
else
  echo "[gate] ✗ SHIP GATE FAILED — 不写 manifest，不可交付。"
  echo "[gate] 排查现场（勿删）：$DATA_DIR"
  echo "[gate] 步骤明细："
  i=0
  while [ $i -lt ${#STEP_NAMES[@]} ]; do
    echo "[gate]   [${STEP_OKS[$i]}]  ${STEP_NAMES[$i]} — ${STEP_DETAILS[$i]}"
    i=$((i + 1))
  done
  exit 1
fi
