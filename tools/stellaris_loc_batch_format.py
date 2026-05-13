#!/usr/bin/env python3
"""Build LLM-ready translation batches from TODO JSONL records."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from stellaris_loc_common import dump_json, load_jsonl
    from stellaris_loc_translation_cache import TranslationCache
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_common import dump_json, load_jsonl
    from tools.stellaris_loc_translation_cache import TranslationCache


def build_batch_items(
    todo_records: list[dict],
    cache: TranslationCache | None = None,
    skip_cached_complete: bool = True,
) -> list[dict]:
    """Convert TODO records to compact batch items for LLM translation."""
    items: list[dict] = []
    for record in todo_records:
        masked_source = record["masked_source"]
        if cache is not None and skip_cached_complete and cache.has_completed(masked_source):
            continue

        items.append(
            {
                "id": record["id"],
                "key": record["key"],
                "text": masked_source,
            }
        )
    return items


def _chunk(items: list[dict], batch_size: int) -> list[list[dict]]:
    return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]


def write_batches(
    items: list[dict],
    batch_size: int,
    out_dir: Path,
    dry_run: bool = False,
) -> list[Path]:
    """Write JSON batches to output directory."""
    paths: list[Path] = []
    for index, chunk in enumerate(_chunk(items, batch_size), start=1):
        out_file = out_dir / f"batch_{index:03d}.json"
        dump_json(out_file, chunk, dry_run=dry_run, pretty=True)
        paths.append(out_file)
    return paths


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Format TODO JSONL into fixed-size JSON batch files for translation.",
    )
    parser.add_argument("--todo", required=True, help="Path to TODO JSONL.")
    parser.add_argument("--batch-size", required=True, type=int, help="Batch size, e.g. 100.")
    parser.add_argument("--out", required=True, help="Output batch directory.")
    parser.add_argument("--cache-db", help="Optional SQLite cache database path.")
    parser.add_argument(
        "--include-cached-complete",
        action="store_true",
        help="Include cache-complete records in output batches (default is to skip them).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview batches without writing files.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size must be > 0")

    todo_path = Path(args.todo).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    todo_records = load_jsonl(todo_path)

    cache = None
    if args.cache_db:
        cache = TranslationCache(Path(args.cache_db).expanduser().resolve())
        cache.init_db()

    items = build_batch_items(
        todo_records=todo_records,
        cache=cache,
        skip_cached_complete=not args.include_cached_complete,
    )
    batch_paths = write_batches(
        items=items,
        batch_size=args.batch_size,
        out_dir=out_dir,
        dry_run=args.dry_run,
    )

    print("Batch formatting summary")
    print("========================")
    print(f"TODO records: {len(todo_records)}")
    print(f"Batch items: {len(items)}")
    print(f"Batch files: {len(batch_paths)}")
    if args.dry_run:
        print(f"DRY-RUN output dir: {out_dir}")
    else:
        print(f"Wrote batches to: {out_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
