#!/usr/bin/env python3
"""Extract translation TODO items from fresh English and Russian skeleton files."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

try:
    from stellaris_loc_common import (
        build_stable_todo_id,
        dump_jsonl,
        english_to_russian_relative_path,
        is_technical_only_value,
        mask_protected_tokens,
        parse_localisation_file,
    )
    from stellaris_loc_scan import find_english_localisation_files
    from stellaris_loc_translation_cache import TranslationCache
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_common import (
        build_stable_todo_id,
        dump_jsonl,
        english_to_russian_relative_path,
        is_technical_only_value,
        mask_protected_tokens,
        parse_localisation_file,
    )
    from tools.stellaris_loc_scan import find_english_localisation_files
    from tools.stellaris_loc_translation_cache import TranslationCache


@dataclass
class TodoSummary:
    english_files: int = 0
    russian_files_missing: int = 0
    translated_already: int = 0
    technical_only_skipped: int = 0
    total_occurrences: int = 0
    unique_units: int = 0


def _entry_requires_translation(english_value: str, russian_value: str) -> bool:
    if russian_value == english_value:
        return True
    if russian_value.strip() == "":
        return True
    return False


def _build_occurrence(file_rel: Path, entry, token_map: dict[str, str]) -> dict:
    return {
        "file": str(file_rel),
        "key": entry.key,
        "line": entry.line,
        "entry_index": entry.entry_index,
        "key_occurrence_index": entry.key_occurrence_index,
        "token_map": token_map,
    }


def build_todo_records(
    fresh_root: Path,
    russian_root: Path,
    cache: TranslationCache | None = None,
) -> tuple[list[dict], TodoSummary]:
    summary = TodoSummary()
    english_files = find_english_localisation_files(fresh_root)
    summary.english_files = len(english_files)

    records_by_id: dict[str, dict] = {}
    ordered_ids: list[str] = []

    for english_file in english_files:
        english_rel = english_file.relative_to(fresh_root)
        russian_rel = english_to_russian_relative_path(english_rel)
        russian_file = russian_root / russian_rel

        if not russian_file.exists():
            summary.russian_files_missing += 1
            continue

        english_parsed = parse_localisation_file(english_file, expected_header="l_english:")
        russian_parsed = parse_localisation_file(russian_file, expected_header="l_russian:")

        pair_count = min(len(english_parsed.entries), len(russian_parsed.entries))

        for idx in range(pair_count):
            english_entry = english_parsed.entries[idx]
            russian_entry = russian_parsed.entries[idx]

            if english_entry.key != russian_entry.key:
                continue

            if is_technical_only_value(english_entry.value):
                summary.technical_only_skipped += 1
                continue

            if not _entry_requires_translation(english_entry.value, russian_entry.value):
                summary.translated_already += 1
                continue

            masked_source, token_map = mask_protected_tokens(english_entry.value)
            unit_id = build_stable_todo_id(masked_source)
            occurrence = _build_occurrence(
                file_rel=russian_rel,
                entry=russian_entry,
                token_map=token_map,
            )

            if unit_id not in records_by_id:
                records_by_id[unit_id] = {
                    "id": unit_id,
                    "file": str(russian_rel),
                    "key": russian_entry.key,
                    "line": russian_entry.line,
                    "entry_index": russian_entry.entry_index,
                    "key_occurrence_index": russian_entry.key_occurrence_index,
                    "source": english_entry.value,
                    "masked_source": masked_source,
                    "token_map": token_map,
                    "occurrences": [occurrence],
                }
                ordered_ids.append(unit_id)

                if cache is not None:
                    cache.upsert_source(
                        source_text=english_entry.value,
                        masked_source=masked_source,
                        status="pending",
                    )
            else:
                records_by_id[unit_id]["occurrences"].append(occurrence)

            summary.total_occurrences += 1

    records = [records_by_id[unit_id] for unit_id in ordered_ids]
    summary.unique_units = len(records)
    return records, summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract translatable localisation values into TODO JSONL.",
    )
    parser.add_argument("--fresh-root", required=True, help="Path to fresh mod root.")
    parser.add_argument("--russian-root", required=True, help="Path to Russian output root.")
    parser.add_argument("--out", required=True, help="Path to output TODO JSONL file.")
    parser.add_argument("--cache-db", help="Optional SQLite cache path.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview extraction results without writing JSONL.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    fresh_root = Path(args.fresh_root).expanduser().resolve()
    russian_root = Path(args.russian_root).expanduser().resolve()
    out_path = Path(args.out).expanduser().resolve()

    if not fresh_root.exists() or not fresh_root.is_dir():
        parser.error(f"Fresh root is not an existing directory: {fresh_root}")

    cache = None
    if args.cache_db:
        cache = TranslationCache(Path(args.cache_db).expanduser().resolve())
        cache.init_db()

    records, summary = build_todo_records(
        fresh_root=fresh_root,
        russian_root=russian_root,
        cache=cache,
    )

    dump_jsonl(out_path, records, dry_run=args.dry_run)

    print("TODO extraction summary")
    print("=======================")
    print(f"English files scanned: {summary.english_files}")
    print(f"Missing Russian files: {summary.russian_files_missing}")
    print(f"Technical-only skipped: {summary.technical_only_skipped}")
    print(f"Already translated skipped: {summary.translated_already}")
    print(f"Total occurrences: {summary.total_occurrences}")
    print(f"Unique translation units: {summary.unique_units}")
    if args.dry_run:
        print(f"DRY-RUN output path: {out_path}")
    else:
        print(f"Wrote TODO JSONL: {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
