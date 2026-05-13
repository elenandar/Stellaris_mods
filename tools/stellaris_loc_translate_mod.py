#!/usr/bin/env python3
"""Translate one Stellaris mod end-to-end using the batch pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

try:
    from stellaris_loc_apply_translations import apply_translation_sources
    from stellaris_loc_batch_format import build_batch_items, write_batches
    from stellaris_loc_common import dump_json, dump_jsonl, load_jsonl
    from stellaris_loc_extract_todo import build_todo_records
    from stellaris_loc_llm_client import add_llm_cli_args
    from stellaris_loc_rebuild_skeleton import rebuild_skeletons
    from stellaris_loc_scan import find_english_localisation_files
    from stellaris_loc_translate_batches import translate_batches_in_directory
    from stellaris_loc_validate import validate_roots
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_apply_translations import apply_translation_sources
    from tools.stellaris_loc_batch_format import build_batch_items, write_batches
    from tools.stellaris_loc_common import dump_json, dump_jsonl, load_jsonl
    from tools.stellaris_loc_extract_todo import build_todo_records
    from tools.stellaris_loc_llm_client import add_llm_cli_args
    from tools.stellaris_loc_rebuild_skeleton import rebuild_skeletons
    from tools.stellaris_loc_scan import find_english_localisation_files
    from tools.stellaris_loc_translate_batches import translate_batches_in_directory
    from tools.stellaris_loc_validate import validate_roots


def translate_mod_workflow(
    *,
    fresh_root: Path,
    russian_root: Path,
    work_dir: Path,
    cache_db: Path | None,
    provider: str,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    batch_size: int,
    glossary_version: str,
    temperature: float,
    timeout: int,
    max_retries: int,
    skip_rebuild: bool = False,
    resume: bool = False,
    force: bool = False,
    dry_run: bool = False,
    limit_batches: int | None = None,
    translator: Callable[..., list[dict]] | None = None,
) -> dict:
    report: dict = {
        "fresh_root": str(fresh_root),
        "russian_root": str(russian_root),
        "work_dir": str(work_dir),
        "status": "started",
        "english_files_found": 0,
        "skeleton": {},
        "skeleton_validation": {},
        "todo": {},
        "batch_format": {},
        "translation": {},
        "apply": {},
        "final_validation": {},
    }

    english_files = find_english_localisation_files(fresh_root)
    report["english_files_found"] = len(english_files)

    if not skip_rebuild:
        rebuild_summary = rebuild_skeletons(fresh_root=fresh_root, russian_root=russian_root, dry_run=dry_run)
        report["skeleton"] = {
            "english_files_found": rebuild_summary.english_files_found,
            "files_created": rebuild_summary.files_created,
            "files_updated": rebuild_summary.files_updated,
            "files_skipped": rebuild_summary.files_skipped,
            "dry_run_actions": rebuild_summary.dry_run_actions,
        }
    else:
        report["skeleton"] = {"skipped": True}

    skeleton_results = validate_roots(fresh_root=fresh_root, russian_root=russian_root)
    skeleton_error_count = sum(len(result.errors) for result in skeleton_results)
    skeleton_warning_count = sum(len(result.source_warnings) for result in skeleton_results)
    report["skeleton_validation"] = {
        "pairs_checked": len(skeleton_results),
        "errors": skeleton_error_count,
        "source_warnings": skeleton_warning_count,
    }

    if skeleton_error_count:
        report["status"] = "failed_skeleton_validation"
        dump_json(work_dir / "report.json", report, dry_run=dry_run, pretty=True)
        return report

    todo_path = work_dir / "todo.jsonl"
    if resume and todo_path.exists() and not force:
        todo_records = load_jsonl(todo_path)
        report["todo"] = {"reused": True, "unique_units": len(todo_records)}
    else:
        todo_records, todo_summary = build_todo_records(
            fresh_root=fresh_root,
            russian_root=russian_root,
            cache=None,
        )
        report["todo"] = {
            "english_files": todo_summary.english_files,
            "russian_files_missing": todo_summary.russian_files_missing,
            "translated_already": todo_summary.translated_already,
            "technical_only_skipped": todo_summary.technical_only_skipped,
            "total_occurrences": todo_summary.total_occurrences,
            "unique_units": todo_summary.unique_units,
        }
        dump_jsonl(todo_path, todo_records, dry_run=dry_run)

    batch_dir = work_dir / "batches"
    if resume and batch_dir.exists() and list(batch_dir.glob("batch_*.json")) and not force:
        batch_files = sorted(batch_dir.glob("batch_*.json"))
        report["batch_format"] = {"reused": True, "batch_files": len(batch_files)}
    else:
        batch_items = build_batch_items(todo_records)
        batch_files = write_batches(batch_items, batch_size=batch_size, out_dir=batch_dir, dry_run=dry_run)
        report["batch_format"] = {
            "batch_items": len(batch_items),
            "batch_files": len(batch_files),
        }

    translations_dir = work_dir / "translations"
    translation_summary = translate_batches_in_directory(
        batches_dir=batch_dir,
        translations_dir=translations_dir,
        provider=provider,
        base_url=base_url,
        api_key=api_key,
        model=model,
        glossary_version=glossary_version,
        temperature=temperature,
        timeout=timeout,
        max_retries=max_retries,
        cache_db=cache_db,
        dry_run=dry_run,
        limit=limit_batches,
        force=force,
        translator=translator,
    )
    report["translation"] = {
        "batches_seen": translation_summary.batches_seen,
        "batches_translated": translation_summary.batches_translated,
        "batches_skipped": translation_summary.batches_skipped,
        "batches_failed": translation_summary.batches_failed,
        "items_written": translation_summary.items_written,
    }

    if translation_summary.batches_failed:
        report["status"] = "failed_translation"
        dump_json(work_dir / "report.json", report, dry_run=dry_run, pretty=True)
        return report

    files_updated, values_updated, missing_ids, apply_errors = apply_translation_sources(
        todo_records=todo_records,
        translations_path=None,
        translations_dir=translations_dir,
        russian_root=russian_root,
        dry_run=dry_run,
        cache_db=cache_db,
        model_name=model or "",
        glossary_version=glossary_version,
    )
    report["apply"] = {
        "files_updated": files_updated,
        "values_updated": values_updated,
        "missing_translation_ids": missing_ids,
        "errors": len(apply_errors),
    }

    if apply_errors:
        report["status"] = "failed_apply"
        dump_json(work_dir / "report.json", report, dry_run=dry_run, pretty=True)
        return report

    final_results = validate_roots(fresh_root=fresh_root, russian_root=russian_root)
    final_error_count = sum(len(result.errors) for result in final_results)
    final_warning_count = sum(len(result.source_warnings) for result in final_results)
    report["final_validation"] = {
        "pairs_checked": len(final_results),
        "errors": final_error_count,
        "source_warnings": final_warning_count,
    }
    report["status"] = "ok" if final_error_count == 0 else "failed_final_validation"

    dump_json(work_dir / "report.json", report, dry_run=dry_run, pretty=True)
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Translate one Stellaris mod end-to-end.")
    parser.add_argument("--fresh-root", required=True, help="Fresh mod root.")
    parser.add_argument("--russian-root", required=True, help="Russian output mod root.")
    parser.add_argument("--work-dir", required=True, help="Working directory for todo, batches, translations, and report.")
    parser.add_argument("--cache-db", help="Optional SQLite cache path.")
    parser.add_argument("--provider", default="openai-compatible", help="Translation provider.")
    parser.add_argument("--batch-size", type=int, default=20, help="Batch size.")
    parser.add_argument("--glossary-version", required=True, help="Glossary version label.")
    parser.add_argument("--skip-rebuild", action="store_true", help="Skip skeleton rebuild step.")
    parser.add_argument("--resume", action="store_true", help="Reuse existing work files if present.")
    parser.add_argument("--force", action="store_true", help="Force regeneration/retranslation of existing outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Plan work without writing outputs.")
    parser.add_argument("--limit-batches", type=int, help="Translate only the first N batches.")
    add_llm_cli_args(parser)
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        report = translate_mod_workflow(
            fresh_root=Path(args.fresh_root).expanduser().resolve(),
            russian_root=Path(args.russian_root).expanduser().resolve(),
            work_dir=Path(args.work_dir).expanduser().resolve(),
            cache_db=Path(args.cache_db).expanduser().resolve() if args.cache_db else None,
            provider=args.provider,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            batch_size=args.batch_size,
            glossary_version=args.glossary_version,
            temperature=args.temperature,
            timeout=args.timeout,
            max_retries=args.max_retries,
            skip_rebuild=args.skip_rebuild,
            resume=args.resume,
            force=args.force,
            dry_run=args.dry_run,
            limit_batches=args.limit_batches,
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print("Mod translation status:", report.get("status", "unknown"))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
