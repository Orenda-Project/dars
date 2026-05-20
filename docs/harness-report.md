---
type: reference
last_verified: 2026-05-20
owner: hataf
---

# Dars Harness Report

A single-page tour of the harness that ships inside `dars/`: what files it consists of, how those files actually talk to each other through Claude's tool calls, and how the design has evolved since it was first introduced.

This report is sourced entirely from inside `dars/` — no cross-project files.

---

## 1. What the harness is

The harness is the Claude Code configuration that shapes how the agent behaves inside this repo: lifecycle hooks, slash-command skills, subagent definitions, MCP servers, and per-session telemetry. **None of it is Dars application code** — it's the operating manual the agent loads on every session.

It splits into two halves:

- **Guides (feedforward)** — `CLAUDE.md`, agents, skills. They steer Claude *before* it acts.
- **Sensors (feedback)** — hooks, beads, the tool-use log, `/retrospect`. They observe *after* Claude acts and feed corrections back into the guides.

Without sensors, you have a style guide nobody enforces. The system works because violations are caught mechanically.

---

## 2. Contents — file inventory

```
dars/
├── CLAUDE.md                              L1 router (107/150 lines)
├── docs/
│   ├── README.md                          L2 router for docs/
│   ├── harness-setup.md                   the canonical "how the .claude/ tree works" doc
│   ├── ROADMAP.md                         /build picks items from this
│   ├── conventions.md                     /build reads before any change
│   ├── WRITING_DOCS.md                    doc-type rules + frontmatter contract
│   └── adr/  features/  plans/  specs/    L3 reference subtrees
├── .claude/
│   ├── settings.json                      hooks + MCP servers (checked in)
│   ├── settings.local.json                personal overrides (not checked in)
│   ├── hooks/
│   │   ├── session-start.sh               SessionStart        (35 lines)
│   │   ├── session-end.sh                 Stop                (38 lines)
│   │   ├── block-bad-commands.sh          PreToolUse[Bash]    (25 lines)
│   │   ├── guard-file-writes.sh           PreToolUse[Write|Edit] (20 lines)
│   │   ├── validate-after-write.sh        PostToolUse[Write|Edit] (13 lines)
│   │   └── log-tool-use.sh                PostToolUse[*]      (68 lines)
│   ├── skills/
│   │   ├── feature/SKILL.md               /feature — plan-first phased workflow
│   │   ├── retrospect/SKILL.md            /retrospect — consumes sessions/*.jsonl
│   │   └── supabase-postgres-best-practices/  vendored guidance
│   ├── agents/build.md                    /build subagent definition
│   ├── commands/build.md                  /build slash-command wrapper
│   ├── sessions/<session_id>.jsonl        per-session tool-use log (gitignored)
│   ├── worktrees/                         isolated git worktrees for parallel Agent runs
│   ├── improvements.md                    rolling /retrospect output (8 dated retros so far)
│   └── patterns.md                        observed patterns + counts (3+ → harness change)
└── .beads/
    ├── status.jsonl                       work tracker (open/in_progress/closed/blocked)
    ├── decisions.jsonl                    architectural decisions + rationale
    ├── failures.jsonl                     incidents + lessons
    ├── archive/                           closed beads, by date
    └── README.md
```

### The four conceptual systems

| System | Purpose | Where it lives |
|---|---|---|
| Document hierarchy | Load minimum high-signal context per task | `CLAUDE.md` (L1) → `docs/README.md` (L2) → `docs/*.md` (L3) |
| Beads | Survive context resets — append-only work memory | `.beads/*.jsonl` |
| Telemetry + retrospect loop | Tool calls logged, analysed, surfaced as improvements | `sessions/*.jsonl` → `/retrospect` → `improvements.md` → `patterns.md` |
| Skill + agent layer | Repeatable workflows and isolated worker definitions | `.claude/skills/`, `.claude/agents/`, `.claude/commands/` |

---

## 3. Flow diagram — how the harness uses Claude's tools

