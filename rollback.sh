#!/usr/bin/env bash
# Rollback for ticket 937d8cafda22 (enable-kanban): restore the superagent
# profile composition from the pre-kanban backups and restart the service.
# Backups made before the change: *.bak-kanban-20261107
set -u
PROFILE_DIR="$HOME/.dsh/profiles/superagent"
SCRIPT="$HOME/dsh-superagent-prototype/scripts/dsh-superagent"
LOG_DIR="$(cd "$(dirname "$0")" && pwd)/work"

for f in package.json pnpm-lock.yaml; do
  if [ -f "$PROFILE_DIR/$f.bak-kanban-20261107" ]; then
    cp -p "$PROFILE_DIR/$f.bak-kanban-20261107" "$PROFILE_DIR/$f"
    echo "restored $f from backup"
  else
    echo "MISSING backup for $f; aborting" >&2
    exit 9
  fi
done

# Reconcile node_modules with the restored files (prunes @alpacachen/dsh-kanban).
(cd "$PROFILE_DIR" && pnpm install --frozen-lockfile=false) >> "$LOG_DIR/rollback.log" 2>&1 \
  || { echo "pnpm install failed; see work/rollback.log" >&2; exit 8; }

# Restart inside tmux so the service escapes the caller's process group.
tmux kill-session -t kanban-rollback 2>/dev/null
tmux new-session -d -s kanban-rollback \
  "python3 '$SCRIPT' restart --profile superagent >> '$LOG_DIR/rollback-restart.log' 2>&1; \
   echo \"restart_exit=\$?\" >> '$LOG_DIR/rollback-restart.log'"
echo "rollback applied; restart running in tmux session kanban-rollback (see work/rollback-restart.log)"
