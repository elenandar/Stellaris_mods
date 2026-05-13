#!/usr/bin/env python3
"""Validate English/Russian Stellaris localisation `.yml` file pairs."""

from __future__ import annotations

import argparse
import codecs
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    from stellaris_loc_scan import find_english_localisation_files
except ImportError:  # pragma: no cover
    from tools.stellaris_loc_scan import find_english_localisation_files


SAFE_ENTRY_RE = re.compile(
    r"^\s*([A-Za-z0-9_.@-]+):([0-9]+)?\s+\"(?:[^\"\\]|\\.)*\"\s*(#.*)?$"
)
ENTRY_CAPTURE_RE = re.compile(
    r'^\s*([A-Za-z0-9_.@-]+):([0-9]+)?\s+"((?:[^"\\]|\\.)*)"\s*(#.*)?$'
)
ENTRY_PREFIX_RE = re.compile(r"^\s*([A-Za-z0-9_.@-]+):([0-9]+)?\s+")

DOLLAR_TOKEN_RE = re.compile(r"\$[^$\r\n]+\$")
BRACKET_TOKEN_RE = re.compile(r"\[[^\[\]\r\n]+\]")
ICON_TOKEN_RE = re.compile("\u00a3[^\u00a3\r\n]+\u00a3")
FORMATTING_TAG_RE = re.compile("\u00a7.")

UNICODE_QUOTES = {
    "\u00ab",  # <<
    "\u00bb",  # >>
    "\u201c",  # left double curly quote
    "\u201d",  # right double curly quote
    "\u201e",  # low double quote
}

BANNED_PHRASES = (
    "todo",
    "truncated",
    "fixme",
    "\u043e\u0441\u0442\u0430\u043b\u044c\u043d\u043e\u0435 \u0430\u043d\u0430\u043b\u043e\u0433\u0438\u0447\u043d\u043e",
)


@dataclass
class ValidationIssue:
    message: str
    file_path: Path
    line: int | None = None
    key: str | None = None


@dataclass
class LocalisationEntry:
    key: str
    marker: str | None
    value: str
    line: int


@dataclass
class ParsedLocalisationFile:
    path: Path
    expected_header: str
    header_found: bool
    bom_present: bool
    entries: list[LocalisationEntry]
    issues: list[ValidationIssue]


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


def english_to_russian_relative_path(english_relative: Path) -> Path:
    """Map an English localisation relative path to expected Russian path."""
    parts = ["russian" if p == "english" else p for p in english_relative.parts]
    if not parts:
        return english_relative

    file_name = parts[-1]
    if file_name.endswith("_l_english.yml"):
        file_name = file_name[: -len("_l_english.yml")] + "_l_russian.yml"
    elif "l_english" in file_name:
        file_name = file_name.replace("l_english", "l_russian")
    parts[-1] = file_name
    return Path(*parts)


def _read_utf8(path: Path) -> tuple[str, bool, str | None]:
    """Read file as UTF-8 and return text, BOM flag, and decode error (if any)."""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return "", False, f"Failed to read file: {exc}"

    bom_present = raw.startswith(codecs.BOM_UTF8)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        text = raw.decode("utf-8", errors="replace")
        return text, bom_present, f"UTF-8 decode error: {exc}"

    return text, bom_present, None


