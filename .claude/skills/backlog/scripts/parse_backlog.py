#!/usr/bin/env python3
"""Parse the backlog index markdown and output filtered items."""

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

# Fix Windows cp1252 stdout encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Import shared config loader
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_loader import load_config


def parse_backlog_table(content: str) -> list[dict]:
    """Parse the Backlog Items markdown table into a list of dicts."""
    items = []

    section_match = re.search(r"## Backlog Items\s*\n", content)
    if not section_match:
        print("Error: Could not find '## Backlog Items' section in index file.", file=sys.stderr)
        sys.exit(1)

    section_content = content[section_match.end():]
    lines = section_content.split("\n")
    in_table = False
    header_seen = False
    separator_seen = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## ") or stripped.startswith("---"):
            if in_table:
                break
            if stripped.startswith("---") and separator_seen:
                break
            continue

        if not header_seen and re.match(r"\|\s*ID\s*\|", stripped):
            header_seen = True
            in_table = True
            continue

        if header_seen and not separator_seen and re.match(r"\|[-\s|]+\|", stripped):
            separator_seen = True
            continue

        if separator_seen and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]

            if len(cells) >= 6:
                if len(cells) >= 7:
                    score_raw = cells[5].strip()
                    try:
                        score = int(score_raw) if score_raw else 0
                    except ValueError:
                        score = 0
                    files_raw = cells[6].strip()
                else:
                    score = 0
                    files_raw = cells[5].strip()

                file_links = re.findall(r"\[(\d+)\]\(([^)]+)\)", files_raw)
                files = [{"label": label, "path": path} for label, path in file_links]

                items.append({
                    "id": cells[0].strip(),
                    "feature": cells[1].strip(),
                    "priority": cells[2].strip(),
                    "status": cells[3].strip(),
                    "abbrev": cells[4].strip(),
                    "score": score,
                    "files": files,
                })

    return items


def parse_dependencies_table(content: str) -> list[dict]:
    """Parse the Dependencies table from the index.

    Returns list of dicts with keys: blocker_id, blocked_ids (list of str).
    Only parses hard blockers — stops at "Soft dependencies" or next section.
    """
    deps = []
    section_match = re.search(r"## Dependencies\s*\n", content)
    if not section_match:
        return deps

    section_content = content[section_match.end():]
    lines = section_content.split("\n")
    header_seen = False
    separator_seen = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("**Soft dependencies"):
            break

        if not header_seen and re.match(r"\|\s*ID\s*\|", stripped):
            header_seen = True
            continue

        if header_seen and not separator_seen and re.match(r"\|[-\s|]+\|", stripped):
            separator_seen = True
            continue

        if separator_seen and stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2:
                blocker_id = cells[0].strip().zfill(3)
                blocked_raw = cells[1].strip()
                blocked_ids = [b.strip().zfill(3) for b in blocked_raw.split(",")]
                deps.append({
                    "blocker_id": blocker_id,
                    "blocked_ids": blocked_ids,
                })

    return deps


def build_blocked_by_map(
    dependencies: list[dict], items: list[dict]
) -> dict[str, list[str]]:
    """Build reverse dependency map: blocked_item_id -> [open blocker IDs]."""
    closed_statuses = {"COMPLETE", "CLOSED"}
    status_map = {item["id"]: item["status"] for item in items}
    blocked_by: dict[str, list[str]] = {}

    for dep in dependencies:
        blocker = dep["blocker_id"]
        if status_map.get(blocker, "") not in closed_statuses:
            for blocked_id in dep["blocked_ids"]:
                blocked_by.setdefault(blocked_id, []).append(blocker)

    return blocked_by


def filter_items(
    items: list[dict],
    status: str | None = None,
    priority: str | None = None,
    abbrev: str | None = None,
    item_id: str | None = None,
    include_closed: bool = False,
    blocked_by_map: dict[str, list[str]] | None = None,
    show_blocked: bool = False,
) -> tuple[list[dict], list[dict]]:
    """Filter items by provided criteria. Returns (selectable_items, blocked_items)."""
    filtered = []
    blocked = []
    for item in items:
        if not include_closed and item["status"] in ("COMPLETE", "CLOSED"):
            continue
        if status and item["status"].upper() != status.upper():
            continue
        if priority and item["priority"].lower() != priority.lower():
            continue
        if abbrev and item["abbrev"].upper() != abbrev.upper():
            continue
        if item_id and item["id"].lstrip("0") != item_id.lstrip("0"):
            continue

        if blocked_by_map and not show_blocked:
            if blocked_by_map.get(item["id"]):
                blocked.append(item)
                continue

        filtered.append(item)

    return filtered, blocked


