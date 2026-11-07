# Deploy notes — ticket 937d8cafda22 (enable-kanban)

Date: 2026-11-07. Operator request (Feishu om_x100b61e2f7e654a8c4b292fd12b6b36,
"@openclaw助手 用看板插件吧"): enable a kanban plugin on the local DSH
deployment so ticket progress is visible. Routing-note constraints honored:
target is the local machine deployment; plugin source and configuration
confirmed before changing anything; backups taken and a rollback path kept.

## Source selection (GitHub survey, 2026-11-07)

Candidates checked via `gh search repos "dsh kanban"` / `"dsh board"`:

| repo | stars | last push | license | verdict |
| --- | --- | --- | --- | --- |
| alpacachen/dsh-kanban | 22 | 2026-11-06 | MIT | **selected** |
| isolat-3k/dsh-kanban | 9 | 2026-08-16 | MIT | stale for ~3 months |
| hfanshu/dsh-kanban, dcchanInSz/dsh-kanban, roxorlt/dsh-kanban, lihuu/dsh-board, workain/dsh-board | 0 | various | MIT/none | no adoption signal |

Selected: `@alpacachen/dsh-kanban` — highest stars, npm-published, actively
maintained (release v1.11.1 the day before), declares per-version DSH
compatibility in its README.

**Version choice:** npm resolved **1.11.0** (not 1.11.1). This is the better
match for this deployment anyway: DSH here is **0.2.1-rc.5**, and v1.11.1's
only functional change ("适配 DSH 0.2.2-rc.1", PR #68) adapts to a
`createDrafts` behavior introduced in 0.2.2-rc.1; its third argument is simply
ignored by older hosts. v1.11.0 declares compatibility with DSH
0.2.0-rc.2 / 0.2.1-rc.3 — rc.5 is a later rc of the same 0.2.1 line.

## Configuration method (official docs first)

Per `docs/user/guide/plugin-market.zh.md` (and the plugin README's Web
install), the supported path on a profile deployment is
`dsh plugin --profile <name> add <pkg>` followed by a service restart. The
`dsh plugin` CLI forwards to pnpm in the profile directory **and** registers
the bundle: after the command, `~/.dsh/profiles/superagent/package.json`
contains both the dependency `"@alpacachen/dsh-kanban": "^1.11.0"` and the
`dsh.profile.bundles` entry `"@alpacachen/dsh-kanban"`. No manual
cordis.patch.yml edit was needed (the plugin ships its own patch layer that
inserts the `dsh-kanban` bundle).

## What changed

- `~/.dsh/profiles/superagent/package.json`: dependency + bundle entry added
  (by `dsh plugin --profile superagent add @alpacachen/dsh-kanban`).
  Backup: `package.json.bak-kanban-20261107`.
- `~/.dsh/profiles/superagent/pnpm-lock.yaml`: +51 packages installed.
  Backup: `pnpm-lock.yaml.bak-kanban-20261107`.
- `~/.dsh/profiles/superagent/node_modules/`: `@alpacachen/dsh-kanban@1.11.0`
  installed. Nothing else in the bundle list changed.
- No existing data touched: the board store is per-workspace plugin data, and
  this is a first install (no prior board data to migrate).

## Verification before activation

- `dsh --profile superagent --dump-config`: exit 0, `dsh-kanban` layer present.
- Baseline health recorded before the change: all components ready except
  `github: error` (pre-existing, unrelated). `status` exit code baseline: 2.

## Activation

`activation.sh` (committed here) was run in a detached tmux session
(`kanban-activate`), per the install-memory-routing deploy notes: a restart
driven from a host-attached process group died with it once (~11 min outage).
The script calls `scripts/dsh-superagent restart --profile superagent`,
logs `restart_exit=0` at 2026-11-07T05:08:24Z, and would run `rollback.sh`
automatically on exit 1 (restartable failure). Exit 2/3 (component error /
setup wait) intentionally does not roll back.

## Post-activation verification (e2e on the real target)

- Health after restart: all components ready except `github: error`
  (unchanged from baseline). `status` exit code: 0.
- Screenshots in `work/` (token-free; viewport captures):
  - `before-sidebar.png` — **Before**: sidebar has no Board entry. Captured
    from a throwaway boot of the exact pre-change composition (the two
    `.bak-kanban-20261107` files, same dsh 0.2.1-rc.5) on port 3083 with an
    isolated stateDir and the Feishu Source disabled; the throwaway profile
    and its temp state were removed afterwards.
  - `after-sidebar.png` — **After**: sidebar gains the **Board** entry
    (live service, port 3082).
  - `after-board.png` — Board view: workspace selector defaulted to
    `enable-kanban-937d8cafda22`, four columns (Todo / In Progress / Review /
    Done), search and priority/label/due-date filters.
  - `after-card-dialog.png` / `after-card-created.png` /
    `after-card-persisted.png` — a real card for this ticket was created in
    In Progress ("启用看板插件，让工单进度可见") and **verified to persist
    across a full page reload** (programmatic checks:
    cardVisibleAfterSave / cardVisibleAfterReload / notePreviewAfterReload
    all true).
- The throwaway baseline boot also re-validated that the rest of the
  composition still resolves without the plugin.

## Rollback

Run `rollback.sh` in this directory: it restores both `.bak-kanban-20261107`
files, runs `pnpm install` to prune the plugin from node_modules, and
restarts the service in a detached tmux session. The plugin's board data
(written after install) is not removed by the rollback; delete the plugin's
per-workspace board store first if a pristine state is wanted.

## Known limitations

- The plugin's 19 `kanban_*` agent tools were not exercised separately in an
  agent session; the e2e covers the user-visible board (render, create,
  persist). The bundle load is the same path that registers the tools.
- Screenshots show the GUI in English locale; a zh locale is available in the
  plugin.
- Plugin is community software (MIT); board data lives in a plugin-managed
  JSON file at each workspace root (observed: `.dsh-kanban.json` in this
  ticket directory, holding the card created during e2e), so include those
  files in any future backup rotation if boards become load-bearing.
