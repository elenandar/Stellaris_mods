#!/usr/bin/env python3
"""Apply masked translations back into Russian Stellaris localisation files."""

from __future__ import annotations

import argparse
import re
from collections import Counter
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


PLACEHOLDER_RE = re.compile(r"__PROT_[0-9]{4}__")


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


def _record_token_map(record: dict) -> dict[str, str]:
    token_map = record.get("token_map")
    if isinstance(token_map, dict):
        return {str(k): str(v) for k, v in token_map.items()}

    occurrences = _todo_occurrences(record)
    if occurrences and isinstance(occurrences[0], dict):
        occ_map = occurrences[0].get("token_map", {})
        if isinstance(occ_map, dict):
            return {str(k): str(v) for k, v in occ_map.items()}

    return {}


def _record_key(record: dict) -> str:
    key = record.get("key")
    if isinstance(key, str) and key:
        return key

    occurrences = _todo_occurrences(record)
    if occurrences and isinstance(occurrences[0], dict):
        return str(occurrences[0].get("key", ""))
    return ""


def _record_file(record: dict) -> str:
    file_value = record.get("file")
    if isinstance(file_value, str) and file_value:
        return file_value

    occurrences = _todo_occurrences(record)
    if occurrences and isinstance(occurrences[0], dict):
        return str(occurrences[0].get("file", ""))
    return ""


def _count_placeholders(value: str) -> Counter[str]:
    return Counter(PLACEHOLDER_RE.findall(value))


def _validate_masked_translation(record: dict, masked_translation: str) -> list[str]:
    errors: list[str] = []

    token_map = _record_token_map(record)
    expected_counts = _count_placeholders(str(record.get("masked_source", "")))
    if not expected_counts and token_map:
        # Backward compatibility for TODO rows without masked_source.
        expected_counts = Counter({placeholder: 1 for placeholder in token_map})

    actual_counts = _count_placeholders(masked_translation)

    for placeholder, expected_count in expected_counts.items():
        actual_count = actual_counts.get(placeholder, 0)
        if actual_count != expected_count:
            if actual_count == 0:
                errors.append(
                    f"required placeholder {placeholder!r} is missing in masked translation"
                )
            else:
                errors.append(
                    f"placeholder {placeholder!r} count mismatch: expected {expected_count}, found {actual_count}"
                )

    for placeholder in token_map:
        if placeholder not in expected_counts:
            actual_count = actual_counts.get(placeholder, 0)
            if actual_count != 1:
                errors.append(
                    f"placeholder {placeholder!r} count mismatch: expected 1, found {actual_count}"
                )

    for placeholder, actual_count in actual_counts.items():
        if placeholder not in token_map:
            errors.append(
                f"unknown placeholder {placeholder!r} found in masked translation (count={actual_count})"
            )

    restored = restore_masked_tokens(masked_translation, token_map)
    unresolved = sorted(set(PLACEHOLDER_RE.findall(restored)))
    if unresolved:
        errors.append(
            "unresolved placeholders remain after restore: " + ", ".join(unresolved)
        )

    return errors


def _cache_error(
    cache: TranslationCache | None,
    record: dict,
    masked_translation: str,
    model_name: str,
    glossary_version: str,
    error_message: str,
) -> None:
    if cache is None:
        return

    cache.save_translation(
        source_text=str(record.get("source", "")),
        masked_source=str(record.get("masked_source", "")),
        translated_masked_text=masked_translation,
        restored_translation="",
        model_name=model_name,
        glossary_version=glossary_version,
        status="error",
        error_message=error_message,
    )


def apply_translations(
    todo_records: list[dict],
    translations: list[dict],
    russian_root: Path,
    dry_run: bool = False,
    cache: TranslationCache | None = None,
    model_name: str = "",
    glossary_version: str = "",
) -> tuple[int, int, int, list[str]]:
    """Apply translations and return (files_updated, values_updated, missing_ids, validation_errors)."""
    todo_by_id = {str(record.get("id", "")): record for record in todo_records}

    unknown_ids = [
        str(item.get("id")) for item in translations if str(item.get("id")) not in todo_by_id
    ]
    if unknown_ids:
        preview = ", ".join(unknown_ids[:5])
        raise ValueError(f"Translations contain unknown id(s) not present in TODO: {preview}")

    translations_by_id: dict[str, str] = {}
    for item in translations:
        item_id = str(item.get("id", ""))
        if not item_id:
            continue
        translations_by_id[item_id] = str(item.get("translation", ""))

    replacements_by_file: dict[str, dict[str, str]] = {}
    missing_translation_ids = 0
    validation_errors: list[str] = []

    for todo_id, record in todo_by_id.items():
        if todo_id not in translations_by_id:
            missing_translation_ids += 1
            continue

        masked_translation = translations_by_id[todo_id]
        key_for_error = _record_key(record)
        file_for_error = _record_file(record)

        entry_errors = _validate_masked_translation(record, masked_translation)
        if entry_errors:
            joined = "; ".join(entry_errors)
            error_line = (
                f"id={todo_id} key={key_for_error or '<unknown>'} "
                f"file={file_for_error or '<unknown>'}: {joined}"
            )
            validation_errors.append(error_line)
            print(f"ERROR: {error_line}")
            _cache_error(
                cache=cache,
                record=record,
                masked_translation=masked_translation,
                model_name=model_name,
                glossary_version=glossary_version,
                error_message=error_line,
            )
            continue

        occurrence_failed = False
        unit_replacements: dict[str, dict[str, str]] = {}
        for occurrence in _todo_occurrences(record):
            file_rel = occurrence.get("file")
            key = occurrence.get("key")
            token_map = occurrence.get("token_map")

            if not isinstance(token_map, dict):
                token_map = _record_token_map(record)

            if not file_rel or not key:
                continue

            restored = restore_masked_tokens(masked_translation, token_map)
            unresolved_after_restore = sorted(set(PLACEHOLDER_RE.findall(restored)))
            if unresolved_after_restore:
                error_line = (
                    f"id={todo_id} key={key} file={file_rel}: unresolved placeholders remain "
                    f"after restore: {', '.join(unresolved_after_restore)}"
                )
                validation_errors.append(error_line)
                print(f"ERROR: {error_line}")
                _cache_error(
                    cache=cache,
                    record=record,
                    masked_translation=masked_translation,
                    model_name=model_name,
                    glossary_version=glossary_version,
                    error_message=error_line,
                )
                occurrence_failed = True
                break

            safe_value = escape_localisation_value(restored)
            unit_replacements.setdefault(str(file_rel), {})[str(key)] = safe_value

        if occurrence_failed:
            continue

        for file_rel, replacements in unit_replacements.items():
            replacements_by_file.setdefault(file_rel, {}).update(replacements)

        if cache is not None:
            first_occurrence = _todo_occurrences(record)[0]
            first_token_map = first_occurrence.get("token_map", {})
            if not isinstance(first_token_map, dict):
                first_token_map = _record_token_map(record)
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

    return files_updated, values_updated, missing_translation_ids, validation_errors


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
        files_updated, values_updated, missing_translation_ids, validation_errors = apply_translations(
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
    print(f"Placeholder validation errors: {len(validation_errors)}")
    if args.dry_run:
        print("DRY-RUN mode: no files were written.")
    print("Recommendation: run validator after apply.")
    print("python tools/stellaris_loc_validate.py --fresh-root <fresh_mod> --russian-root <output_mod>")

    if validation_errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
