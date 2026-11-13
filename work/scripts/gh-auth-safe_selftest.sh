#!/bin/bash
# gh-auth-safe_selftest.sh — P1 设备授权单点入口自测（脚本级，fake gh，不依赖真实 GitHub/钥匙串）
# 覆盖：scope 校验通过/缺少、并发串行锁、失效锁清理、等待已存在的 gh auth 流（不杀进程）、
#       status/doctor 基本可用、日志落盘。
# 用法：bash ~/.dsh/bin/gh-auth-safe_selftest.sh
set -u
BIN_DIR="${SELFTEST_BIN:-$HOME/.dsh/bin}"
WRAP="$BIN_DIR/gh-auth-safe.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/gh-auth-safe.XXXXXX")"
trap 'rm -rf "$TMP" "${SLOWBIN:-}"' EXIT
FAKE_HOME="$TMP/home"
BIN="$TMP/bin"
mkdir -p "$FAKE_HOME" "$BIN"
pass=0
fail=0

cat >"$BIN/gh" <<'EOF'
#!/bin/bash
# fake gh：足够支撑 wrapper 的 auth status / api
if [ "$1" = "auth" ] && [ "$2" = "status" ]; then
  if [ "${3:-}" = "--json" ]; then
    echo '{"hosts":{"github.com":[{"state":"success","active":true,"host":"github.com","login":"tester","tokenSource":"keyring","scopes":"gist, read:org, repo, workflow","gitProtocol":"https"}]}}'
  else
    echo "github.com"
    echo "  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'"
  fi
  exit 0
fi
if [ "$1" = "api" ] && [ "$2" = "-i" ]; then
  printf 'HTTP/2.0 200 OK\r\nX-OAuth-Scopes: gist, read:org, repo, workflow\r\n\r\n{}'
  exit 0
fi
if [ "$1" = "api" ]; then
  echo "tester"
  exit 0
fi
exit 1
EOF
chmod +x "$BIN/gh"

runw() { # runw <args...> ; stdout/err -> $TMP/{out,err}.txt, echo rc
  ( HOME="$FAKE_HOME" PATH="$BIN:$PATH" "$WRAP" "$@" ) >"$TMP/out.txt" 2>"$TMP/err.txt"
  echo $?
}

# 1) verify 通过
rc="$(runw verify -s workflow)"
if [ "$rc" = 0 ] && grep -q '授权校验通过' "$TMP/err.txt"; then
  pass=$((pass + 1)); echo "ok   verify-pass                                   rc=$rc"
else
  fail=$((fail + 1)); echo "FAIL verify-pass expected rc=0 + 通过"; sed 's/^/     /' "$TMP/err.txt" | head -4
fi

# 2) verify 缺少 scope -> rc=3
rc="$(runw verify -s admin:org)"
if [ "$rc" = 3 ] && grep -q '缺少：admin:org' "$TMP/err.txt"; then
  pass=$((pass + 1)); echo "ok   verify-missing-scope                         rc=$rc"
else
  fail=$((fail + 1)); echo "FAIL verify-missing-scope expected rc=3 + 缺少 admin:org"; sed 's/^/     /' "$TMP/err.txt" | head -4
fi

# 3) 并发串行锁：两个 dry-run 应串行（第二个等待第一个），结果都 rc=0
start=$(date +%s)
( HOME="$FAKE_HOME" PATH="$BIN:$PATH" GH_AUTH_DRY_RUN=1 GH_AUTH_DRY_HOLD=1 "$WRAP" refresh -s workflow ) >"$TMP/a.out" 2>"$TMP/a.err" &
p1=$!
sleep 0.3
( HOME="$FAKE_HOME" PATH="$BIN:$PATH" GH_AUTH_DRY_RUN=1 GH_AUTH_DRY_HOLD=1 "$WRAP" refresh -s workflow ) >"$TMP/b.out" 2>"$TMP/b.err" &
p2=$!
wait "$p1"; r1=$?
wait "$p2"; r2=$?
elapsed=$(( $(date +%s) - start ))
if [ "$r1" = 0 ] && [ "$r2" = 0 ] && [ "$elapsed" -ge 2 ] && grep -q '串行等待' "$TMP/b.err"; then
  pass=$((pass + 1)); echo "ok   lock-serializes                              rc=$r1/$r2 elapsed=${elapsed}s"
