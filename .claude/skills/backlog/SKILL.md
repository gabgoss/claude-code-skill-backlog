---
name: backlog
description: Parse backlog index, select items, route to fix/plan based on scope, update status. Use when selecting backlog items for triage and routing to the appropriate fix or planning workflow.
argument-hint: "[item-id]"
user-invocable: true
allowed-tools: Read, Edit, Write, Glob, Grep, Bash(python *), Bash(git *), Task
---

# Backlog Skill

Parse the project backlog index, let the user select items, assess scope, route each item to the right action (direct fix, task list, or session planning), and update status.

**Configuration:** All paths and scoring weights are defined in [config.yaml](config.yaml). Edit that file to match your project.

---

## Phase 1: FETCH

**Score and parse the backlog index:**
```bash
python .claude/skills/backlog/scripts/score_backlog.py
python .claude/skills/backlog/scripts/parse_backlog.py
```

- `score_backlog.py` computes priority scores (8 configurable factors) and writes the Score column to the index
  - Items that block other open items get a blocker bonus per blocked item (force multiplier)
- `parse_backlog.py` reads the backlog index (path from config.yaml)
- Outputs a formatted table of **selectable** items (excludes COMPLETE, CLOSED, and items blocked by open dependencies)
- Blocked items appear in a separate summary below the main table
- Prints JSON temp file path on the last line: `JSON: /tmp/backlog-XXXXX/items.json`
- If no open items: print "No open backlog items." and **STOP**

**With filters:**
```bash
python .claude/skills/backlog/scripts/parse_backlog.py --priority High
python .claude/skills/backlog/scripts/parse_backlog.py --abbrev APP
python .claude/skills/backlog/scripts/parse_backlog.py --status IN_PROGRESS
```

Display the table to the user.

---

## Phase 2: SELECT

**If `$ARGUMENTS` was provided** (an item ID):
- Use that item ID directly — skip the selection prompt
- Read the JSON temp file to get the full item data

**If no arguments:**
- Present the table from Phase 1 (only selectable items — blocked items are excluded)
- Use `AskUserQuestion` to ask: "Which items would you like to triage?"
  - Provide the first 4 item IDs as options (highest priority from selectable items)
  - User can select one or more, or type a custom ID
  - Do NOT offer blocked items — they cannot be worked until their blockers are resolved

**For each selected item**, update status to IN_PROGRESS:
```bash
python .claude/skills/backlog/scripts/update_backlog.py --id "{item_id}" --status IN_PROGRESS
```

---

## Phase 3: RESOLVE

**For each selected item:**

1. Get the item's file paths from the JSON data (the `files` array)
2. Read each backlog item file (files have YAML frontmatter with `created`, `blocks`, and `status` fields)
3. **Staleness check:** If the item has measurable acceptance criteria (counts, percentages, coverage targets), run the relevant verification command *before* routing. If criteria are already met or nearly met, present a "Close as COMPLETE" option instead of routing through a fix workflow.

4. Assess the item's scope:

| Signal | Check | Indicates |
|--------|-------|-----------|
| "Bug" in feature name | Index Feature column | Direct fix |
| File < 50 lines + specific fix | Content analysis | Direct fix |
| 3-5 discrete steps | Count numbered items | Task list |
| "multi-sprint" / "architecture" / "migration" | Keywords | Session planning |
| 6+ sub-items or headings | File structure | Session planning |
| Multiple reference files (01, 02, 03...) | Files column | Session planning |

5. Present the scope assessment to the user:

   ```
   ─────────────────────────────────────────────
   ITEM: {ID} — {Feature}
   Priority: {Priority} | Abbrev: {Abbrev}
   ─────────────────────────────────────────────

   ## What This Is About

   {2-4 sentence plain-language summary of what the backlog item describes}

   ## Files Touched

   - `{path/to/file1.ext}` — {brief role}
   - `{path/to/file2.ext}` — {brief role}

   ## Tasks at a Glance

   1. {First discrete task or step}
   2. {Second discrete task or step}
   3. ...

   ## Scope Assessment

   Route: {DIRECT_FIX | TASK_LIST | SESSION_PLANNING}
   Reason: {why this route was chosen}
   ─────────────────────────────────────────────
   ```

---

## Phase 4: ACT

**Use `AskUserQuestion` to confirm the routing:**
- Option 1: Recommended route (from Phase 3 assessment)
- Option 2: Alternative route
- Option 3: Skip this item

