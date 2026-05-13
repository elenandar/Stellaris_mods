#!/usr/bin/env python3
"""Automatically translate Stellaris batch JSON files with an LLM API."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

try:
    from stellaris_loc_common import dump_json, load_json
    from stellaris_loc_llm_client import add_llm_cli_args, resolve_llm_config, translate_batch_with_llm
    from stellaris_loc_translation_cache import TranslationCache
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_common import dump_json, load_json
    from tools.stellaris_loc_llm_client import (
        add_llm_cli_args,
        resolve_llm_config,
        translate_batch_with_llm,
    )
    from tools.stellaris_loc_translation_cache import TranslationCache


PLACEHOLDER_RE = re.compile(r"__PROT_[0-9]{4}__")
UNICODE_QUOTES_RE = re.compile(r"[\u00ab\u00bb\u201c\u201d\u201e]")
FORBIDDEN_PHRASES = (
    "TODO",
    "TRUNCATED",
    "FIXME",
    "остальное аналогично",
)


@dataclass
class BatchTranslationSummary:
    batches_seen: int = 0
    batches_translated: int = 0
    batches_skipped: int = 0
    batches_failed: int = 0
    items_written: int = 0
    failed_reports: list[dict] | None = None

    def __post_init__(self) -> None:
        if self.failed_reports is None:
            self.failed_reports = []


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_required_context_docs(repo_root: Path) -> dict[str, str]:
    docs = {}
    for name in ("glossary_ru.md", "translation_rules.md", "known_issues.md"):
        path = repo_root / name
        docs[name] = path.read_text(encoding="utf-8") if path.exists() else ""
    return docs


def build_system_prompt(context_docs: dict[str, str]) -> str:
    return (
        "You are translating Stellaris localisation batch items from English to Russian.\n"
        "Return only a valid JSON array. No markdown. No explanations.\n"
        "Output schema:\n"
        "[\n  {\"id\": \"...\", \"translation\": \"...\"}\n]\n"
        "Translate only the field text. Use key, file, source, entry_index, and key_occurrence_index only as context.\n"
        "Preserve placeholders like __PROT_0000__ exactly, with identical counts.\n"
        "Do not invent, rename, remove, or reorder placeholders.\n"
        "Do not output markdown fences.\n"
        "Do not use Unicode quotes.\n"
        "Do not create multiline strings.\n"
        "Do not output TODO, TRUNCATED, FIXME, or остальное аналогично.\n"
        "Do not translate catalogue names such as P4T-257-a, PXT-947, P57J-657-b, XJ-9, 3V-0L.\n"
        "Proper names may be localized to Cyrillic: Antares Prime -> Антарес Прайм, Ancient Antares -> Древний Антарес, Altair Prime -> Альтаир Прайм.\n"
        "Localisation keys must never be translated.\n\n"
        "Reference documents follow.\n\n"
        f"[glossary_ru.md]\n{context_docs['glossary_ru.md']}\n\n"
        f"[translation_rules.md]\n{context_docs['translation_rules.md']}\n\n"
        f"[known_issues.md]\n{context_docs['known_issues.md']}"
    )


def build_user_prompt(batch_items: list[dict]) -> str:
    batch_json = json.dumps(batch_items, ensure_ascii=False, indent=2)
    return (
        "Translate the following batch items.\n"
        "Return only a valid JSON array with objects of the form: \n"
        "{\"id\": \"...\", \"translation\": \"...\"}\n"
        "Do not include key, file, source, entry_index, or key_occurrence_index in the response.\n"
        "Preserve __PROT_0000__-style placeholders exactly.\n\n"
        f"Batch items:\n{batch_json}"
    )


def validate_translation_response(batch_name: str, batch_items: list[dict], translations: list[dict]) -> list[str]:
    errors: list[str] = []

    if not isinstance(translations, list):
        return [f"{batch_name}: translation payload is not a JSON array"]

    expected_ids = [str(item.get("id", "")) for item in batch_items]
    actual_ids: list[str] = []
    id_to_item = {str(item.get("id", "")): item for item in batch_items}

    for index, item in enumerate(translations):
        if not isinstance(item, dict):
            errors.append(f"{batch_name}: translation item at index {index} is not an object")
            continue
        item_id = item.get("id")
        translation = item.get("translation")
        if not isinstance(item_id, str):
            errors.append(f"{batch_name}: translation item at index {index} has invalid id")
            continue
        if not isinstance(translation, str):
            errors.append(f"{batch_name}: translation item id={item_id} has invalid translation")
            continue

        actual_ids.append(item_id)

        if "```" in translation:
            errors.append(f"{batch_name}: id={item_id} contains markdown fence")

        if "\n" in translation or "\r" in translation:
            errors.append(f"{batch_name}: id={item_id} contains multiline translation")

        if UNICODE_QUOTES_RE.search(translation):
            errors.append(f"{batch_name}: id={item_id} contains Unicode quote characters")

        upper_translation = translation.upper()
        for phrase in FORBIDDEN_PHRASES:
            if phrase.upper() in upper_translation:
                errors.append(f"{batch_name}: id={item_id} contains forbidden phrase {phrase!r}")

        source_item = id_to_item.get(item_id)
        if source_item is None:
            continue

        expected_placeholders = PLACEHOLDER_RE.findall(str(source_item.get("text", "")))
        actual_placeholders = PLACEHOLDER_RE.findall(translation)
        if Counter(expected_placeholders) != Counter(actual_placeholders):
            errors.append(
                f"{batch_name}: id={item_id} placeholder mismatch: expected {Counter(expected_placeholders)}, "
                f"actual {Counter(actual_placeholders)}"
            )

    expected_counter = Counter(expected_ids)
    actual_counter = Counter(actual_ids)
    for item_id, expected_count in expected_counter.items():
        actual_count = actual_counter.get(item_id, 0)
        if actual_count < expected_count:
            errors.append(
                f"{batch_name}: missing id {item_id!r}: expected {expected_count}, found {actual_count}"
            )
    for item_id, actual_count in actual_counter.items():
        expected_count = expected_counter.get(item_id, 0)
        if actual_count > expected_count:
            errors.append(
                f"{batch_name}: extra id {item_id!r}: expected {expected_count}, found {actual_count}"
            )

    return errors


def _valid_existing_translation_file(batch_items: list[dict], path: Path) -> bool:
    try:
        payload = load_json(path)
    except Exception:
        return False
    return not validate_translation_response(path.name, batch_items, payload)


def _normalize_translations_to_batch_order(batch_items: list[dict], translations: list[dict]) -> list[dict]:
    translation_map = {str(item["id"]): item for item in translations if isinstance(item, dict) and "id" in item}
    ordered: list[dict] = []
    for batch_item in batch_items:
        item_id = str(batch_item["id"])
        if item_id not in translation_map:
            continue
        ordered.append(
            {
                "id": item_id,
                "translation": str(translation_map[item_id]["translation"]),
            }
        )
    return ordered


def _cached_translations(cache: TranslationCache | None, batch_items: list[dict]) -> tuple[list[dict], list[dict]]:
    cached: list[dict] = []
    pending: list[dict] = []

    for item in batch_items:
        if cache is None:
            pending.append(item)
            continue
        record = cache.get(str(item.get("text", "")))
        if record is None or record.status not in {"translated", "applied"} or not record.translated_masked_text:
            pending.append(item)
            continue

        cached.append({"id": str(item.get("id", "")), "translation": record.translated_masked_text})

    return cached, pending


def _save_cache_entries(
    cache: TranslationCache | None,
    batch_items: list[dict],
    translations: list[dict],
    glossary_version: str,
    model_name: str,
) -> None:
    if cache is None:
        return

    translation_map = {str(item["id"]): str(item["translation"]) for item in translations}
    for batch_item in batch_items:
        item_id = str(batch_item.get("id", ""))
        if item_id not in translation_map:
            continue
        cache.save_translation(
            source_text=str(batch_item.get("source", "")),
            masked_source=str(batch_item.get("text", "")),
            translated_masked_text=translation_map[item_id],
            restored_translation=translation_map[item_id],
            model_name=model_name,
            glossary_version=glossary_version,
            status="translated",
            error_message=None,
        )


def translate_batches_in_directory(
    *,
    batches_dir: Path,
    translations_dir: Path,
    provider: str,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    glossary_version: str,
    temperature: float,
    timeout: int,
    max_retries: int,
    cache_db: Path | None = None,
    dry_run: bool = False,
    limit: int | None = None,
    force: bool = False,
    translator: Callable[..., list[dict]] | None = None,
) -> BatchTranslationSummary:
    if provider != "openai-compatible":
        raise ValueError(f"Unsupported provider: {provider}")

    resolved_base_url, resolved_api_key, resolved_model = resolve_llm_config(base_url, api_key, model)
    repo_root = _repo_root()
    context_docs = _load_required_context_docs(repo_root)
    system_prompt = build_system_prompt(context_docs)

    cache = None
    if cache_db is not None:
        cache = TranslationCache(cache_db)
        cache.init_db()

    batch_files = sorted(batches_dir.glob("batch_*.json"))
    if limit is not None:
        batch_files = batch_files[:limit]

    summary = BatchTranslationSummary(batches_seen=len(batch_files))
    failure_reports: list[dict] = []

    for batch_file in batch_files:
        translation_file = translations_dir / f"{batch_file.stem}_ru.json"
        batch_items = load_json(batch_file)

        if translation_file.exists() and not force and _valid_existing_translation_file(batch_items, translation_file):
            summary.batches_skipped += 1
            continue

        cached, pending = _cached_translations(cache, batch_items)
        success = False
        last_errors: list[str] = []

        if not pending:
            cached_errors = validate_translation_response(batch_file.name, batch_items, cached)
            if cached_errors:
                summary.batches_failed += 1
                failure_reports.append(
                    {
                        "batch": str(batch_file),
                        "translation_file": str(translation_file),
                        "errors": cached_errors,
                    }
                )
                continue
            merged = _normalize_translations_to_batch_order(batch_items, cached)
            if not dry_run:
                dump_json(translation_file, merged, dry_run=False, pretty=True)
            summary.batches_translated += 1
            summary.items_written += len(merged)
            continue

        translate_func = translator or translate_batch_with_llm
        for attempt in range(1, max_retries + 1):
            user_prompt = build_user_prompt(pending)
            try:
                llm_translations = translate_func(
                    batch_items=pending,
                    model=resolved_model,
                    base_url=resolved_base_url,
                    api_key=resolved_api_key,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    temperature=temperature,
                    timeout=timeout,
                    max_retries=max_retries,
                )
            except Exception as exc:
                last_errors = [f"{batch_file.name}: translator failure on attempt {attempt}: {exc}"]
                continue

            merged_raw = [*cached, *llm_translations]
            errors = validate_translation_response(batch_file.name, batch_items, merged_raw)
            if errors:
                last_errors = errors
                continue

            merged = _normalize_translations_to_batch_order(batch_items, merged_raw)

            if not dry_run:
                dump_json(translation_file, merged, dry_run=False, pretty=True)
            _save_cache_entries(cache, batch_items, merged, glossary_version, resolved_model)
            summary.batches_translated += 1
            summary.items_written += len(merged)
            success = True
            break

        if success:
            continue

        summary.batches_failed += 1
        failure_reports.append(
            {
                "batch": str(batch_file),
                "translation_file": str(translation_file),
                "errors": last_errors,
            }
        )

    summary.failed_reports = failure_reports

    if failure_reports and not dry_run:
        dump_json(repo_root / "reports" / "failed_batches.json", failure_reports, dry_run=False, pretty=True)

    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Automatically translate Stellaris batch JSON files.")
    parser.add_argument("--batches-dir", required=True, help="Directory containing batch_*.json files.")
    parser.add_argument("--translations-dir", required=True, help="Directory to write batch_*_ru.json files.")
    parser.add_argument("--cache-db", help="Optional SQLite cache path.")
    parser.add_argument("--provider", default="openai-compatible", help="Translation provider.")
    parser.add_argument("--glossary-version", required=True, help="Glossary version label.")
    parser.add_argument("--dry-run", action="store_true", help="Validate inputs and planned work without writing outputs.")
    parser.add_argument("--limit", type=int, help="Translate only first N batch files.")
    parser.add_argument("--force", action="store_true", help="Retranslate even if output file already exists and is valid.")
    add_llm_cli_args(parser)
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        summary = translate_batches_in_directory(
            batches_dir=Path(args.batches_dir).expanduser().resolve(),
            translations_dir=Path(args.translations_dir).expanduser().resolve(),
            provider=args.provider,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            glossary_version=args.glossary_version,
            temperature=args.temperature,
            timeout=args.timeout,
            max_retries=args.max_retries,
            cache_db=Path(args.cache_db).expanduser().resolve() if args.cache_db else None,
            dry_run=args.dry_run,
            limit=args.limit,
            force=args.force,
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print("Batch translation summary")
    print("=========================")
    print(f"Batches seen: {summary.batches_seen}")
    print(f"Batches translated: {summary.batches_translated}")
    print(f"Batches skipped: {summary.batches_skipped}")
    print(f"Batches failed: {summary.batches_failed}")
    print(f"Items written: {summary.items_written}")
    return 1 if summary.batches_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
