#!/usr/bin/env bash
# Activation for ticket 937d8cafda22 (enable-kanban): restart the superagent
# profile so the freshly installed @alpacachen/dsh-kanban bundle loads.
# Run this from a detached tmux session (own process group) per the
# install-memory-routing deploy notes: a restart driven from a host-attached
# process group died with it once (~11 min outage).
# Exit codes of scripts/dsh-superagent restart:
#   0 service healthy; 1 stopped/broken (restartable failure) -> rollback;
#   2 running with a component error (baseline has one: github: error);
#   3 running, waiting for setup -> attention, no rollback.
set -u
SCRIPT="$HOME/dsh-superagent-prototype/scripts/dsh-superagent"
LOG_DIR="$(cd "$(dirname "$0")" && pwd)/work"
mkdir -p "$LOG_DIR"

python3 "$SCRIPT" restart --profile superagent >> "$LOG_DIR/activation.log" 2>&1
code=$?
echo "$(date -u +%FT%TZ) restart_exit=$code" >> "$LOG_DIR/activation.log"
if [ "$code" -eq 1 ]; then
  echo "restart reported a restartable failure; running rollback.sh" >> "$LOG_DIR/activation.log"
  bash "$(dirname "$0")/rollback.sh" >> "$LOG_DIR/activation.log" 2>&1
fi
# codes 0/2/3 keep the new composition (2 matches the pre-change baseline).
