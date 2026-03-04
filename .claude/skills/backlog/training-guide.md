# Backlog — Training Guide

A practical guide to managing your project backlog using the scoring system and `/backlog` skill.

---

## 1. Quick Start

### Run a triage session

```
/backlog              # Interactive: score, parse, select, fix/plan
/backlog 002          # Triage a specific item by ID
```

### Score items manually (outside triage)

```bash
python .claude/skills/backlog/scripts/score_backlog.py           # Score + write to index
python .claude/skills/backlog/scripts/score_backlog.py --dry-run # Score without writing
python .claude/skills/backlog/scripts/score_backlog.py --review  # Priority review report
```

### View filtered items

```bash
python .claude/skills/backlog/scripts/parse_backlog.py                  # All open items
python .claude/skills/backlog/scripts/parse_backlog.py --priority High  # High priority only
python .claude/skills/backlog/scripts/parse_backlog.py --abbrev APP     # Single category
python .claude/skills/backlog/scripts/parse_backlog.py --status IN_PROGRESS  # Active work
```

### Update an item's status

```bash
python .claude/skills/backlog/scripts/update_backlog.py --id 002 --status IN_PROGRESS
```

This updates both the index table and the item file's YAML frontmatter. Setting COMPLETE or CLOSED automatically archives the item file.

---

## 2. How Scoring Works

Every open item gets a numeric score computed from 8 factors (all configurable in `config.yaml`). Higher score = higher priority for attention.

### Factor Breakdown

| # | Factor | Default Points | What It Measures |
|---|--------|---------------|------------------|
| 1 | **Priority** | 30 / 20 / 10 | Base weight from High/Medium/Low |
| 2 | **Bug/Fix keyword** | +15 | Title contains "Bug" or "Fix" |
| 3 | **IN_PROGRESS boost** | +10 | Active work gets a bump to stay visible |
| 4 | **File count** | +5 per extra | Items with more reference files are complex |
| 5 | **PLANNING penalty** | -5 | Planning items score lower than actionable ones |
| 6 | **Blocks count** | +20 per open item | Items that block others are high-leverage |
| 7 | **Momentum** | +5 | Same-abbrev item was recently completed |
| 8 | **Age** | +1/week (max 12) | Older items slowly rise to prevent neglect |

### Reading Scores

| Score Range | What It Means |
|-------------|---------------|
| 40+ | Top priority. High + multiple boosters (bugs, blockers, momentum). Act first. |
| 30-39 | High priority or medium with strong signals. Strong candidates for next session. |
| 20-29 | Medium priority baseline. Standard backlog items. |
| 10-19 | Low priority or new items without boosters. Address when bandwidth allows. |

---

## 3. Priority Review

Run `score_backlog.py --review` to surface items needing attention. The report has four sections:

### Age Cap Warning (> 8 weeks)

Items approaching the 12-week age cap are accumulating "sympathy points" instead of being worked on. Consider:
- **Reprioritize** — raise to High if it's actually important
- **Close** — if it's no longer relevant
- **Plan** — if it needs a plan to become actionable

### Score/Priority Mismatch

A Low-priority item scoring 25+ (or a High-priority item scoring under 20) suggests the declared priority doesn't match reality.

### IN_PROGRESS Staleness

All IN_PROGRESS items are listed for review. Items sitting IN_PROGRESS across sessions may be stalled, forgotten, or already done.

### High-Impact Blockers

Items that `blocks` 2+ other items. These are force multipliers — completing them unblocks downstream work.

---

## 4. Creating New Backlog Items

### Step 1: Choose the next ID

Look at the last row in your backlog index and increment by 1.

### Step 2: Create the item file

Use the template at `templates/backlog-item.md`. Key fields:

```yaml
---
id: 004
title: "My New Feature"
priority: Medium
status: NOT_STARTED
abbrev: APP
created: 2026-01-15
blocks: []
---
```

**Scoring tips:**
- Include "Bug" or "Fix" in the title if applicable (activates bonus)
- Populate `blocks` if this item unblocks others (each adds a scoring boost)
- Set `created` to today's date (age scoring starts from this date)

### Step 3: Add to the index

Add a row to the `## Backlog Items` table:

```markdown
| 004 | My New Feature | Medium | NOT_STARTED | APP | 0 | [01](APP-004-01-MyNewFeature.md) |
```

### Step 4: Score

Run `score_backlog.py` to compute and write the actual score to the index.

---

## 5. Triage Workflow Overview

When you invoke `/backlog`, the skill follows 7 phases:

```
Phase 1: FETCH     Score items, then parse and display the table
Phase 2: SELECT    Pick items to triage (or pass an ID as argument)
Phase 3: RESOLVE   Read item files, assess scope, recommend a route
Phase 4: ACT       Execute the chosen route (fix, task list, or plan)
Phase 5: VERIFY    Review results, approve or revert
Phase 6: CLOSE     Update status, re-score, archive if complete
Phase 7: LESSONS   Capture any lessons learned (optional)
```

### Route Selection

| Signal | Route | What Happens |
|--------|-------|--------------|
| Bug + short file + clear fix | **Direct Fix** | Agent makes the fix, you review |
| 3-5 discrete steps | **Task List** | Tasks created, worked sequentially |
| Multi-sprint / architectural / 6+ sub-items | **Session Planning** | Deferred to planning |

---

## 6. Blocking Graph

The `blocks` field in YAML frontmatter creates a dependency graph. When item A blocks items B and C:

```yaml
# In item A's frontmatter:
blocks: [004, 005]
```

This gives item A a scoring boost per blocked item, surfacing it as a high-leverage target.

**Blocked items are hidden from triage:** Items whose blockers are still open are automatically excluded from the selectable list. Use `--show-blocked` to include them.

---

## 7. Common Tasks

### "What should I work on next?"

```bash
python .claude/skills/backlog/scripts/parse_backlog.py --priority High
```

The top-scored item is the highest-leverage choice.

### "Is anything stale or misaligned?"

```bash
python .claude/skills/backlog/scripts/score_backlog.py --review
```

### "How many items are open for category X?"

```bash
python .claude/skills/backlog/scripts/parse_backlog.py --abbrev APP
```

### "Mark an item done"

```bash
python .claude/skills/backlog/scripts/update_backlog.py --id 002 --status COMPLETE
```

---

## 8. Setup for a New Project

1. Copy the entire `backlog/` directory to your project's `.claude/skills/`
2. Edit `config.yaml`:
   - Set `project.name` to your project name
   - Set `project.backlog_dir` to where you want backlog files (e.g., `docs/backlog`)
   - Define your abbreviations
   - Tune scoring weights if needed
   - Configure `build_commands` for your tech stack
3. Copy `seed/00-Index-Backlog.md` to your backlog directory
4. Replace the example items with your real backlog items
5. Run `/backlog` to verify everything works
