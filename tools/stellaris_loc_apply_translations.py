#!/usr/bin/env python3
"""Apply masked translations back into Russian Stellaris localisation files."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from stellaris_loc_common import (
        apply_value_replacements,
        escape_localisation_value,
        load_json,
        load_jsonl,
        read_utf8,
        restore_masked_tokens,
        write_utf8_bom,
    )
    from stellaris_loc_translation_cache import TranslationCache
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_common import (
        apply_value_replacements,
        escape_localisation_value,
        load_json,
        load_jsonl,
        read_utf8,
        restore_masked_tokens,
        write_utf8_bom,
    )
    from tools.stellaris_loc_translation_cache import TranslationCache


def _load_translations(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        return load_jsonl(path)

    payload = load_json(path)
    if isinstance(payload, list):
        return payload
    raise ValueError("Translation input must be a JSON array or JSONL rows.")


def _todo_occurrences(record: dict) -> list[dict]:
    occurrences = record.get("occurrences")
    if isinstance(occurrences, list) and occurrences:
        return occurrences

    return [
        {
            "file": record.get("file"),
            "key": record.get("key"),
            "line": record.get("line"),
            "token_map": record.get("token_map", {}),
        }
    ]


def apply_translations(
    todo_records: list[dict],
    translations: list[dict],
    russian_root: Path,
    dry_run: bool = False,
    cache: TranslationCache | None = None,
    model_name: str = "",
    glossary_version: str = "",
) -> tuple[int, int, int]:
    """Apply translations and return (files_updated, values_updated, missing_translation_ids)."""
    todo_by_id = {record["id"]: record for record in todo_records}
    unknown_ids = [item.get("id") for item in translations if item.get("id") not in todo_by_id]
    if unknown_ids:
        preview = ", ".join(str(value) for value in unknown_ids[:5])
        raise ValueError(f"Translations contain unknown id(s) not present in TODO: {preview}")

    translations_by_id: dict[str, str] = {}
    for item in translations:
        item_id = item.get("id")
        if not item_id:
            continue
        translations_by_id[item_id] = str(item.get("translation", ""))

    replacements_by_file: dict[str, dict[str, str]] = {}
    missing_translation_ids = 0

    for todo_id, record in todo_by_id.items():
        if todo_id not in translations_by_id:
            missing_translation_ids += 1
            continue

        masked_translation = translations_by_id[todo_id]
        for occurrence in _todo_occurrences(record):
            file_rel = occurrence.get("file")
            key = occurrence.get("key")
            if not file_rel or not key:
                continue

            token_map = occurrence.get("token_map", {})
            restored = restore_masked_tokens(masked_translation, token_map)
            safe_value = escape_localisation_value(restored)

            replacements_by_file.setdefault(str(file_rel), {})[str(key)] = safe_value

        if cache is not None:
            first_occurrence = _todo_occurrences(record)[0]
            first_token_map = first_occurrence.get("token_map", {})
            restored_for_cache = restore_masked_tokens(masked_translation, first_token_map)
            cache.save_translation(
                source_text=str(record.get("source", "")),
                masked_source=str(record.get("masked_source", "")),
                translated_masked_text=masked_translation,
                restored_translation=restored_for_cache,
                model_name=model_name,
                glossary_version=glossary_version,
                status="applied",
                error_message=None,
            )

    files_updated = 0
    values_updated = 0

    for file_rel, replacements in replacements_by_file.items():
        file_path = russian_root / file_rel
        if not file_path.exists():
            print(f"SKIP missing file: {file_path}")
            continue

        text, _, read_error = read_utf8(file_path)
        if read_error is not None:
            print(f"SKIP read error: {file_path} ({read_error})")
            continue

        new_text, replaced_keys = apply_value_replacements(text, replacements)
        if not replaced_keys:
            continue

        if new_text != text:
            write_utf8_bom(file_path, new_text, dry_run=dry_run)
            files_updated += 1
            values_updated += len(replaced_keys)

    return files_updated, values_updated, missing_translation_ids


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply translated masked text to Russian localisation files.",
    )
    parser.add_argument("--todo", required=True, help="Path to TODO JSONL.")
    parser.add_argument("--translations", required=True, help="Path to translations JSON/JSONL.")
    parser.add_argument("--russian-root", required=True, help="Path to Russian output mod root.")
    parser.add_argument("--cache-db", help="Optional SQLite cache path.")
    parser.add_argument("--model", default="", help="Model name for cache metadata.")
    parser.add_argument("--glossary-version", default="", help="Glossary version tag for cache metadata.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview file updates without writing changes.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    todo_path = Path(args.todo).expanduser().resolve()
    translations_path = Path(args.translations).expanduser().resolve()
    russian_root = Path(args.russian_root).expanduser().resolve()

    if not russian_root.exists() or not russian_root.is_dir():
        parser.error(f"Russian root is not an existing directory: {russian_root}")

    todo_records = load_jsonl(todo_path)
    translations = _load_translations(translations_path)

    cache = None
    if args.cache_db:
        cache = TranslationCache(Path(args.cache_db).expanduser().resolve())
        cache.init_db()

    try:
        files_updated, values_updated, missing_translation_ids = apply_translations(
            todo_records=todo_records,
            translations=translations,
            russian_root=russian_root,
            dry_run=args.dry_run,
            cache=cache,
            model_name=args.model,
            glossary_version=args.glossary_version,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("Apply summary")
    print("=============")
    print(f"Files updated: {files_updated}")
    print(f"Values updated: {values_updated}")
    print(f"TODO ids without translation: {missing_translation_ids}")
    if args.dry_run:
        print("DRY-RUN mode: no files were written.")
    print("Recommendation: run validator after apply.")
    print("python tools/stellaris_loc_validate.py --fresh-root <fresh_mod> --russian-root <output_mod>")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
