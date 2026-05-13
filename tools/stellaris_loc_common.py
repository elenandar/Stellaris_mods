#!/usr/bin/env python3
"""Common helpers for Stellaris localisation tooling."""

from __future__ import annotations

import codecs
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SAFE_ENTRY_RE = re.compile(
    r"^\s*([A-Za-z0-9_.@-]+):([0-9]+)?\s+\"(?:[^\"\\]|\\.)*\"\s*(#.*)?$"
)
ENTRY_CAPTURE_RE = re.compile(
    r'^\s*([A-Za-z0-9_.@-]+):([0-9]+)?\s+"((?:[^"\\]|\\.)*)"\s*(#.*)?$'
)
ENTRY_PREFIX_RE = re.compile(r"^\s*([A-Za-z0-9_.@-]+):([0-9]+)?\s+")
ENTRY_REWRITE_RE = re.compile(
    r'^(?P<lead>\s*)(?P<key>[A-Za-z0-9_.@-]+):(?P<marker>[0-9]+)?(?P<space>\s+)"'
    r'(?P<value>(?:[^"\\]|\\.)*)"(?P<trail>\s*(?:#.*)?)$'
)

DOLLAR_TOKEN_RE = re.compile(r"\$[^$\r\n]+\$")
BRACKET_TOKEN_RE = re.compile(r"\[[^\[\]\r\n]+\]")
ICON_TOKEN_RE = re.compile("\u00a3[^\u00a3\r\n]+\u00a3")
FORMATTING_TAG_RE = re.compile("\u00a7.")

PROTECTED_TOKEN_RE = re.compile(
    r"\$[^$\r\n]+\$|\[[^\[\]\r\n]+\]|\u00a3[^\u00a3\r\n]+\u00a3|\u00a7.|\\n|\\t|\\\"|\\\\"
)
PLACEHOLDER_RE = re.compile(r"__PROT_[0-9]{4}__")


@dataclass
class ParseIssue:
    message: str
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
    text: str
    bom_present: bool
    header_found: bool
    entries: list[LocalisationEntry]
    issues: list[ParseIssue]


def normalize_header_line(line: str) -> str:
    """Normalize localisation header line to tolerate BOM and surrounding spaces."""
    return line.lstrip("\ufeff").strip()


def read_utf8(path: Path) -> tuple[str, bool, str | None]:
    """Read file as UTF-8 and detect BOM."""
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


def write_utf8_bom(path: Path, text: str, dry_run: bool = False) -> None:
    """Write UTF-8 with BOM. Supports dry-run."""
    if dry_run:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def has_header(path: Path, expected_header: str) -> bool:
    """Return True if file contains the expected localisation header."""
    if path.suffix.lower() != ".yml":
        return False

    text, _, error = read_utf8(path)
    if error is not None:
        return False

    for line in text.splitlines():
        if normalize_header_line(line) == expected_header:
            return True
    return False


def english_to_russian_relative_path(english_relative: Path) -> Path:
    """Map English localisation relative path to expected Russian relative path."""
    parts = ["russian" if part == "english" else part for part in english_relative.parts]
    if not parts:
        return english_relative

    filename = parts[-1]
    if filename.endswith("_l_english.yml"):
        filename = filename[: -len("_l_english.yml")] + "_l_russian.yml"
    elif "l_english" in filename:
        filename = filename.replace("l_english", "l_russian")
    parts[-1] = filename

    return Path(*parts)


def replace_english_header_with_russian(text: str) -> tuple[str, bool]:
    """Replace first l_english: header with a clean l_russian: header line."""
    lines = text.splitlines(keepends=True)

    for idx, line in enumerate(lines):
        body = line.rstrip("\r\n")
        eol = line[len(body) :]
        if normalize_header_line(body) == "l_english:":
            lines[idx] = f"l_russian:{eol}"
            return "".join(lines), True

    if not lines and normalize_header_line(text) == "l_english:":
        return "l_russian:", True

    return "".join(lines), False


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


def diagnose_nonmatching_entry(line: str) -> list[str]:
    """Return human-readable diagnosis for a non-matching entry line."""
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


def parse_localisation_file(path: Path, expected_header: str | None = None) -> ParsedLocalisationFile:
    """Parse localisation file and return entries plus parse issues."""
    text, bom_present, decode_error = read_utf8(path)
    issues: list[ParseIssue] = []
    if decode_error:
        issues.append(ParseIssue(message=decode_error, line=1))

    header_found = expected_header is None
    entries: list[LocalisationEntry] = []

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        # Remove hidden BOM if it leaked into first lexical token.
        parse_line = raw_line.lstrip("\ufeff")
        normalized = normalize_header_line(raw_line)

        if not normalized or normalized.startswith("#"):
            continue

        if normalized in ("l_english:", "l_russian:"):
            if expected_header and normalized == expected_header:
                header_found = True
            continue

        safe_match = SAFE_ENTRY_RE.match(parse_line)
        if safe_match is not None:
            capture_match = ENTRY_CAPTURE_RE.match(parse_line)
            if capture_match is None:
                issues.append(
                    ParseIssue(
                        message="Localization entry could not be parsed after safe-format match.",
                        line=line_no,
                    )
                )
                continue

            key = capture_match.group(1)
            marker = capture_match.group(2)
            value = capture_match.group(3)
            entries.append(LocalisationEntry(key=key, marker=marker, value=value, line=line_no))
            continue

        if ":" in parse_line or '"' in parse_line:
            for message in diagnose_nonmatching_entry(parse_line):
                issues.append(ParseIssue(message=message, line=line_no))

    if expected_header and not header_found:
        issues.append(ParseIssue(message=f"Missing expected header: {expected_header}", line=1))

    return ParsedLocalisationFile(
        path=path,
        text=text,
        bom_present=bom_present,
        header_found=header_found,
        entries=entries,
        issues=issues,
    )


