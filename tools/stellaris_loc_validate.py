#!/usr/bin/env python3
"""Validate English/Russian Stellaris localisation .yml file pairs."""

from __future__ import annotations

import argparse
from collections import Counter
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
    errors: list[ValidationIssue]
    source_warnings: list[ValidationIssue]

    @property
    def issues(self) -> list[ValidationIssue]:
        """Backward-compatibility aggregation of all findings."""
        return [*self.source_warnings, *self.errors]

    @property
    def is_valid(self) -> bool:
        """Translation-valid state: no fatal errors."""
        return not self.errors


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


def _duplicate_line_map(entries) -> dict[str, list[int]]:
    line_map: dict[str, list[int]] = {}
    for entry in entries:
        line_map.setdefault(entry.key, []).append(entry.line)
    return line_map


def _classify_duplicate_key_policy(english_file, russian_file) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    errors: list[ValidationIssue] = []
    source_warnings: list[ValidationIssue] = []

    english_entries = english_file.entries
    russian_entries = russian_file.entries
    english_keys = [entry.key for entry in english_entries]
    russian_keys = [entry.key for entry in russian_entries]

    english_counts = Counter(english_keys)
    russian_counts = Counter(russian_keys)
    english_line_map = _duplicate_line_map(english_entries)
    russian_line_map = _duplicate_line_map(russian_entries)

    english_dupe_keys = [key for key, count in english_counts.items() if count > 1]
    russian_dupe_keys = [key for key, count in russian_counts.items() if count > 1]

    for key in english_dupe_keys:
        source_warnings.append(
            ValidationIssue(
                message=(
                    f"Duplicate key in English source: {key!r} occurs "
                    f"{english_counts[key]} times."
                ),
                file_path=english_file.path,
                line=english_line_map[key][0],
                key=key,
            )
        )

    if english_keys == russian_keys:
        for key in russian_dupe_keys:
            if english_counts.get(key, 0) > 1 and russian_counts[key] == english_counts[key]:
                source_warnings.append(
                    ValidationIssue(
                        message=(
                            f"Duplicate key in Russian output preserved from English source: "
                            f"{key!r} occurs {russian_counts[key]} times."
                        ),
                        file_path=russian_file.path,
                        line=russian_line_map[key][0],
                        key=key,
                    )
                )
    else:
        for key in russian_dupe_keys:
            en_count = english_counts.get(key, 0)
            ru_count = russian_counts[key]

            if en_count == 0:
                errors.append(
                    ValidationIssue(
                        message=(
                            f"Duplicate key appears only in Russian output: {key!r} "
                            f"occurs {ru_count} times."
                        ),
                        file_path=russian_file.path,
                        line=russian_line_map[key][0],
                        key=key,
                    )
                )
                continue

            if ru_count > en_count:
                errors.append(
                    ValidationIssue(
                        message=(
                            f"Duplicate key count increased in Russian output for {key!r}: "
                            f"English {en_count}, Russian {ru_count}."
                        ),
                        file_path=russian_file.path,
                        line=russian_line_map[key][0],
                        key=key,
                    )
                )
                continue

            if en_count != ru_count:
                errors.append(
                    ValidationIssue(
                        message=(
                            f"Russian output did not preserve full duplicate key sequence for {key!r}: "
                            f"English {en_count}, Russian {ru_count}."
                        ),
                        file_path=russian_file.path,
                        line=russian_line_map[key][0],
                        key=key,
                    )
                )
                continue

            if en_count > 1:
                errors.append(
                    ValidationIssue(
                        message=(
                            f"Russian output did not preserve full ordered key sequence from "
                            f"English source for duplicate key {key!r}."
                        ),
                        file_path=russian_file.path,
                        line=russian_line_map[key][0],
                        key=key,
                    )
                )

    return errors, source_warnings


