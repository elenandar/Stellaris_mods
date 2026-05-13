#!/usr/bin/env python3
"""Build Russian localisation skeleton files from fresh English localisation files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

try:
    from stellaris_loc_common import (
        english_to_russian_relative_path,
        read_utf8,
        replace_english_header_with_russian,
        write_utf8_bom,
    )
    from stellaris_loc_scan import find_english_localisation_files
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_common import (
        english_to_russian_relative_path,
        read_utf8,
        replace_english_header_with_russian,
        write_utf8_bom,
    )
    from tools.stellaris_loc_scan import find_english_localisation_files


@dataclass
class RebuildSummary:
    english_files_found: int = 0
    files_created: int = 0
    files_updated: int = 0
    files_skipped: int = 0
    dry_run_actions: int = 0


def rebuild_skeletons(fresh_root: Path, russian_root: Path, dry_run: bool = False) -> RebuildSummary:
    summary = RebuildSummary()
    english_files = find_english_localisation_files(fresh_root)
    summary.english_files_found = len(english_files)

    for english_file in english_files:
        english_relative = english_file.relative_to(fresh_root)
        russian_relative = english_to_russian_relative_path(english_relative)
        russian_file = russian_root / russian_relative

        english_text, _, read_error = read_utf8(english_file)
        if read_error is not None:
            summary.files_skipped += 1
            print(f"SKIP read error: {english_file} ({read_error})")
            continue

        russian_text, header_replaced = replace_english_header_with_russian(english_text)
        if not header_replaced:
            summary.files_skipped += 1
            print(f"SKIP no l_english header: {english_file}")
            continue

        already_exists = russian_file.exists()
        action = "UPDATE" if already_exists else "CREATE"

        if dry_run:
            summary.dry_run_actions += 1
            print(f"DRY-RUN {action}: {russian_file}")
            continue

        write_utf8_bom(russian_file, russian_text, dry_run=False)

        if already_exists:
            summary.files_updated += 1
        else:
            summary.files_created += 1

        print(f"{action}: {russian_file}")

    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create Russian Stellaris localisation skeleton files from English files.",
    )
    parser.add_argument("--fresh-root", required=True, help="Path to fresh mod root.")
    parser.add_argument("--russian-root", required=True, help="Path to Russian output root.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned write operations without writing files.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    fresh_root = Path(args.fresh_root).expanduser().resolve()
    russian_root = Path(args.russian_root).expanduser().resolve()

    if not fresh_root.exists() or not fresh_root.is_dir():
        parser.error(f"Fresh root is not an existing directory: {fresh_root}")

    summary = rebuild_skeletons(fresh_root=fresh_root, russian_root=russian_root, dry_run=args.dry_run)

    print("Summary")
    print("=======")
    print(f"English files found: {summary.english_files_found}")
    print(f"Files created: {summary.files_created}")
    print(f"Files updated: {summary.files_updated}")
    print(f"Files skipped: {summary.files_skipped}")
    print(f"Dry-run actions: {summary.dry_run_actions}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