def collect_escape_sequences(value: str) -> Counter[str]:
    """Count required escaped two-char sequences in a localisation value."""
    tokens: Counter[str] = Counter()
    index = 0
    while index < len(value):
        if value[index] == "\\" and index + 1 < len(value):
            sequence = value[index : index + 2]
            if sequence in ("\\n", "\\t", "\\\\", '\\"'):
                tokens[sequence] += 1
            index += 2
            continue
        index += 1
    return tokens


def extract_protected_token_counters(value: str) -> dict[str, Counter[str]]:
    """Extract protected token counters grouped by token class."""
    return {
        "dollar": Counter(DOLLAR_TOKEN_RE.findall(value)),
        "bracket": Counter(BRACKET_TOKEN_RE.findall(value)),
        "icon": Counter(ICON_TOKEN_RE.findall(value)),
        "formatting": Counter(FORMATTING_TAG_RE.findall(value)),
        "escape": collect_escape_sequences(value),
    }


def mask_protected_tokens(value: str) -> tuple[str, dict[str, str]]:
    """Replace protected tokens with deterministic placeholders."""
    token_map: dict[str, str] = {}
    parts: list[str] = []
    last_index = 0

    for index, match in enumerate(PROTECTED_TOKEN_RE.finditer(value)):
        placeholder = f"__PROT_{index:04d}__"
        parts.append(value[last_index : match.start()])
        parts.append(placeholder)
        token_map[placeholder] = match.group(0)
        last_index = match.end()

    parts.append(value[last_index:])
    return "".join(parts), token_map


def restore_masked_tokens(masked_value: str, token_map: dict[str, str]) -> str:
    """Restore placeholders back to protected tokens."""
    restored = masked_value
    for placeholder in sorted(token_map.keys()):
        restored = restored.replace(placeholder, token_map[placeholder])
    return restored


def is_technical_only_value(value: str) -> bool:
    """Return True if value appears to contain no translatable human text."""
    masked, _ = mask_protected_tokens(value)
    without_placeholders = PLACEHOLDER_RE.sub("", masked)
    residue = re.sub(r"[\s0-9+\-=%.,:;!?/(){}<>*|]", "", without_placeholders)
    return residue == ""


def build_stable_todo_id(masked_source: str) -> str:
    """Build a stable ID for a masked source string."""
    digest = hashlib.sha1(masked_source.encode("utf-8")).hexdigest()
    return f"loc_{digest}"


def escape_localisation_value(value: str) -> str:
    """Normalize value for safe Stellaris one-line localisation usage."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = value.replace("\n", "\\n").replace("\t", "\\t")

    output: list[str] = []
    backslash_run = 0
    for char in value:
        if char == "\\":
            output.append(char)
            backslash_run += 1
            continue

        if char == '"' and backslash_run % 2 == 0:
            output.append("\\")
            output.append('"')
            backslash_run = 0
            continue

        output.append(char)
        backslash_run = 0

    return "".join(output)


def apply_value_replacements(
    text: str,
    replacements_by_key: dict[str, str],
) -> tuple[str, set[str]]:
    """Replace localisation values by key while preserving structure and comments."""
    lines = text.splitlines(keepends=True)
    replaced_keys: set[str] = set()

    for idx, line in enumerate(lines):
        body = line.rstrip("\r\n")
        eol = line[len(body) :]

        match = ENTRY_REWRITE_RE.match(body)
        if match is None:
            continue

        key = match.group("key")
        if key not in replacements_by_key:
            continue

        marker = match.group("marker")
        marker_part = marker if marker is not None else ""
        new_value = replacements_by_key[key]
        lines[idx] = (
            f"{match.group('lead')}{key}:{marker_part}{match.group('space')}"
            f"\"{new_value}\"{match.group('trail')}{eol}"
        )
        replaced_keys.add(key)

    return "".join(lines), replaced_keys


def dump_json(path: Path, payload: Any, dry_run: bool = False, pretty: bool = True) -> None:
    """Write JSON file safely with UTF-8."""
    if dry_run:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None)
    if pretty:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def load_json(path: Path) -> Any:
    """Load JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def dump_jsonl(path: Path, rows: list[dict[str, Any]], dry_run: bool = False) -> None:
    """Write JSONL file."""
    if dry_run:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL file into list of dict objects."""
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            rows.append(json.loads(stripped))
    return rows
