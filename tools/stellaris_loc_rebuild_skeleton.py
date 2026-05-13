#!/usr/bin/env python3
"""Build Russian localisation skeleton files from fresh English localisation files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

try:
    from stellaris_loc_scan import find_english_localisation_files
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_scan import find_english_localisation_files


@dataclass
class RebuildSummary:
    english_files_found: int = 0
    files_created: int = 0
    files_updated: int = 0
    files_skipped: int = 0
    dry_run_actions: int = 0


def english_to_russian_relative_path(english_relative: Path) -> Path:
    """Map an English localisation relative path to expected Russian path."""
    parts = ["russian" if p == "english" else p for p in english_relative.parts]
    if not parts:
        return english_relative

    filename = parts[-1]
    if filename.endswith("_l_english.yml"):
        filename = filename[: -len("_l_english.yml")] + "_l_russian.yml"
    elif "l_english" in filename:
        filename = filename.replace("l_english", "l_russian")
    parts[-1] = filename
    return Path(*parts)


def _replace_english_header_with_russian(text: str) -> tuple[str, bool]:
    lines = text.splitlines(keepends=True)
    replaced = False

    for idx, line in enumerate(lines):
        body = line.rstrip("\r\n")
        eol = line[len(body) :]
        if body.strip() == "l_english:":
            indent = body[: len(body) - len(body.lstrip())]
            lines[idx] = f"{indent}l_russian:{eol}"
            replaced = True
            break

    if not replaced and not lines and text.strip() == "l_english:":
        return "l_russian:", True

    return "".join(lines), replaced


def rebuild_skeletons(fresh_root: Path, russian_root: Path, dry_run: bool = False) -> RebuildSummary:
    summary = RebuildSummary()
    english_files = find_english_localisation_files(fresh_root)
    summary.english_files_found = len(english_files)

    for english_file in english_files:
        english_relative = english_file.relative_to(fresh_root)
        russian_relative = english_to_russian_relative_path(english_relative)
        russian_file = russian_root / russian_relative

        try:
            english_text = english_file.read_text(encoding="utf-8-sig")
        except OSError:
            summary.files_skipped += 1
            print(f"SKIP read error: {english_file}")
            continue

        russian_text, header_replaced = _replace_english_header_with_russian(english_text)
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

        russian_file.parent.mkdir(parents=True, exist_ok=True)
        russian_file.write_text(russian_text, encoding="utf-8-sig")

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
