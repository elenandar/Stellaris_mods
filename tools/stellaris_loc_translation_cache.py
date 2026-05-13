#!/usr/bin/env python3
"""SQLite cache for Stellaris batch translation pipeline."""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CacheRecord:
    source_text: str
    masked_source: str
    translated_masked_text: str | None
    restored_translation: str | None
    model_name: str | None
    glossary_version: str | None
    updated_at: str
    status: str
    error_message: str | None


class TranslationCache:
    """Deduplicating translation cache keyed by masked source text."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS translation_cache (
                    masked_source TEXT PRIMARY KEY,
                    source_text TEXT NOT NULL,
                    translated_masked_text TEXT,
                    restored_translation TEXT,
                    model_name TEXT,
                    glossary_version TEXT,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
                """
            )

    def upsert_source(
        self,
        source_text: str,
        masked_source: str,
        status: str = "pending",
        model_name: str | None = None,
        glossary_version: str | None = None,
    ) -> None:
        """Insert source if missing and keep a fresh timestamp."""
        now = _utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO translation_cache (
                    masked_source,
                    source_text,
                    translated_masked_text,
                    restored_translation,
                    model_name,
                    glossary_version,
                    updated_at,
                    status,
                    error_message
                )
                VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, NULL)
                ON CONFLICT(masked_source) DO UPDATE SET
                    source_text=excluded.source_text,
                    updated_at=excluded.updated_at,
                    status=CASE
                        WHEN translation_cache.status IN ('translated', 'applied')
                            THEN translation_cache.status
                        ELSE excluded.status
                    END
                """,
                (
                    masked_source,
                    source_text,
                    model_name,
                    glossary_version,
                    now,
                    status,
                ),
            )

    def save_translation(
        self,
        source_text: str,
        masked_source: str,
        translated_masked_text: str,
        restored_translation: str,
        model_name: str,
        glossary_version: str,
        status: str = "translated",
        error_message: str | None = None,
    ) -> None:
        """Store translated result for masked source."""
        now = _utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO translation_cache (
                    masked_source,
                    source_text,
                    translated_masked_text,
                    restored_translation,
                    model_name,
                    glossary_version,
                    updated_at,
                    status,
                    error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(masked_source) DO UPDATE SET
                    source_text=excluded.source_text,
                    translated_masked_text=excluded.translated_masked_text,
                    restored_translation=excluded.restored_translation,
                    model_name=excluded.model_name,
                    glossary_version=excluded.glossary_version,
                    updated_at=excluded.updated_at,
                    status=excluded.status,
                    error_message=excluded.error_message
                """,
                (
                    masked_source,
                    source_text,
                    translated_masked_text,
                    restored_translation,
                    model_name,
                    glossary_version,
                    now,
                    status,
                    error_message,
                ),
            )

    def get(self, masked_source: str) -> CacheRecord | None:
        """Fetch cache record by masked source."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    source_text,
                    masked_source,
                    translated_masked_text,
                    restored_translation,
                    model_name,
                    glossary_version,
                    updated_at,
                    status,
                    error_message
                FROM translation_cache
                WHERE masked_source = ?
                """,
                (masked_source,),
            ).fetchone()

        if row is None:
            return None

        return CacheRecord(
            source_text=row["source_text"],
            masked_source=row["masked_source"],
            translated_masked_text=row["translated_masked_text"],
            restored_translation=row["restored_translation"],
            model_name=row["model_name"],
            glossary_version=row["glossary_version"],
            updated_at=row["updated_at"],
            status=row["status"],
            error_message=row["error_message"],
        )

    def has_completed(self, masked_source: str) -> bool:
        """Return True when record exists and status is translated/applied."""
        record = self.get(masked_source)
        if record is None:
            return False
        return record.status in {"translated", "applied"}

    def count_records(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM translation_cache").fetchone()
        return int(row["count"]) if row is not None else 0

    def count_by_status(self, status: str) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM translation_cache WHERE status = ?",
                (status,),
            ).fetchone()
        return int(row["count"]) if row is not None else 0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage SQLite translation cache.")
    parser.add_argument("--db", required=True, help="Path to SQLite cache database.")
    parser.add_argument("--init", action="store_true", help="Initialize cache schema.")
    parser.add_argument("--stats", action="store_true", help="Print cache statistics.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    cache = TranslationCache(Path(args.db).expanduser().resolve())

    if args.init:
        cache.init_db()
        print(f"Initialized cache DB: {cache.db_path}")

    if args.stats:
        cache.init_db()
        print(f"DB: {cache.db_path}")
        print(f"Records: {cache.count_records()}")
        print(f"Pending: {cache.count_by_status('pending')}")
        print(f"Translated: {cache.count_by_status('translated')}")
        print(f"Applied: {cache.count_by_status('applied')}")

    if not args.init and not args.stats:
        parser.error("Use at least one action: --init or --stats")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