Each arrow is a real tool invocation or hook event. Hooks are configured in `settings.json` and live under `.claude/hooks/`. `exit 0` allows; `exit 2` blocks and surfaces stderr back to the agent.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              SESSION LIFECYCLE                               │
└──────────────────────────────────────────────────────────────────────────────┘

  ┌───────────────┐                              ┌─────────────────────────┐
  │  SESSION      │  ─── SessionStart hook ───►  │  session-start.sh        │
  │  STARTS       │                              │   • prints open beads    │
  │               │  ◄── injected as stdout ───  │   • graphify graph hint  │
  └──────┬────────┘                              └─────────────────────────┘
         │
         │  Claude auto-loads CLAUDE.md (L1).
         │  docs/README.md (L2) only when domain matches.
         │  docs/*.md (L3) only when blocked without it.
         │
         ▼
  ┌──────────────────────────────────────── TOOL USE LOOP ─────────────────────┐
  │                                                                            │
  │  ┌──────────────┐                                                          │
  │  │  Bash        │ ──pre──► block-bad-commands.sh                           │
  │  │              │            • blocks `git add/commit .env`     ─exit 2──► BLOCK
  │  │              │            • blocks `git push -f main`        ─exit 2──► BLOCK
  │  │              │            • runs `make test` before push     ─exit 2──► BLOCK
  │  │              │ ◄─exit 0──                                               │
  │  ├──────────────┤                                                          │
  │  │  Write/Edit  │ ──pre──► guard-file-writes.sh                            │
  │  │              │            • warn on .env writes                         │
  │  │              │            • CLAUDE.md > 150 lines             ─exit 2──► BLOCK
  │  │              │ ◄─exit 0──                                               │
  │  │              │                                                          │
  │  │              │ ──post─► validate-after-write.sh                         │
  │  │              │            • `python3 -m py_compile` on .py   ─exit 2──► BLOCK
  │  │              │ ◄─exit 0──                                               │
  │  ├──────────────┤                                                          │
  │  │  Glob / Grep │ ──pre──► inline hook in settings.json                    │
  │  │              │            • if graphify-out/graph.json exists,          │
  │  │              │              inject "read GRAPH_REPORT.md first" note   │
  │  │              │ ◄────────                                                │
  │  ├──────────────┤                                                          │
  │  │  any tool *  │ ──post─► log-tool-use.sh                                 │
  │  │              │            • appends 1 line of JSON to                   │
  │  │              │              .claude/sessions/<session_id>.jsonl         │
  │  │              │            • per-tool compact summary,                   │
  │  │              │              never logs file contents                    │
  │  │              │ ◄────────                                                │
  │  └──────────────┘                                                          │
  │                                                                            │
  │  Claude appends to .beads/status.jsonl as it opens / closes beads          │
  │  (status.jsonl is append-only — closes are new lines, not edits).          │
  └────────────────────────────────────────────────────────────────────────────┘
         │
         │  /feature, /retrospect, /build are user-triggered skills/agents.
         │  /build (subagent) spawns via the Agent tool with its own context;
         │  the parent session sees only the agent's summary.
         │
         ▼
  ┌───────────────┐                              ┌──────────────────────────┐
  │  SESSION      │ ──── Stop hook ───────────►  │ session-end.sh           │
  │  ENDS         │                              │  • count open beads       │
  │               │                              │  • check unstaged changes │
  │               │                              │  • prompt: run /retrospect│
  │               │                              └──────────┬───────────────┘
  └───────────────┘                                         │
                                                            ▼
                  ┌──────────────────────────────────────────────────────────┐
                  │  RETROSPECT LOOP (user-triggered, not automatic)         │
                  │                                                          │
                  │   /retrospect reads latest sessions/*.jsonl and computes │
                  │     • total calls + top-5 tools                          │
                  │     • re-reads of same file with no Edit between         │
                  │     • parallelism gaps (≥3 same-tool serial calls)       │
                  │     • Bash error spikes                                  │
                  │     • named anti-patterns (raw cat/sed/awk,              │
                  │       grep/find when graphify exists, etc.)              │
                  │                                                          │
                  │   Emits ISSUE / ROOT CAUSE / EVIDENCE / FIX / PRIORITY   │
                  │   blocks → appends to .claude/improvements.md            │
                  │                                                          │
                  │   Recurring entries get counted in .claude/patterns.md;  │
                  │   anything hitting count ≥ 3 is the trigger to change    │
                  │   the harness itself (new hook, new rule in CLAUDE.md).  │
                  └──────────────────────────────────────────────────────────┘
```

### How Claude's tools map to harness components

| Claude tool | Pre-hook (gate) | Post-hook (validate / log) | Files touched |
|---|---|---|---|
| `Bash` | `block-bad-commands.sh` | `log-tool-use.sh` | shell, git, `make test` |
| `Write` / `Edit` | `guard-file-writes.sh` | `validate-after-write.sh`, `log-tool-use.sh` | any source/doc file |
| `Read` | — | `log-tool-use.sh` | any file |
| `Glob` / `Grep` | inline graphify hint | `log-tool-use.sh` | filesystem search |
| `Agent` (subagent) | — | `log-tool-use.sh` | sub-project source via the agent's own session |
| `SessionStart` event | — | `session-start.sh` injects beads + graph hint | `.beads/status.jsonl`, `graphify-out/` |
| `Stop` event | — | `session-end.sh` flags open beads + unstaged work | `.beads/status.jsonl`, working tree |

The hooks communicate with Claude via stdin (the tool input/output as JSON) and exit codes. They are short bash scripts — combined source is under 200 lines.

---

## 4. Evolution — every harness commit in `dars`

Chronological, sourced from `git log` against `.claude/`, `CLAUDE.md`, and `docs/harness-setup.md`. Oldest first. Commit SHA links to the GitHub commit; PR column links to the merge PR. Repo: [Orenda-Project/dars](https://github.com/Orenda-Project/dars), default review branch is `staging`.

The March–April commits all landed as **direct pushes to `main`** — the feature-branch + staging-PR convention only kicks in from `b5ecc39` (2026-05-13, PR #15) onward. The rule that *codifies* "PRs target staging" (`00a7ea6`, PR #18) shipped the same day, a few hours after the first PR-routed harness change.

| Date | SHA | PR | What changed |
|---|---|---|---|
| 2026-03-26 | [`f442d2f`](https://github.com/Orenda-Project/dars/commit/f442d2f) | direct push to main | Repo initialised with project scaffolding (first `CLAUDE.md`). |
| 2026-03-26 | [`0c780f3`](https://github.com/Orenda-Project/dars/commit/0c780f3) | direct push to main | `CLAUDE.md` filled out with gotchas + current build status — pre-harness, content-heavy. |
| 2026-03-27 | [`03f14c8`](https://github.com/Orenda-Project/dars/commit/03f14c8) | direct push to main | Roadmap + context docs added; `CLAUDE.md` re-pointed to them. |
| **2026-04-08** | [**`ab25bf0`**](https://github.com/Orenda-Project/dars/commit/ab25bf0) | direct push to main | **Initial harness build.** L1/L3 docs split, `.beads/` with all three JSONL files, all 5 base hooks in `.claude/hooks/`, `.claude/settings.json` wiring `SessionStart` / `PreToolUse` / `PostToolUse` / `Stop`. `CLAUDE.md` trimmed to a router. |
| 2026-04-08 | [`5f747f8`](https://github.com/Orenda-Project/dars/commit/5f747f8) | direct push to main | **Hook bug fix.** `session-start.sh` and `session-end.sh` were treating beads as last-write-wins; switched to *last-status-wins* so an appended `closed` line correctly hides the original `open` line in append-only JSONL. |
| 2026-04-08 | [`38fcf32`](https://github.com/Orenda-Project/dars/commit/38fcf32) | direct push to main | First `/build` skill — "pick from roadmap, implement, ship." |
| 2026-04-08 | [`5b10210`](https://github.com/Orenda-Project/dars/commit/5b10210) | direct push to main | **Skill → Agent migration.** `/build` was reshaped as a subagent (richer tool access, isolation, own context) rather than a skill. Plugin-format skill folder removed. |
| 2026-04-08 | [`832418c`](https://github.com/Orenda-Project/dars/commit/832418c) | direct push to main | Branch-per-feature enforced inside the `/build` agent; added `.claude/commands/build.md` wrapper. Committed an early 2,219-line `harness.md` reference (later superseded by `docs/harness-setup.md`). |
| 2026-04-13 | [`f9ab36d`](https://github.com/Orenda-Project/dars/commit/f9ab36d) | direct push to main | "Always work on a feature branch" promoted from agent-internal to a Critical Rule in `CLAUDE.md` — first time a rule moved up the L1 ladder after a real violation. *(Ironically, this rule was itself committed directly to main — the rule kicks in for everything that came after.)* |
| 2026-05-13 | [`b5ecc39`](https://github.com/Orenda-Project/dars/commit/b5ecc39) | [#15](https://github.com/Orenda-Project/dars/pull/15) | Settings + graphify graph refreshed; added the inline `PreToolUse[Glob|Grep]` graphify hint that injects a "read GRAPH_REPORT.md first" note when the graph exists. |
| 2026-05-13 | [`00a7ea6`](https://github.com/Orenda-Project/dars/commit/00a7ea6) | [#18](https://github.com/Orenda-Project/dars/pull/18) | `CLAUDE.md` updated to note `staging` as PR base branch (rule 2 in current Critical Rules). |
| 2026-05-15 | [`eda0e12`](https://github.com/Orenda-Project/dars/commit/eda0e12) | [#36](https://github.com/Orenda-Project/dars/pull/36) | `REBUILD.md` onramp added; `CLAUDE.md` got the pinned "🔥 ACTIVE: v2 rebuild" pointer at the top of Quick Navigation. |
| **2026-05-20** | [**`a853682`**](https://github.com/Orenda-Project/dars/commit/a853682) | [#80](https://github.com/Orenda-Project/dars/pull/80) | **Telemetry + workflow overhaul.** Added `log-tool-use.sh` `PostToolUse[*]` hook → per-session JSONL log. Rewrote `/retrospect` to read that log (real EVIDENCE — re-reads, parallelism gaps, 6 named anti-patterns) instead of recalling from conversation. Rewrote `/feature` as a plan-first, phase-based workflow (S/M/L feature folders, glossary, decision log, per-phase docs, onramp). `sessions/` gitignored. |

### Themes across the commits

1. **From feedforward to feedback.** April was about *guides* (docs, agents, commands). May added *sensors* — the tool-use log and the retrospect skill that grades the session on evidence, not vibes.
2. **Skills became Agents where isolation mattered.** `/build` moved from a skill to a subagent (`5b10210`) because isolated tool access + its own context produced cleaner results on long jobs.
3. **Rules harden after they break.** Both the feature-branch rule (`f9ab36d`) and the last-status-wins beads parsing fix (`5f747f8`) came after real failures, not in the initial design — exactly the loop the harness is meant to enable.
4. **`improvements.md` is now a long doc.** Eight dated retrospect entries since 2026-05-07, with `patterns.md` tracking which ones have crossed the count-≥3 threshold that justifies a harness change.

---

## 5. Day-to-day effect

What the harness gives you, in practice:

- **Session start:** open beads injected automatically. You pick up where you left off.
- **Write Python:** `py_compile` runs before the response continues — syntax errors caught in the same turn.
- **Write `CLAUDE.md`:** hard-blocked if the change pushes it past 150 lines. Stays a router.
- **`git add .env`:** blocked.
- **`git push -f main`:** blocked. Plain `git push` runs `make test` first and blocks on red.
- **`grep` when graphify exists:** you get a hint to read `GRAPH_REPORT.md` first.
- **Every tool call:** one JSON line in `sessions/<session_id>.jsonl`. No file contents — just paths, commands (first 200 chars), patterns, and error flag.
- **End of session:** open beads counted, unstaged changes flagged, `/retrospect` prompted.
- **`/retrospect`:** real numbers, real evidence, dated entry appended to `improvements.md`.
- **Pattern hits 3:** `patterns.md` flags it as a candidate for a new hook or a new rule in `CLAUDE.md`.

The harness is only as good as the failure log and retrospect cadence that feed it. Both are inside this repo.

---

## Related docs

- [.claude/](.claude/) — the harness itself
- [docs/harness-setup.md](harness-setup.md) — operating reference for adding hooks/skills/agents
- [CLAUDE.md](../CLAUDE.md) — the L1 router
- [.beads/README.md](../.beads/README.md) — work-tracking schemas
