#!/usr/bin/env bash
# 共享盘就绪后，在 Mac（或任意 POSIX 机器）上跑一次：校验挂载 → 建目录骨架 → 放看板 → 自检。
#
# 用法：
#   bash oral-share-setup.sh                 # 默认 /Volumes/oral
#   bash oral-share-setup.sh /Volumes/oral   # 指定挂载点
#
# 退出码：0 就绪；2 挂载点不存在（先去 Finder 连接 smb://<PC>/oral）；3 不可写；4 自检失败。
set -uo pipefail

MNT="${1:-/Volumes/oral}"
HERE="$(cd "$(dirname "$0")" && pwd)"
BOARD="$HERE/job-status.py"

if [[ ! -d "$MNT" ]]; then
  echo "✗ 找不到挂载点：$MNT"
  echo "  先在 Mac：Finder → 前往 → 连接服务器 → smb://<PC名或IP>/oral（密码在 Finder 里输入）"
  echo "  或命令行：open 'smb://<PC名或IP>/oral'"
  exit 2
fi

probe="$MNT/.oral-write-test.$$"
if ! ( : > "$probe" ) 2>/dev/null; then
  echo "✗ 挂载点不可写：$MNT（检查共享权限/账号）"
  exit 3
fi
rm -f "$probe"

mkdir -p "$MNT/jobs" "$MNT/queue" "$MNT/archive" "$MNT/bin"
[[ -f "$BOARD" ]] || { echo "✗ 找不到 $BOARD（本脚本要与 job-status.py 放在同一目录）"; exit 4; }
cp -f "$BOARD" "$MNT/bin/job-status.py"
chmod +x "$MNT/bin/job-status.py" 2>/dev/null || true

if ! python3 "$MNT/bin/job-status.py" --root "$MNT/jobs" >/tmp/oral-board-selftest.txt 2>&1; then
  echo "✗ 看板自检失败，输出如下："
  cat /tmp/oral-board-selftest.txt
  exit 4
fi

echo "✓ 共享盘就绪：$MNT"
echo "  结构：jobs/ queue/ archive/ bin/（已建）"
echo "  看板：" python3 "$MNT/bin/job-status.py" --watch 15
echo "  下一步：按文档第 5.5 节在各阶段脚本里写 status.json，任务就会出现在看板上。"
