#!/usr/bin/env python3
"""Translate a collection of Stellaris mods sequentially."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

try:
    from stellaris_loc_common import dump_json
    from stellaris_loc_llm_client import add_llm_cli_args
    from stellaris_loc_translate_mod import translate_mod_workflow
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_common import dump_json
    from tools.stellaris_loc_llm_client import add_llm_cli_args
    from tools.stellaris_loc_translate_mod import translate_mod_workflow


def translate_collection_workflow(
    *,
    fresh_root: Path,
    output_root: Path,
    work_root: Path,
    cache_db: Path | None,
    provider: str,
    base_url: str | None,
    api_key: str | None,
    model: str | None,
    batch_size: int,
    workers: int,
    glossary_version: str,
    temperature: float,
    timeout: int,
    max_retries: int,
    resume: bool = False,
    force: bool = False,
    dry_run: bool = False,
    limit_batches: int | None = None,
    translator: Callable[..., list[dict]] | None = None,
) -> dict:
    del workers

    summary: dict = {
        "fresh_root": str(fresh_root),
        "output_root": str(output_root),
        "work_root": str(work_root),
        "mods": [],
        "ok": 0,
        "failed": 0,
    }

    mod_dirs = sorted([path for path in fresh_root.iterdir() if path.is_dir()])
    for mod_dir in mod_dirs:
        russian_root = output_root / mod_dir.name
        work_dir = work_root / mod_dir.name
        try:
            report = translate_mod_workflow(
                fresh_root=mod_dir,
                russian_root=russian_root,
                work_dir=work_dir,
                cache_db=cache_db,
                provider=provider,
                base_url=base_url,
                api_key=api_key,
                model=model,
                batch_size=batch_size,
                glossary_version=glossary_version,
                temperature=temperature,
                timeout=timeout,
                max_retries=max_retries,
                skip_rebuild=False,
                resume=resume,
                force=force,
                dry_run=dry_run,
                limit_batches=limit_batches,
                translator=translator,
            )
        except Exception as exc:
            report = {"status": "failed_exception", "mod": mod_dir.name, "error": str(exc)}

        summary["mods"].append({"mod": mod_dir.name, "report": report})
        if report.get("status") == "ok":
            summary["ok"] += 1
        else:
            summary["failed"] += 1

    dump_json(work_root / "collection_report.json", summary, dry_run=dry_run, pretty=True)
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Translate all fresh mods in a collection.")
    parser.add_argument("--fresh-root", required=True, help="Root directory containing fresh mod subdirectories.")
    parser.add_argument("--output-root", required=True, help="Root directory for Russian output mod trees.")
    parser.add_argument("--work-root", required=True, help="Root directory for per-mod work directories.")
    parser.add_argument("--cache-db", help="Optional SQLite cache path.")
    parser.add_argument("--provider", default="openai-compatible", help="Translation provider.")
    parser.add_argument("--batch-size", type=int, default=20, help="Batch size.")
    parser.add_argument("--workers", type=int, default=1, help="Reserved worker count option.")
    parser.add_argument("--glossary-version", required=True, help="Glossary version label.")
    parser.add_argument("--resume", action="store_true", help="Reuse existing per-mod work files if present.")
    parser.add_argument("--force", action="store_true", help="Force regeneration/retranslation of existing outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Plan work without writing outputs.")
    parser.add_argument("--limit-batches", type=int, help="Translate only first N batches per mod.")
    add_llm_cli_args(parser)
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        summary = translate_collection_workflow(
            fresh_root=Path(args.fresh_root).expanduser().resolve(),
            output_root=Path(args.output_root).expanduser().resolve(),
            work_root=Path(args.work_root).expanduser().resolve(),
            cache_db=Path(args.cache_db).expanduser().resolve() if args.cache_db else None,
            provider=args.provider,
            base_url=args.base_url,
            api_key=args.api_key,
            model=args.model,
            batch_size=args.batch_size,
            workers=args.workers,
            glossary_version=args.glossary_version,
            temperature=args.temperature,
            timeout=args.timeout,
            max_retries=args.max_retries,
            resume=args.resume,
            force=args.force,
            dry_run=args.dry_run,
            limit_batches=args.limit_batches,
        )
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print("Collection translation summary")
    print("==============================")
    print(f"Mods OK: {summary['ok']}")
    print(f"Mods failed: {summary['failed']}")
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
