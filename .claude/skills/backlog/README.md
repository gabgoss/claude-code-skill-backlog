# Backlog — Starter Kit

A portable, configurable backlog management skill for Claude Code projects.

## What This Does

- **Scores** backlog items using 8 weighted factors (priority, bug keywords, blockers, age, etc.)
- **Parses** a markdown-based backlog index with filtering, sorting, and dependency awareness
- **Routes** items to the right workflow: direct fix, task list, or session planning
- **Updates** status with automatic YAML frontmatter sync and archival of completed items
- **Captures** lessons learned from triage sessions

## Quick Setup

### 1. Copy to your project

```bash
cp -r StarterKit/backlog/ .claude/skills/backlog/
```

### 2. Edit config.yaml

Open `.claude/skills/backlog/config.yaml` and customize:

```yaml
project:
  name: "YourProject"
  backlog_dir: "docs/backlog"         # Where backlog files live
  archive_dir: "docs/backlog/archive" # Where completed items go
  index_file: "00-Index-Backlog.md"   # The master index filename

abbreviations:
  APP: "Application features"
  API: "API endpoints"
  UI: "Frontend changes"
  # ... your categories

build_commands:
  default: "npm test"                 # Your build/test command
```

### 3. Create your backlog directory

```bash
mkdir -p docs/backlog/archive
cp .claude/skills/backlog/seed/00-Index-Backlog.md docs/backlog/
```

Edit the seed file to replace example items with your real backlog.

### 4. Test it

```
/backlog
```

## Directory Structure

```
backlog/
├── README.md              # This file
├── config.yaml            # Project-specific settings (EDIT THIS)
├── SKILL.md               # Skill workflow (Claude-facing)
├── reference.md           # Format specs and script interfaces
├── training-guide.md      # How to use the system
├── templates/
│   ├── backlog-item.md    # Template for new items
│   └── triage-prompt.md   # Template for fix delegation
├── scripts/
│   ├── config_loader.py   # Shared config reader
│   ├── score_backlog.py   # 8-factor scoring engine
│   ├── parse_backlog.py   # Index parser with filters
│   └── update_backlog.py  # Status updater with archival
└── seed/
    └── 00-Index-Backlog.md  # Starter backlog index
```

## What You Customize (config.yaml)

| Setting | Purpose | Example |
|---------|---------|---------|
| `project.backlog_dir` | Where backlog files live | `docs/backlog` |
| `abbreviations` | Your project's category codes | `API`, `UI`, `DATA` |
| `scoring.*` | Tune scoring weights | Increase `blocks_bonus` for dependency-heavy projects |
| `build_commands` | Build/test commands for fix verification | `npm test`, `cargo build` |

## What You Don't Touch

The Python scripts, SKILL.md workflow, and templates work unchanged across projects. They read all project-specific values from `config.yaml`.

## Requirements

- Python 3.10+ (for `match` syntax and `X | Y` type unions)
- Optional: `pyyaml` (`pip install pyyaml`) — scripts fall back to regex parsing if unavailable
- Claude Code CLI or VS Code extension with Claude Code
