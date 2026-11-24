# ☠️ POST-RESTART — DSH 0.2.2 upgrade

If you are the worker resumed because the host restarted during the DSH upgrade:

1. Read `~/.dsh/state/upgrade-status.json` and `~/.dsh/state/upgrade-0.2.2.log`.
2. Run `bash work/upgrade/post-restart-check.sh` from this ticket directory.
3. Verify the items in `work/upgrade/UPGRADE-CHECKLIST.md` that need a human/host:
   - Feishu @mention round-trip
   - hooks bridge: run a bash tool call and confirm `/tmp/hook_payload/last.json` updates; try a denied command if safe
   - old session resume + a new session
   - UI pages / plugin pages
4. Report the outcome: `dsh --version`, web/http status, plugin failures, hooks result, and whether the switch rolled back.

Do **not** repeat the upgrade. If the status is `rolled_back` or `failed`, report that and include the log tail.
