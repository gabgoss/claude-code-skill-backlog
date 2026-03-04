#!/usr/bin/env python3
"""Shared config loader for backlog scripts.

Reads config.yaml from the skill directory and resolves paths
relative to the project root.
"""

import re
import sys
from pathlib import Path

# Try yaml import; fall back to regex extraction
try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def find_project_root(start_path: Path) -> Path:
    """Walk upward from start_path to find the project root (has CLAUDE.md or .claude/)."""
    current = start_path.resolve()
    while current != current.parent:
        if (current / "CLAUDE.md").exists() or (current / ".claude").is_dir():
            return current
        current = current.parent
    raise FileNotFoundError(
        "Could not find project root (no CLAUDE.md or .claude/ found walking upward)"
    )


def _parse_yaml_simple(text: str) -> dict:
    """Minimal YAML parser for flat and one-level-nested structures.

    Handles the config.yaml format without requiring PyYAML.
    """
    result: dict = {}
    current_section = None

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Top-level key with nested content (ends with ':' and no value)
        if re.match(r"^[a-zA-Z_]\w*:\s*$", stripped):
            current_section = stripped.rstrip(":").strip()
            result[current_section] = {}
            continue

        # Top-level key with scalar value
        top_match = re.match(r"^([a-zA-Z_]\w*):\s+(.+)$", stripped)
        if top_match and current_section is None:
            key, val = top_match.group(1), top_match.group(2).strip().strip("'\"")
            result[key] = _coerce(val)
            continue

        # Nested key-value under a section
        nested_match = re.match(r"^\s+([a-zA-Z_]\w*):\s+(.+)$", stripped)
        if nested_match and current_section is not None:
            key, val = nested_match.group(1), nested_match.group(2).strip().strip("'\"")
            result[current_section][key] = _coerce(val)
            continue

        # List item under a section
        list_match = re.match(r"^\s+-\s+(.+)$", stripped)
        if list_match and current_section is not None:
            val = list_match.group(1).strip().strip("'\"")
            if not isinstance(result[current_section], list):
                result[current_section] = []
            result[current_section].append(_coerce(val))
            continue

        # Top-level key starting a new context resets section
        if re.match(r"^[a-zA-Z_]", stripped):
            current_section = None
            top_match2 = re.match(r"^([a-zA-Z_]\w*):\s*(.*)$", stripped)
            if top_match2:
                key = top_match2.group(1)
                val = top_match2.group(2).strip().strip("'\"")
                if val:
                    result[key] = _coerce(val)
                else:
                    current_section = key
                    result[key] = {}

    return result


def _coerce(val: str):
    """Coerce string values to int, float, or bool where obvious."""
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def load_config(script_path: Path | None = None) -> dict:
    """Load config.yaml from the skill directory.

    Args:
        script_path: Path to the calling script. If None, uses __file__.

    Returns:
        Parsed config dict with resolved paths.
    """
    if script_path is None:
        script_path = Path(__file__)

    # config.yaml lives one level up from scripts/
    skill_dir = script_path.resolve().parent.parent
    config_path = skill_dir / "config.yaml"

    if not config_path.exists():
        print(f"Error: config.yaml not found at {config_path}", file=sys.stderr)
        print("Copy config.yaml from the starter kit and customize it.", file=sys.stderr)
        sys.exit(1)

    raw = config_path.read_text(encoding="utf-8")

    if HAS_YAML:
        config = yaml.safe_load(raw) or {}
    else:
        config = _parse_yaml_simple(raw)

    # Resolve project root
    try:
        project_root = find_project_root(skill_dir)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    config["_project_root"] = project_root
    config["_skill_dir"] = skill_dir

    # Resolve backlog paths
    project = config.get("project", {})
    backlog_rel = project.get("backlog_dir", "Backlog")
    config["_backlog_dir"] = project_root / backlog_rel
    config["_archive_dir"] = project_root / project.get("archive_dir", f"{backlog_rel}/Archive")
    config["_index_path"] = config["_backlog_dir"] / project.get("index_file", "00-Index-Backlog.md")

    # Resolve lessons paths (optional)
    lessons_dir = project.get("lessons_dir", "")
    if lessons_dir:
        config["_lessons_dir"] = project_root / lessons_dir
        config["_lessons_index"] = config["_lessons_dir"] / project.get("lessons_index", "00-Index-LessonsLearned.md")
    else:
        config["_lessons_dir"] = None
        config["_lessons_index"] = None

    return config


def get_scoring_weights(config: dict) -> dict:
    """Extract scoring weights from config, with defaults."""
    scoring = config.get("scoring", {})
    return {
        "priority_high": scoring.get("priority_high", 30),
        "priority_medium": scoring.get("priority_medium", 20),
        "priority_low": scoring.get("priority_low", 10),
        "bug_fix_bonus": scoring.get("bug_fix_bonus", 15),
        "in_progress_bonus": scoring.get("in_progress_bonus", 10),
        "file_count_bonus": scoring.get("file_count_bonus", 5),
        "planning_penalty": scoring.get("planning_penalty", -5),
        "blocks_bonus": scoring.get("blocks_bonus", 20),
        "momentum_bonus": scoring.get("momentum_bonus", 5),
        "age_bonus_per_week": scoring.get("age_bonus_per_week", 1),
        "age_cap": scoring.get("age_cap", 12),
    }
