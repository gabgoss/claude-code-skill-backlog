# Backlog — Reference

Detailed documentation for the `/backlog` skill.

---

## 1. Backlog Index Format

**Source file:** Configured in `config.yaml` under `project.backlog_dir` / `project.index_file`

### Table Columns

| Column | Type | Description |
|--------|------|-------------|
| ID | 3-digit zero-padded (001-999) | Unique backlog item number |
| Feature | Free text | Short description of the item |
| Priority | High, Medium, Low | Item priority level |
| Status | See status values below | Current item state |
| Abbrev | 2-4 chars | Category abbreviation (defined in config.yaml) |
| Score | Integer or `-` | Computed priority score (open items only; `-` for COMPLETE/CLOSED) |
| Files | Markdown links | Reference files: `[01](path.md) [02](path2.md)` |

### Status Values

| Status | Description |
|--------|-------------|
| NOT_STARTED | Item identified but no work begun |
| PLANNING | Requirements gathering or design in progress |
| IN_PROGRESS | Active development |
| BLOCKED | Waiting on dependency or decision |
| COMPLETE | Implemented and verified |
| CLOSED | Resolved without implementation (duplicate, won't fix, etc.) |

### Abbreviations

Define your project's abbreviations in `config.yaml` under the `abbreviations` section.

### File Naming Convention

**Pattern:** `{Abbrev}-{XXX}-{YY}-{Topic}.md`

| Component | Description | Example |
|-----------|-------------|---------|
| `Abbrev` | Category abbreviation | `APP` |
| `XXX` | Backlog index number | `003` |
| `YY` | Document reference within item | `01`, `02` |
| `Topic` | Descriptive name (PascalCase) | `UserProfilePage` |

Multiple files per item: `YY` increments (01, 02, 03...).

---

## 2. Routing Decision Tree

### Scope Assessment Signals

| Signal | How to Detect | Weight |
|--------|---------------|--------|
| "Bug" in feature name | Case-insensitive check on Feature column | Strong -> Direct Fix |
| Item file < 50 lines | Line count on read | Strong -> Direct Fix |
| Specific file paths mentioned | Regex for code file extensions | Moderate -> Direct Fix |
| "multi-sprint" / "phased" keywords | Case-insensitive content search | Strong -> Session Planning |
| "refactor" / "redesign" / "architecture" / "migration" | Content keywords | Strong -> Session Planning |
| 6+ sub-items or ## headings | Count numbered list items and H2 headers | Moderate -> Session Planning |
| Multiple reference files (YY > 01) | Files column has 2+ links | Moderate -> Session Planning |
| 3-5 numbered steps | Count discrete steps | Moderate -> Task List |

### Decision Logic

```
1. Read item file(s)
2. Compute signals

IF (IS_BUG AND IS_SHORT) OR (IS_SHORT AND HAS_CLEAR_FIX):
    -> DIRECT FIX

ELIF HAS_MULTI_SPRINT OR IS_ARCHITECTURAL OR (SUB_ITEMS >= 6):
    -> SESSION PLANNING

ELIF 2 <= STEP_COUNT <= 5:
    -> TASK LIST

ELSE:
    -> SESSION PLANNING (conservative default)

3. Present recommendation via AskUserQuestion
4. User can override to any route or skip
```

---

## 3. Action Routes

### Route A: Direct Fix

**When:** Bug with clear scope, item file < 50 lines, specific fix described.

**Process:**
1. Read [templates/triage-prompt.md](templates/triage-prompt.md)
2. Fill in all placeholders with item details and file content
3. Launch: `Task(general-purpose, prompt=<assembled prompt>)`
4. Agent reads the relevant source files, makes the fix, verifies build
5. Results reviewed in Phase 5

### Route B: Task List

**When:** Medium scope, 3-5 discrete steps, completable in one session.

**Process:**
1. Analyze item file to extract discrete work items
2. Create tasks with `TaskCreate` for each step
3. Work through tasks sequentially (or delegate via Task tool)
4. Mark each task completed as it finishes
5. Results reviewed in Phase 5

### Route C: Session Planning

**When:** Multi-sprint scope, architectural changes, unclear requirements.

**Process:**
1. Summarize the backlog item and its reference files
2. Tell the user the item needs a full plan
3. Update status to PLANNING
4. No further action in this session

---

## 4. Script Interfaces

### parse_backlog.py

```
python .claude/skills/backlog/scripts/parse_backlog.py [OPTIONS]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--status STATUS` | No | Filter by status (case-insensitive) |
| `--priority PRIORITY` | No | Filter by priority (case-insensitive) |
| `--abbrev ABBREV` | No | Filter by abbreviation (case-insensitive) |
| `--id ID` | No | Filter by specific item ID |
| `--include-closed` | No | Include COMPLETE/CLOSED items |
| `--show-blocked` | No | Include items blocked by open dependencies (hidden by default) |

**Output:** Formatted table of selectable items + blocked items summary + JSON temp file path.

**JSON schema:**
```json
[
  {
    "id": "002",
    "feature": "Fix login redirect bug",
    "priority": "High",
    "status": "NOT_STARTED",
    "abbrev": "BUG",
    "files": [
      {"label": "01", "path": "BUG-002-01-LoginRedirectBug.md"}
    ]
  }
]
```

### update_backlog.py

```
python .claude/skills/backlog/scripts/update_backlog.py --id ID --status STATUS
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--id ID` | Yes | Item ID (e.g., 002) |
| `--status STATUS` | Yes | New status (NOT_STARTED, PLANNING, IN_PROGRESS, BLOCKED, COMPLETE, CLOSED) |

**Automatic archival (COMPLETE/CLOSED):**
When status is set to COMPLETE or CLOSED, the script automatically:
1. Extracts file links from the index row's Files column
2. Moves each file to the Archive/ directory
3. Updates index links to point to Archive/
4. Idempotent: already-archived files are skipped

### score_backlog.py

```
python .claude/skills/backlog/scripts/score_backlog.py [OPTIONS]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--dry-run` | No | Compute and print scores without writing to the index |
| `--review` | No | Output a priority review report (no index writes) |

---

## 5. Status Flow

```
NOT_STARTED --[select in Phase 2]--> IN_PROGRESS
                                          |
                  +-----------------------+-----------------------+
                  |                       |                       |
                  v                       v                       v
            DIRECT FIX               TASK LIST              SESSION PLAN
                  |                       |                       |
            +-----+                       |                       |
            |     |                       v                       v
   Approved v  Reverted v         All done --> COMPLETE    Plan --> PLANNING
         COMPLETE  NOT_STARTED
```

---

## 6. Scoring System

Items are ranked by a computed priority score using 8 weighted factors. All weights are configurable in `config.yaml`.

### Scoring Factors

| # | Factor | Default Points | Source |
|---|--------|---------------|--------|
| 1 | Priority | High=30, Med=20, Low=10 | Index: Priority column |
| 2 | Bug/Fix keyword | +15 | Index: Feature contains "Bug" or "Fix" |
| 3 | IN_PROGRESS boost | +10 | Index: Status column |
| 4 | File count | +5 per extra file (beyond 1) | Index: Files column |
| 5 | PLANNING penalty | -5 | Index: Status = PLANNING |
| 6 | Blocks count | +20 per open item blocked | Item YAML: `blocks` field |
| 7 | Abbrev momentum | +5 | Archive: same-abbrev item recently completed |
| 8 | Age | +1 per week (cap: +12) | Item YAML: `created` field |

### Priority Review

`score_backlog.py --review` surfaces items needing attention:
- Items with age > 8 weeks (approaching cap)
- Score/priority mismatch
- All IN_PROGRESS items (staleness check)
- High-impact blockers (blocks 2+ items)

---

## 7. YAML Frontmatter Format

```yaml
---
title: "Item title"
created: 2026-01-15
status: NOT_STARTED
blocks: []
---
```

| Field | Type | Used By |
|-------|------|---------|
| `title` | string | Display |
| `created` | date (YYYY-MM-DD) | Scoring factor 8 (age) |
| `status` | string | Synced by `update_backlog.py` |
| `blocks` | list of item IDs | Scoring factor 6 (blocks count) |

---

## 8. Troubleshooting

| Issue | Solution |
|-------|----------|
| `Error: config.yaml not found` | Copy config.yaml from starter kit to your skill directory |
| `Error: Backlog index not found` | Verify path in config.yaml matches your project structure |
| `Error: Item ID not found` | Check the ID exists in the index; IDs are zero-padded (002, not 2) |
| `No items match filters` | Remove filters or use `--include-closed` to see all items |
| Parse error on table | Table format may have changed; check separator row and column count |
| Status update doesn't stick | Verify the file isn't open in another editor with unsaved changes |
