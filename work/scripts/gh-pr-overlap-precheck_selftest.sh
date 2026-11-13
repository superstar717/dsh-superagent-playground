#!/bin/bash
# gh-pr-overlap-precheck_selftest.sh — P2 重复 PR 预检自测（脚本级，不依赖宿主/真实 gh）
# 覆盖：有重叠→stderr 警告且 rc=0；无重叠→静默；DSH_PR_OVERLAP_OK=1→静默；
#       非 git 目录/gh 失败→静默（不阻断）。
# 用法：bash ~/.dsh/bin/gh-pr-overlap-precheck_selftest.sh
set -u
BIN_DIR="${SELFTEST_BIN:-$HOME/.dsh/bin}"
PRECHECK="$BIN_DIR/gh-pr-overlap-precheck.sh"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/pr-precheck.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
FAKE_HOME="$TMP/home"
mkdir -p "$FAKE_HOME" "$TMP/bin"
pass=0
fail=0

REPO="$TMP/repo"
ORIGIN="$TMP/origin.git"
mkdir -p "$REPO"
(
  cd "$REPO" || exit 1
  git init -q -b main
  git config user.email selftest@example.com
  git config user.name selftest
  printf 'base\n' > shared.txt
  printf 'base\n' > only-main.txt
  git add . && git commit -qm base
  git init -q --bare "$ORIGIN"
  git remote add origin "$ORIGIN"
  git push -q origin main
  git checkout -qb feature
  printf 'feature\n' > shared.txt
  printf 'feature\n' > feature-only.txt
  git add . && git commit -qm feature
) || { echo "FAIL 无法准备临时仓库"; exit 1; }

write_fake_gh() { # write_fake_gh <json>
  cat >"$TMP/bin/gh" <<EOF
#!/bin/bash
if [ "\$1" = "pr" ] && [ "\$2" = "list" ]; then
  cat <<'JSON'
$1
JSON
  exit 0
fi
exit 1
EOF
  chmod +x "$TMP/bin/gh"
}

run_precheck() { # run_precheck [env-prefix...]
  ( cd "$REPO" && HOME="$FAKE_HOME" PATH="$TMP/bin:$PATH" "$@" "$PRECHECK" ) >"$TMP/out.txt" 2>"$TMP/err.txt"
  echo $?
}

# 1) 有重叠：警告 #12 + shared.txt，rc=0
write_fake_gh '[{"number":12,"title":"重复机制修复","headRefName":"agent/other","files":[{"path":"shared.txt"},{"path":"only-main.txt"}]}]'
rc="$(run_precheck)"
if [ "$rc" = 0 ] && grep -q '#12' "$TMP/err.txt" && grep -q 'shared.txt' "$TMP/err.txt"; then
  pass=$((pass + 1)); echo "ok   overlap-warns                                rc=$rc"
else
  fail=$((fail + 1)); echo "FAIL overlap-warns expected rc=0 + #12/shared.txt"; sed 's/^/     /' "$TMP/err.txt" | head -5
fi

# 2) 无重叠：静默
write_fake_gh '[{"number":13,"title":"无关 PR","headRefName":"agent/x","files":[{"path":"other.txt"}]}]'
rc="$(run_precheck)"
if [ "$rc" = 0 ] && [ ! -s "$TMP/err.txt" ]; then
  pass=$((pass + 1)); echo "ok   no-overlap-silent                           rc=$rc"
else
  fail=$((fail + 1)); echo "FAIL no-overlap-silent expected rc=0 + empty stderr"; sed 's/^/     /' "$TMP/err.txt" | head -5
fi

# 3) 显式豁免：静默
rc="$(run_precheck env DSH_PR_OVERLAP_OK=1)"
if [ "$rc" = 0 ] && [ ! -s "$TMP/err.txt" ]; then
  pass=$((pass + 1)); echo "ok   explicit-exempt-silent                      rc=$rc"
else
  fail=$((fail + 1)); echo "FAIL explicit-exempt-silent expected rc=0 + empty stderr"
fi

# 4) 非 git 目录：静默
rc="$( cd "$TMP" && HOME="$FAKE_HOME" PATH="$TMP/bin:$PATH" "$PRECHECK" >"$TMP/out.txt" 2>"$TMP/err.txt"; echo $? )"
if [ "$rc" = 0 ] && [ ! -s "$TMP/err.txt" ]; then
  pass=$((pass + 1)); echo "ok   non-git-silent                              rc=$rc"
else
  fail=$((fail + 1)); echo "FAIL non-git-silent expected rc=0 + empty stderr"
fi

# 5) gh pr list 失败：静默（不阻断）
cat >"$TMP/bin/gh" <<'EOF'
#!/bin/bash
echo "HTTP 401: Requires authentication" >&2
exit 1
EOF
chmod +x "$TMP/bin/gh"
rc="$(run_precheck)"
if [ "$rc" = 0 ] && [ ! -s "$TMP/err.txt" ]; then
  pass=$((pass + 1)); echo "ok   gh-failure-silent                           rc=$rc"
else
  fail=$((fail + 1)); echo "FAIL gh-failure-silent expected rc=0 + empty stderr"
fi

# 6) 日志有记录
if [ -f "$FAKE_HOME/.dsh/state/gh-pr-overlap.log" ] && [ -s "$FAKE_HOME/.dsh/state/gh-pr-overlap.log" ]; then
  pass=$((pass + 1)); echo "ok   log-written"
else
  fail=$((fail + 1)); echo "FAIL log-written missing $FAKE_HOME/.dsh/state/gh-pr-overlap.log"
fi

echo "gh-pr-overlap-precheck selftest: pass=$pass fail=$fail"
[ "$fail" = 0 ]