def format_table(items: list[dict], sort_by: str = "score") -> str:
    """Format items as a readable table."""
    if not items:
        return "No items match filters."

    if sort_by == "score":
        items = sorted(items, key=lambda x: (-x.get("score", 0), x["id"]))
    else:
        items = sorted(items, key=lambda x: x["id"])

    id_w = max(len(item["id"]) for item in items)
    id_w = max(id_w, 2)
    feat_w = max(len(item["feature"]) for item in items)
    feat_w = min(max(feat_w, 7), 55)
    pri_w = max(len(item["priority"]) for item in items)
    pri_w = max(pri_w, 8)
    stat_w = max(len(item["status"]) for item in items)
    stat_w = max(stat_w, 6)
    abbr_w = max(len(item["abbrev"]) for item in items)
    abbr_w = max(abbr_w, 6)
    score_w = 5
    files_w = 5

    header = (
        f"{'ID':<{id_w}} | {'Feature':<{feat_w}} | {'Priority':<{pri_w}} | "
        f"{'Status':<{stat_w}} | {'Abbrev':<{abbr_w}} | {'Score':>{score_w}} | {'Files':<{files_w}}"
    )
    separator = (
        f"{'-' * id_w}-+-{'-' * feat_w}-+-{'-' * pri_w}-+-"
        f"{'-' * stat_w}-+-{'-' * abbr_w}-+-{'-' * score_w}-+-{'-' * files_w}"
    )

    lines = [header, separator]

    for item in items:
        feature = item["feature"]
        if len(feature) > 55:
            feature = feature[:52] + "..."
        file_count = str(len(item["files"]))
        score_str = str(item.get("score", 0))

        lines.append(
            f"{item['id']:<{id_w}} | {feature:<{feat_w}} | {item['priority']:<{pri_w}} | "
            f"{item['status']:<{stat_w}} | {item['abbrev']:<{abbr_w}} | {score_str:>{score_w}} | {file_count:<{files_w}}"
        )

    lines.append(f"\n{len(items)} item(s) found.")
    return "\n".join(lines)


def format_blocked_summary(
    blocked_items: list[dict], blocked_by_map: dict[str, list[str]]
) -> str:
    """Format a summary of blocked items with their blockers."""
    if not blocked_items:
        return ""

    lines = ["", "--- Blocked Items (resolve blockers first) ---"]

    for item in sorted(blocked_items, key=lambda x: (-x.get("score", 0), x["id"])):
        blockers = blocked_by_map.get(item["id"], [])
        blocker_str = ", ".join(blockers)
        feature = item["feature"]
        if len(feature) > 45:
            feature = feature[:42] + "..."
        score_str = str(item.get("score", 0))
        lines.append(
            f"  {item['id']} | {feature:<45} | {score_str:>3} pts | blocked by: {blocker_str}"
        )

    lines.append(f"\n{len(blocked_items)} item(s) blocked.")
    return "\n".join(lines)


def write_json(items: list[dict]) -> str:
    """Write items to a JSON temp file and return the path."""
    tmp_dir = tempfile.mkdtemp(prefix="backlog-")
    json_path = os.path.join(tmp_dir, "items.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
    return json_path


def main():
    parser = argparse.ArgumentParser(
        description="Parse the backlog index and output filtered items."
    )
    parser.add_argument("--status", help="Filter by status (e.g., NOT_STARTED, IN_PROGRESS)")
    parser.add_argument("--priority", help="Filter by priority (e.g., High, Medium, Low)")
    parser.add_argument("--abbrev", help="Filter by abbreviation")
    parser.add_argument("--id", help="Filter by specific item ID (e.g., 003)")
    parser.add_argument("--include-closed", action="store_true", help="Include COMPLETE and CLOSED items")
    parser.add_argument("--show-blocked", action="store_true", help="Include items blocked by open dependencies")
    parser.add_argument("--sort", choices=["score", "id"], default="score", help="Sort order (default: score descending)")

    args = parser.parse_args()

    # Load config
    config = load_config(Path(__file__))
    index_path = config["_index_path"]

    if not index_path.exists():
        print(f"Error: Backlog index not found at {index_path}", file=sys.stderr)
        sys.exit(1)

    content = index_path.read_text(encoding="utf-8")
    all_items = parse_backlog_table(content)
    dependencies = parse_dependencies_table(content)
    blocked_by_map = build_blocked_by_map(dependencies, all_items)

    filtered, blocked = filter_items(
        all_items,
        status=args.status,
        priority=args.priority,
        abbrev=args.abbrev,
        item_id=args.id,
        include_closed=args.include_closed,
        blocked_by_map=blocked_by_map,
        show_blocked=args.show_blocked,
    )

    print(format_table(filtered, sort_by=args.sort))

    if blocked:
        print(format_blocked_summary(blocked, blocked_by_map))

    if filtered:
        json_path = write_json(filtered)
        print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
