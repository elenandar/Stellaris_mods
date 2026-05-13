#!/usr/bin/env python3
"""Validate English/Russian Stellaris localisation .yml file pairs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

try:
    from stellaris_loc_common import (
        english_to_russian_relative_path,
        extract_protected_token_counters,
        parse_localisation_file,
    )
    from stellaris_loc_scan import find_english_localisation_files
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_common import (
        english_to_russian_relative_path,
        extract_protected_token_counters,
        parse_localisation_file,
    )
    from tools.stellaris_loc_scan import find_english_localisation_files


UNICODE_QUOTES = {
    "\u00ab",
    "\u00bb",
    "\u201c",
    "\u201d",
    "\u201e",
}

BANNED_PHRASES = (
    "todo",
    "truncated",
    "fixme",
    "\u043e\u0441\u0442\u0430\u043b\u044c\u043d\u043e\u0435 \u0430\u043d\u0430\u043b\u043e\u0433\u0438\u0447\u043d\u043e",
)

TOKEN_LABELS = {
    "dollar": "$...$",
    "bracket": "[...]",
    "icon": "resource icon",
    "formatting": "formatting tag",
    "escape": "escape sequence",
}


@dataclass
class ValidationIssue:
    message: str
    file_path: Path
    line: int | None = None
    key: str | None = None


@dataclass
class ValidationResult:
    english_path: Path
    russian_path: Path
    english_entries: int
    russian_entries: int
    issues: list[ValidationIssue]

    @property
    def is_valid(self) -> bool:
        return not self.issues


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _format_issue(issue: ValidationIssue) -> str:
    location = _display_path(issue.file_path)
    if issue.line is not None:
        location = f"{location}:{issue.line}"

    key_part = f" key={issue.key}" if issue.key else ""
    return f"  - {location}{key_part}: {issue.message}"


def _counter_diff_issues(
    expected: dict[str, int],
    actual: dict[str, int],
    label: str,
    russian_file: Path,
    line: int,
    key: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for token, expected_count in expected.items():
        actual_count = actual.get(token, 0)
        if actual_count < expected_count:
            issues.append(
                ValidationIssue(
                    message=(
                        f"Missing {label} token {token!r}: "
                        f"expected {expected_count}, found {actual_count}."
                    ),
                    file_path=russian_file,
                    line=line,
                    key=key,
                )
            )

    for token, actual_count in actual.items():
        expected_count = expected.get(token, 0)
        if actual_count > expected_count:
            issues.append(
                ValidationIssue(
                    message=(
                        f"Extra {label} token {token!r}: "
                        f"expected {expected_count}, found {actual_count}."
                    ),
                    file_path=russian_file,
                    line=line,
                    key=key,
                )
            )

    return issues


def _scan_line_level_issues(path: Path, text: str) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line
        if line_no == 1 and line.startswith("\ufeff"):
            line = line[1:]

        lowered = line.lower()
        for phrase in BANNED_PHRASES:
            if phrase in lowered:
                issues.append(
                    ValidationIssue(
                        message=f"Forbidden placeholder string found: {phrase!r}.",
                        file_path=path,
                        line=line_no,
                    )
                )

        if any(char in line for char in UNICODE_QUOTES):
            issues.append(
                ValidationIssue(
                    message="Unicode quote character is not allowed.",
                    file_path=path,
                    line=line_no,
                )
            )

    return issues


def _entries_by_key(entries):
    return {entry.key: entry for entry in entries}


def _compare_entry_structure(english_file, russian_file) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    english_entries = english_file.entries
    russian_entries = russian_file.entries
    english_keys = [entry.key for entry in english_entries]
    russian_keys = [entry.key for entry in russian_entries]

    if len(english_keys) != len(russian_keys):
        issues.append(
            ValidationIssue(
                message=(
                    "Localization key count mismatch: "
                    f"English has {len(english_keys)}, Russian has {len(russian_keys)}."
                ),
                file_path=russian_file.path,
            )
        )

    english_set = set(english_keys)
    russian_set = set(russian_keys)
    english_index = _entries_by_key(english_entries)
    russian_index = _entries_by_key(russian_entries)

    for key in english_keys:
        if key not in russian_set:
            issues.append(
                ValidationIssue(
                    message=f"Missing key in Russian file: {key!r}.",
                    file_path=russian_file.path,
                    line=english_index[key].line,
                    key=key,
                )
            )

    for key in russian_keys:
        if key not in english_set:
            issues.append(
                ValidationIssue(
                    message=f"Unexpected extra key in Russian file: {key!r}.",
                    file_path=russian_file.path,
                    line=russian_index[key].line,
                    key=key,
                )
            )

    if english_keys != russian_keys:
        for idx in range(min(len(english_keys), len(russian_keys))):
            if english_keys[idx] == russian_keys[idx]:
                continue
            en_entry = english_entries[idx]
            ru_entry = russian_entries[idx]
            issues.append(
                ValidationIssue(
                    message=(
                        "Key order mismatch at index "
                        f"{idx}: English key {en_entry.key!r}, Russian key {ru_entry.key!r}."
                    ),
                    file_path=russian_file.path,
                    line=ru_entry.line,
                    key=ru_entry.key,
                )
            )

    for key in english_keys:
        if key not in russian_index:
            continue

        en_entry = english_index[key]
        ru_entry = russian_index[key]

        if en_entry.marker != ru_entry.marker:
            issues.append(
                ValidationIssue(
                    message=(
                        "Numeric marker mismatch for key "
                        f"{key!r}: English {en_entry.marker!r}, Russian {ru_entry.marker!r}."
                    ),
                    file_path=russian_file.path,
                    line=ru_entry.line,
                    key=key,
                )
            )

        en_tokens = extract_protected_token_counters(en_entry.value)
        ru_tokens = extract_protected_token_counters(ru_entry.value)

        for token_type, label in TOKEN_LABELS.items():
            issues.extend(
                _counter_diff_issues(
                    expected=dict(en_tokens[token_type]),
                    actual=dict(ru_tokens[token_type]),
                    label=label,
                    russian_file=russian_file.path,
                    line=ru_entry.line,
                    key=key,
                )
            )

    return issues


def validate_pair_files(english_path: Path, russian_path: Path) -> ValidationResult:
    english_file = parse_localisation_file(english_path, expected_header="l_english:")
    russian_file = parse_localisation_file(russian_path, expected_header="l_russian:")

    issues: list[ValidationIssue] = []
    for parse_issue in english_file.issues:
        issues.append(
            ValidationIssue(
                message=parse_issue.message,
                file_path=english_path,
                line=parse_issue.line,
                key=parse_issue.key,
            )
        )
    for parse_issue in russian_file.issues:
        issues.append(
            ValidationIssue(
                message=parse_issue.message,
                file_path=russian_path,
                line=parse_issue.line,
                key=parse_issue.key,
            )
        )

    issues.extend(_scan_line_level_issues(english_path, english_file.text))
    issues.extend(_scan_line_level_issues(russian_path, russian_file.text))

    if not russian_file.bom_present:
        issues.append(
            ValidationIssue(
                message="Russian file is not UTF-8 with BOM.",
                file_path=russian_path,
                line=1,
            )
        )

    issues.extend(_compare_entry_structure(english_file, russian_file))

    return ValidationResult(
        english_path=english_path,
        russian_path=russian_path,
        english_entries=len(english_file.entries),
        russian_entries=len(russian_file.entries),
        issues=issues,
    )


def validate_roots(fresh_root: Path, russian_root: Path) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    english_files = find_english_localisation_files(fresh_root)

    for english_file in english_files:
        english_rel = english_file.relative_to(fresh_root)
        russian_rel = english_to_russian_relative_path(english_rel)
        russian_file = russian_root / russian_rel

        if not russian_file.exists():
            results.append(
                ValidationResult(
                    english_path=english_file,
                    russian_path=russian_file,
                    english_entries=0,
                    russian_entries=0,
                    issues=[
                        ValidationIssue(
                            message="Expected Russian file is missing.",
                            file_path=russian_file,
                            line=1,
                        )
                    ],
                )
            )
            continue

        results.append(validate_pair_files(english_file, russian_file))

    return results


def _print_report(results: list[ValidationResult]) -> None:
    total_issues = sum(len(result.issues) for result in results)

    print("Validation report")
    print("=================")

    for result in results:
        print(
            f"Pair: {_display_path(result.english_path)} -> "
            f"{_display_path(result.russian_path)}"
        )
        if not result.issues:
            print("  - OK")
            continue
        for issue in result.issues:
            print(_format_issue(issue))

    print("-----------------")
    print(f"Pairs checked: {len(results)}")
    print(f"Total issues: {total_issues}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Stellaris English/Russian localisation files.",
    )
    parser.add_argument("--english", help="Path to English .yml localisation file.")
    parser.add_argument("--russian", help="Path to Russian .yml localisation file.")
    parser.add_argument(
        "--fresh-root",
        help="Path to fresh mod root to recursively validate all English files.",
    )
    parser.add_argument(
        "--russian-root",
        help="Path to Russian output mod root for recursive validation.",
    )
    return parser


def _validate_cli_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    pair_mode = bool(args.english or args.russian)
    root_mode = bool(args.fresh_root or args.russian_root)

    if pair_mode and root_mode:
        parser.error("Use either pair mode (--english/--russian) or root mode (--fresh-root/--russian-root).")

    if pair_mode and not (args.english and args.russian):
        parser.error("Pair mode requires both --english and --russian.")

    if root_mode and not (args.fresh_root and args.russian_root):
        parser.error("Root mode requires both --fresh-root and --russian-root.")

    if not pair_mode and not root_mode:
        parser.error("Provide either pair mode or root mode arguments.")


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    _validate_cli_args(args, parser)

    if args.english and args.russian:
        results = [
            validate_pair_files(
                Path(args.english).expanduser().resolve(),
                Path(args.russian).expanduser().resolve(),
            )
        ]
    else:
        fresh_root = Path(args.fresh_root).expanduser().resolve()
        russian_root = Path(args.russian_root).expanduser().resolve()

        if not fresh_root.exists() or not fresh_root.is_dir():
            parser.error(f"Fresh root is not an existing directory: {fresh_root}")

        results = validate_roots(fresh_root=fresh_root, russian_root=russian_root)

    _print_report(results)
    return 1 if any(result.issues for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