def _find_unescaped_quote(value: str, start: int) -> int | None:
    escaped = False
    for index in range(start, len(value)):
        char = value[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            return index
    return None


def _diagnose_nonmatching_entry(line: str) -> list[str]:
    prefix = ENTRY_PREFIX_RE.match(line)
    if prefix is None:
        return ["Localization entry does not match safe format."]

    remainder = line[prefix.end() :]
    if not remainder.startswith('"'):
        return ["Localization value must start with ASCII quote (\")."]

    closing_idx = _find_unescaped_quote(remainder, 1)
    if closing_idx is None:
        return ["Unclosed quote or multiline value detected."]

    tail = remainder[closing_idx + 1 :].strip()
    if tail and not tail.startswith("#"):
        if '"' in tail:
            return ["Unescaped internal quote inside localization value."]
        return ["Unexpected trailing content after closing quote."]

    return ["Localization entry does not match safe format."]


def _collect_escape_sequences(value: str) -> Counter[str]:
    tokens: Counter[str] = Counter()
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            seq = value[index : index + 2]
            if seq in ("\\n", "\\t", "\\\\", '\\"'):
                tokens[seq] += 1
            index += 2
            continue
        index += 1
    return tokens


def _counter_subset_issues(
    expected: Counter[str],
    actual: Counter[str],
    label: str,
    russian_file: Path,
    line: int,
    key: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for token, required_count in expected.items():
        actual_count = actual.get(token, 0)
        if actual_count < required_count:
            issues.append(
                ValidationIssue(
                    message=(
                        f"Missing {label} token {token!r}: "
                        f"expected >= {required_count}, found {actual_count}."
                    ),
                    file_path=russian_file,
                    line=line,
                    key=key,
                )
            )
    return issues


def _line_contains_unicode_quote(text: str) -> bool:
    return any(q in text for q in UNICODE_QUOTES)


def parse_localisation_file(path: Path, expected_header: str) -> ParsedLocalisationFile:
    text, bom_present, decode_error = _read_utf8(path)
    issues: list[ValidationIssue] = []
    if decode_error:
        issues.append(ValidationIssue(message=decode_error, file_path=path))

    lines = text.splitlines()
    entries: list[LocalisationEntry] = []
    key_to_line: dict[str, int] = {}
    header_found = False

    for line_no, raw_line in enumerate(lines, start=1):
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

        if _line_contains_unicode_quote(line):
            issues.append(
                ValidationIssue(
                    message="Unicode quote character is not allowed.",
                    file_path=path,
                    line=line_no,
                )
            )

        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped in ("l_english:", "l_russian:"):
            if stripped == expected_header:
                header_found = True
            continue

        safe_match = SAFE_ENTRY_RE.match(line)
        if safe_match is not None:
            capture_match = ENTRY_CAPTURE_RE.match(line)
            if capture_match is None:
                issues.append(
                    ValidationIssue(
                        message="Localization entry could not be parsed after safe-format match.",
                        file_path=path,
                        line=line_no,
                    )
                )
                continue

            key = capture_match.group(1)
            marker = capture_match.group(2)
            value = capture_match.group(3)
            entries.append(LocalisationEntry(key=key, marker=marker, value=value, line=line_no))

            if key in key_to_line:
                issues.append(
                    ValidationIssue(
                        message=(
                            f"Duplicate key {key!r}: first seen on line {key_to_line[key]}."
                        ),
                        file_path=path,
                        line=line_no,
                        key=key,
                    )
                )
            else:
                key_to_line[key] = line_no
            continue

        for diagnosis in _diagnose_nonmatching_entry(line):
            issues.append(
                ValidationIssue(
                    message=diagnosis,
                    file_path=path,
                    line=line_no,
                )
            )

    if not header_found:
        issues.append(
            ValidationIssue(
                message=f"Missing expected header: {expected_header}",
                file_path=path,
                line=1,
            )
        )

    return ParsedLocalisationFile(
        path=path,
        expected_header=expected_header,
        header_found=header_found,
        bom_present=bom_present,
        entries=entries,
        issues=issues,
    )


def _entries_by_key(entries: Iterable[LocalisationEntry]) -> dict[str, LocalisationEntry]:
    mapping: dict[str, LocalisationEntry] = {}
    for entry in entries:
        mapping[entry.key] = entry
    return mapping


def _compare_entry_structure(
    english_file: ParsedLocalisationFile,
    russian_file: ParsedLocalisationFile,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    english_entries = english_file.entries
    russian_entries = russian_file.entries
    english_keys = [e.key for e in english_entries]
    russian_keys = [e.key for e in russian_entries]

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

    english_key_set = set(english_keys)
    russian_key_set = set(russian_keys)

    missing_keys = [k for k in english_keys if k not in russian_key_set]
    extra_keys = [k for k in russian_keys if k not in english_key_set]

    english_index = _entries_by_key(english_entries)
    russian_index = _entries_by_key(russian_entries)

    for key in missing_keys:
        entry = english_index[key]
        issues.append(
            ValidationIssue(
                message=f"Missing key in Russian file: {key!r}.",
                file_path=russian_file.path,
                line=entry.line,
                key=key,
            )
        )

    for key in extra_keys:
        entry = russian_index[key]
        issues.append(
            ValidationIssue(
                message=f"Unexpected extra key in Russian file: {key!r}.",
                file_path=russian_file.path,
                line=entry.line,
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

        issues.extend(
            _counter_subset_issues(
                Counter(DOLLAR_TOKEN_RE.findall(en_entry.value)),
                Counter(DOLLAR_TOKEN_RE.findall(ru_entry.value)),
                "$...$",
                russian_file.path,
                ru_entry.line,
                key,
            )
        )
        issues.extend(
            _counter_subset_issues(
                Counter(BRACKET_TOKEN_RE.findall(en_entry.value)),
                Counter(BRACKET_TOKEN_RE.findall(ru_entry.value)),
                "[...]",
                russian_file.path,
                ru_entry.line,
                key,
            )
        )
        issues.extend(
            _counter_subset_issues(
                Counter(ICON_TOKEN_RE.findall(en_entry.value)),
                Counter(ICON_TOKEN_RE.findall(ru_entry.value)),
                "resource icon",
                russian_file.path,
                ru_entry.line,
                key,
            )
        )
        issues.extend(
            _counter_subset_issues(
                Counter(FORMATTING_TAG_RE.findall(en_entry.value)),
                Counter(FORMATTING_TAG_RE.findall(ru_entry.value)),
                "formatting tag",
                russian_file.path,
                ru_entry.line,
                key,
            )
        )
        issues.extend(
            _counter_subset_issues(
                _collect_escape_sequences(en_entry.value),
                _collect_escape_sequences(ru_entry.value),
                "escape sequence",
                russian_file.path,
                ru_entry.line,
                key,
            )
        )

    return issues


def validate_pair_files(english_path: Path, russian_path: Path) -> ValidationResult:
    english_file = parse_localisation_file(english_path, expected_header="l_english:")
    russian_file = parse_localisation_file(russian_path, expected_header="l_russian:")

    issues = [*english_file.issues, *russian_file.issues]

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


def _print_report(results: list[ValidationResult]) -> None:
    total_issues = sum(len(result.issues) for result in results)
    total_pairs = len(results)

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
    print(f"Pairs checked: {total_pairs}")
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
        result = validate_pair_files(
            Path(args.english).expanduser().resolve(),
            Path(args.russian).expanduser().resolve(),
        )
        results = [result]
    else:
        fresh_root = Path(args.fresh_root).expanduser().resolve()
        russian_root = Path(args.russian_root).expanduser().resolve()

        if not fresh_root.exists() or not fresh_root.is_dir():
            parser.error(f"Fresh root is not an existing directory: {fresh_root}")

        results = validate_roots(
            fresh_root=fresh_root,
            russian_root=russian_root,
        )

    _print_report(results)
    has_issues = any(result.issues for result in results)
    return 1 if has_issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
