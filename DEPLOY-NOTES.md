# Deploy notes — ticket 226d5178fb80 (kanban-empty-board)

Date: 2026-11-07. Operator report (Feishu om_x100b61c51810c4a0ce1d4205794303e,
"看板功能 是不是 不可用？ 为什么没有任务内容"): the Board panel shows no task
content in any workspace. Follow-up to ticket 937d8cafda22, whose post-restart
re-verification (branch `agent/enable-kanban-937d8cafda22`, ~20:50 the same
day) had already identified the empty boards as expected plugin behavior and
left the gap open. This ticket diagnoses it against the live service and
closes the gap with data, not a restart.

## Diagnosis (verified against the running service, 2026-11-07 ~21:00)

1. **The plugin is fine.** `@alpacachen/dsh-kanban` 1.11.0 serves boards
   normally: startup check found 7 board files (1 valid v6, 6 old v4 that
   migrate automatically with backups on first access), and the API answers
   every workspace read.
2. **Data source is per-workspace.** Boards are keyed by workspace and
   persisted as `<workspace>/.dsh-kanban.json` (hardcoded in the plugin; no
   shared/global board option). A workspace without that file renders the
   default board: 4 columns, 0 cards.
3. **Ticket worktrees are born without one.** Every superagent ticket gets a
   fresh worktree; 21 of 22 ticket worktrees had no board file, so the
   operator saw "No cards" everywhere they clicked (service log shows the
   board reads for `research-anything-tools`, `reproduce-knowledge-graph`,
   `research-workbuddy`, `polish-ppt-pages`, `kanban-empty-board`).
4. **No ticket integration exists.** The plugin does not import
   dsh-superagent tickets (orchestrator store is a separate sqlite; nothing
   writes tickets into any board). Cards only appear via the UI or the
   plugin's `kanban_*` agent tools. The only real card was inside the
   enable-kanban ticket's own worktree; the six `~/project/*` boards hold
   test cards from that ticket's e2e.

So: **看板功能可用；"没有任务内容"是因为看板按工作区隔离、工单不自动进看板。**

## Fix — sync tickets into the boards through the plugin's own API

`work/kanban-ticket-sync.mjs` (Node ≥22, no extra deps):

- reads tickets from a throwaway sqlite snapshot of
  `~/.dsh/state/superagent/orchestrator.sqlite` (`.backup`, read-only,
  includes WAL — the live store is never touched);
- maps each ticket to its worktree (`~/src/<name>-<id[:12]>`) and to the GUI
  workspace id via `~/.dsh/storages/workspace.json`;
- drives the plugin's authenticated HTTP API (`POST /api/kanban`, browser
  cookie minted from the service token printed on its tmux pane), so every
  write goes through the plugin dispatcher: schema v6, id sequence, activity
  log, `completedAt` and column semantics are exactly what the plugin itself
  would write — **no hand-crafted board JSON, no service restart**;
- one card per ticket, marker `工单 <id[:8]>` in the note: missing →
  `addCard` in `In Progress` (open) or `Done` (ended); marker card in the
  wrong column → `moveCard`; otherwise untouched. Idempotent by marker, so
  re-runs are no-ops and boards a human curates are never clobbered.

Ran once (2026-11-07T13:12Z): created 21 cards, 1 already correct
(enable-kanban's hand-made card matches the marker), 0 failures, 0 skipped.
Second run: `{"created":0,"moved":0,"unchanged":22,"skipped":0,"failures":0}`.

## Verification

- Dry-run first: planned exactly 21 creates, 1 unchanged, 0 failures.
- Live run then idempotency re-run (see above).
- **All 22 boards verified through the live API** (`work/verify-summary.txt`):
  exactly one marker card per board, in the expected column — 22 OK, 0 FAIL.
- GUI screenshots, same viewport and locale as the before captures
  (`work/shot-board.mjs`; baseline = worktree at init commit `f9afcb3` with
  plugin 1.11.0 installed and no board files; changed state = this branch
  after the sync run):
  - `before-board-kanban-empty-board.png` / `-2.png` — Before: this ticket's
    workspace and `research-anything-tools`: all columns "No cards".
  - `after-board-kanban-empty-board.png` — After: this ticket's card
    ("排查看板没有任务内容的原因并修正") in In Progress.
  - `after-board-kanban-empty-board-2.png` — After: `research-anything-tools`
    card in Done (its ticket completed earlier today).
- Service log after the run: no new errors; the `Failed to read board … not
  found` lines during the run are the first read of each fileless workspace
  (benign, same as the operator's own browsing).

## Keeping boards fresh (known limitation, deliberate scope)

Nothing auto-creates future tickets' cards — the plugin has no ticket
integration, and adding one belongs to the plugins (upstream
`deepseek-ai/dsh-superagent-prototype` worktree creation or
`alpacachen/dsh-kanban`), not to a local restart. Until such an integration
exists, re-run the script when new tickets should appear:

```sh
node work/kanban-ticket-sync.mjs          # safe to re-run any time
```

Suitable as a cron entry (e.g. hourly); it is read-only on the orchestrator
DB and a no-op when nothing changed. Run log: last-run summary at
`~/.dsh/state/kanban-ticket-sync/state.json`.

Card semantics worth knowing: `completedAt` is stamped by the plugin when the
card enters the Done column (sync time, not the ticket's historical end
date — the real date is in the card note, matching the plugin's "don't
infer completion times" rule); cards land as `createdBy: "human"` because
they arrive via the HTTP path — the note text states they are auto-synced.

## Rollback

Delete the synced cards (search boards for `工单 ` notes) or simply remove
the generated `.dsh-kanban.json` files from the affected worktrees — the
boards return to their previous (empty) state. Nothing else was touched: no
plugin/profile/service change, no restart, orchestrator store read-only.
