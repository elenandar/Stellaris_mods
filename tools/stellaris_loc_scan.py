#!/usr/bin/env python3
"""Scan fresh Stellaris mods for English localisation YAML files."""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    from stellaris_loc_common import has_header
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_common import has_header


ENGLISH_HEADER = "l_english:"


def find_english_localisation_files(root: Path) -> list[Path]:
    """Recursively find English localisation `.yml` files under `root`."""
    result: list[Path] = []
    for path in sorted(root.rglob("*.yml")):
        if path.is_file() and has_header(path, ENGLISH_HEADER):
            result.append(path)
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recursively scan a fresh mod folder for English Stellaris localisation files.",
    )
    parser.add_argument("--root", required=True, help="Path to fresh mod root.")
    parser.add_argument(
        "--absolute",
        action="store_true",
        help="Print absolute file paths (default: root-relative paths).",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        parser.error(f"Root path is not an existing directory: {root}")

    files = find_english_localisation_files(root)
    for file_path in files:
        if args.absolute:
            print(str(file_path))
        else:
            print(str(file_path.relative_to(root)))

    print(f"Found {len(files)} English localisation file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