def _compare_entry_structure(english_file, russian_file) -> tuple[list[ValidationIssue], list[ValidationIssue]]:
    errors: list[ValidationIssue] = []
    source_warnings: list[ValidationIssue] = []

    english_entries = english_file.entries
    russian_entries = russian_file.entries
    english_keys = [entry.key for entry in english_entries]
    russian_keys = [entry.key for entry in russian_entries]

    duplicate_errors, duplicate_warnings = _classify_duplicate_key_policy(english_file, russian_file)
    errors.extend(duplicate_errors)
    source_warnings.extend(duplicate_warnings)

    if len(english_keys) != len(russian_keys):
        errors.append(
            ValidationIssue(
                message=(
                    "Localization key count mismatch: "
                    f"English has {len(english_keys)}, Russian has {len(russian_keys)}."
                ),
                file_path=russian_file.path,
            )
        )

    english_counts = Counter(english_keys)
    russian_counts = Counter(russian_keys)

    for key, en_count in english_counts.items():
        ru_count = russian_counts.get(key, 0)
        if ru_count < en_count:
            errors.append(
                ValidationIssue(
                    message=(
                        f"Missing key occurrence(s) in Russian file: {key!r} "
                        f"(English {en_count}, Russian {ru_count})."
                    ),
                    file_path=russian_file.path,
                    key=key,
                )
            )

    for key, ru_count in russian_counts.items():
        en_count = english_counts.get(key, 0)
        if ru_count > en_count:
            errors.append(
                ValidationIssue(
                    message=(
                        f"Unexpected extra key occurrence(s) in Russian file: {key!r} "
                        f"(English {en_count}, Russian {ru_count})."
                    ),
                    file_path=russian_file.path,
                    key=key,
                )
            )

    if english_keys != russian_keys:
        for idx in range(min(len(english_keys), len(russian_keys))):
            if english_keys[idx] == russian_keys[idx]:
                continue
            en_entry = english_entries[idx]
            ru_entry = russian_entries[idx]
            errors.append(
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

    pair_count = min(len(english_entries), len(russian_entries))
    for idx in range(pair_count):
        en_entry = english_entries[idx]
        ru_entry = russian_entries[idx]

        if en_entry.key != ru_entry.key:
            continue

        if en_entry.marker != ru_entry.marker:
            errors.append(
                ValidationIssue(
                    message=(
                        "Numeric marker mismatch for key "
                        f"{en_entry.key!r}: English {en_entry.marker!r}, Russian {ru_entry.marker!r}."
                    ),
                    file_path=russian_file.path,
                    line=ru_entry.line,
                    key=en_entry.key,
                )
            )

        en_tokens = extract_protected_token_counters(en_entry.value)
        ru_tokens = extract_protected_token_counters(ru_entry.value)
        for token_type, label in TOKEN_LABELS.items():
            errors.extend(
                _counter_diff_issues(
                    expected=dict(en_tokens[token_type]),
                    actual=dict(ru_tokens[token_type]),
                    label=label,
                    russian_file=russian_file.path,
                    line=ru_entry.line,
                    key=en_entry.key,
                )
            )

    return errors, source_warnings


def validate_pair_files(english_path: Path, russian_path: Path) -> ValidationResult:
    english_file = parse_localisation_file(english_path, expected_header="l_english:")
    russian_file = parse_localisation_file(russian_path, expected_header="l_russian:")

    errors: list[ValidationIssue] = []
    source_warnings: list[ValidationIssue] = []

    for parse_issue in english_file.issues:
        errors.append(
            ValidationIssue(
                message=parse_issue.message,
                file_path=english_path,
                line=parse_issue.line,
                key=parse_issue.key,
            )
        )
    for parse_issue in russian_file.issues:
        errors.append(
            ValidationIssue(
                message=parse_issue.message,
                file_path=russian_path,
                line=parse_issue.line,
                key=parse_issue.key,
            )
        )

    errors.extend(_scan_line_level_issues(english_path, english_file.text))
    errors.extend(_scan_line_level_issues(russian_path, russian_file.text))

    if not russian_file.bom_present:
        errors.append(
            ValidationIssue(
                message="Russian file is not UTF-8 with BOM.",
                file_path=russian_path,
                line=1,
            )
        )

    structure_errors, structure_warnings = _compare_entry_structure(english_file, russian_file)
    errors.extend(structure_errors)
    source_warnings.extend(structure_warnings)

    return ValidationResult(
        english_path=english_path,
        russian_path=russian_path,
        english_entries=len(english_file.entries),
        russian_entries=len(russian_file.entries),
        errors=errors,
        source_warnings=source_warnings,
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
                    errors=[
                        ValidationIssue(
                            message="Expected Russian file is missing.",
                            file_path=russian_file,
                            line=1,
                        )
                    ],
                    source_warnings=[],
                )
            )
            continue

        results.append(validate_pair_files(english_file, russian_file))

    return results


def _print_block(title: str, issues: list[ValidationIssue]) -> None:
    print(f"{title}:")
    if not issues:
        print("  - OK")
        return
    for issue in issues:
        print(_format_issue(issue))


def _print_report(results: list[ValidationResult]) -> None:
    total_errors = sum(len(result.errors) for result in results)
    total_warnings = sum(len(result.source_warnings) for result in results)

    print("Validation report")
    print("=================")

    for result in results:
        print(
            f"Pair: {_display_path(result.english_path)} -> "
            f"{_display_path(result.russian_path)}"
        )
        _print_block("Source warnings", result.source_warnings)
        _print_block("Errors", result.errors)

    print("-----------------")
    print(f"Pairs checked: {len(results)}")
    print(f"Source warnings: {total_warnings}")
    print(f"Errors: {total_errors}")


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
    return 1 if any(result.errors for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