### Route A: Direct Fix

For bugs and targeted fixes with clear scope:

1. Read the [triage prompt template](templates/triage-prompt.md)
2. Fill in all placeholders with item details and file content
3. Launch a fix subagent:
   ```
   Task(general-purpose, prompt=<assembled triage prompt>)
   ```
4. Wait for the agent to complete
5. Proceed to Phase 5

### Route B: Task List

For medium-scope items with 3-5 discrete steps:

1. Analyze the backlog item file to extract discrete steps
2. Create tasks using `TaskCreate` for each step
3. Work through each task sequentially
4. After all tasks complete, proceed to Phase 5

### Route C: Session Planning

For large-scope or architectural items:

1. Summarize the item context
2. Tell the user: "This item needs a full plan. Create a session plan with the backlog item context when ready."
3. Proceed to Phase 6 (status -> PLANNING)

---

## Phase 5: VERIFY

**After Route A (Direct Fix):**
1. Show the diff:
   ```bash
   git diff --stat
   ```
   ```bash
   git diff
   ```
2. Use `AskUserQuestion`:
   - **Approve** — Accept changes, mark COMPLETE
   - **Revert** — Discard changes, mark NOT_STARTED
   - **Skip** — Keep changes, don't update status

3. If Revert:
   ```bash
   git checkout -- {list of modified files}
   ```

**After Route B (Task List):**
1. Verify all tasks are marked completed
2. Show summary of changes made
3. Use `AskUserQuestion`: Approve (COMPLETE) or Revert (NOT_STARTED)

**After Route C (Session Planning):**
- No verification needed — plan creation is the deliverable

---

## Phase 6: CLOSE

**Update backlog index status based on Phase 5 decision:**

| Outcome | Status Update |
|---------|---------------|
| Fix approved | `--status COMPLETE` |
| Fix reverted | `--status NOT_STARTED` |
| Task list completed | `--status COMPLETE` |
| Session plan created | `--status PLANNING` |
| Skipped | No change |

```bash
python .claude/skills/backlog/scripts/update_backlog.py --id "{item_id}" --status "{new_status}"
```

**Re-score after status changes:**
```bash
python .claude/skills/backlog/scripts/score_backlog.py
```

**Automatic archival:** When status is set to COMPLETE or CLOSED, the script automatically:
- Moves item file(s) to the Archive/ directory
- Updates index links to point to `Archive/` subfolder

**Print summary table:**

```
ID  | Feature                              | Action        | Status
----|--------------------------------------|---------------|--------
002 | Fix login redirect bug               | Direct Fix    | COMPLETE
001 | Setup project CI pipeline            | Plan Created  | PLANNING
003 | Add user profile page                | Skipped       | IN_PROGRESS
```

---

## Phase 7: LESSON CAPTURE (Optional)

After closing all triaged items, prompt for lessons learned.

**Ask the user:** "Were any lessons learned during this triage session? (y/n)"

**If no:** Skip this phase and finish.

**If yes:** Capture the lesson in whatever format your project uses for lessons learned. If a lessons directory is configured in config.yaml, write a lesson file there.

### Backlog Lesson Categories

| Category | When to Capture | Example |
|----------|-----------------|---------|
| `triage-routing` | Routing decision was non-obvious | "Item appeared simple but required planning due to cross-cutting dependencies" |
| `scope-assessment` | Scope signals were misleading | "Bug keyword but actual issue was architectural" |
| `resolution-outcome` | Fix succeeded or failed in a noteworthy way | "Direct fix worked but revealed a related issue" |

---

## Additional Resources

- [reference.md](reference.md) — Backlog format, routing decision tree, script interfaces, status flow
- [templates/triage-prompt.md](templates/triage-prompt.md) — Fix delegation prompt template

---

## Error Handling

| Situation | Action |
|-----------|--------|
| Index file not found | Script exits with error; print path and STOP |
| Item ID not found | Print error; ask user to verify ID |
| Item file not found | Warn user; skip scope analysis, ask for manual route |
| Fix agent fails | User decides in Phase 5 (revert or skip) |
| Status update fails | Print error; continue to next item |
| No items match filter | Print "No items match filters." and STOP |

---

## Quick Start

```
/backlog                    # Interactive: fetch -> select -> triage
/backlog 002                # Triage a specific item by ID
```