else
  fail=$((fail + 1)); echo "FAIL lock-serializes expected rc=0/0 elapsed>=2 + 串行等待, got rc=$r1/$r2 elapsed=${elapsed}s"
  sed 's/^/     /' "$TMP/b.err" | head -4
fi
if [ ! -d "$FAKE_HOME/.dsh/state/gh-auth.lock" ]; then
  pass=$((pass + 1)); echo "ok   lock-released"
else
  fail=$((fail + 1)); echo "FAIL lock-released: lock dir still exists"
fi

# 4) 失效锁（持有 pid 已退出）自动清理
mkdir -p "$FAKE_HOME/.dsh/state/gh-auth.lock"
echo 999999 >"$FAKE_HOME/.dsh/state/gh-auth.lock/pid"
rc="$( ( HOME="$FAKE_HOME" PATH="$BIN:$PATH" GH_AUTH_DRY_RUN=1 "$WRAP" refresh -s workflow ) >"$TMP/out.txt" 2>"$TMP/err.txt"; echo $? )"
if [ "$rc" = 0 ] && grep -q '清理失效锁' "$TMP/err.txt"; then
  pass=$((pass + 1)); echo "ok   stale-lock-cleaned                           rc=$rc"
else
  fail=$((fail + 1)); echo "FAIL stale-lock-cleaned expected rc=0 + 清理失效锁"; sed 's/^/     /' "$TMP/err.txt" | head -4
fi

# 5) 已有 gh auth 流程在跑：等待其自然结束（不杀）
SLOWBIN="$(mktemp -d "${TMPDIR:-/tmp}/slowflow.XXXXXX")"
printf '#!/bin/bash\nsleep 2\n' >"$SLOWBIN/gh"
chmod +x "$SLOWBIN/gh"
"$SLOWBIN/gh" auth refresh >/dev/null 2>&1 &
slowpid=$!
sleep 0.3
start=$(date +%s)
rc="$( ( HOME="$FAKE_HOME" PATH="$BIN:$PATH" GH_AUTH_DRY_RUN=1 "$WRAP" refresh -s workflow ) >"$TMP/out.txt" 2>"$TMP/err.txt"; echo $? )"
elapsed=$(( $(date +%s) - start ))
wait "$slowpid" 2>/dev/null
if [ "$rc" = 0 ] && [ "$elapsed" -ge 2 ] && grep -q '等待其自然结束' "$TMP/err.txt"; then
  pass=$((pass + 1)); echo "ok   waits-running-flow                           rc=$rc elapsed=${elapsed}s"
else
  fail=$((fail + 1)); echo "FAIL waits-running-flow expected rc=0 elapsed>=2 + 等待其自然结束, got rc=$rc elapsed=${elapsed}s"
  sed 's/^/     /' "$TMP/err.txt" | head -4
fi

# 6) status / doctor 基本可用
rc="$(runw status)"
if [ "$rc" = 0 ]; then
  pass=$((pass + 1)); echo "ok   status                                        rc=$rc"
else
  fail=$((fail + 1)); echo "FAIL status expected rc=0 got $rc"
fi
rc="$(runw doctor)"
if [ "$rc" = 0 ] && grep -q '锁目录' "$TMP/out.txt"; then
  pass=$((pass + 1)); echo "ok   doctor                                        rc=$rc"
else
  fail=$((fail + 1)); echo "FAIL doctor expected rc=0 + 锁目录"
fi

# 7) 日志落盘
if [ -s "$FAKE_HOME/.dsh/state/gh-auth-safe.log" ]; then
  pass=$((pass + 1)); echo "ok   log-written"
else
  fail=$((fail + 1)); echo "FAIL log-written missing gh-auth-safe.log"
fi

echo "gh-auth-safe selftest: pass=$pass fail=$fail"
[ "$fail" = 0 ]
