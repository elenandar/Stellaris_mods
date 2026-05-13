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


UTF8_BOM = codecs.BOM_UTF8


SAFE_ENTRY_RE = re.compile(
    r"^\s*([A-Za-z0-9_.@-]+):([0-9]+)?\s+\"(?:[^\"\\]|\\.)*\"\s*(#.*)?$"
)
ENTRY_CAPTURE_RE = re.compile(
    r'^\s*([A-Za-z0-9_.@-]+):([0-9]+)?\s+"((?:[^"\\]|\\.)*)"\s*(#.*)?$'
)
ENTRY_PREFIX_RE = re.compile(r"^\s*([A-Za-z0-9_.@-]+):([0-9]+)?\s+")
ENTRY_REWRITE_PREFIX_RE = re.compile(
    r'^(?P<lead>\s*)(?P<key>[A-Za-z0-9_.@-]+):(?P<marker>[0-9]+)?(?P<space>\s+)'
)

DOLLAR_TOKEN_RE = re.compile(r"\$[^$\r\n]+\$")
BRACKET_TOKEN_RE = re.compile(r"\[[^\[\]\r\n]+\]")
ICON_TOKEN_RE = re.compile("\u00a3[^\u00a3\r\n]+\u00a3")
FORMATTING_TAG_RE = re.compile("\u00a7.")

PROTECTED_TOKEN_RE = re.compile(
    r"\$[^$\r\n]+\$|\[[^\[\]\r\n]+\]|\u00a3[^\u00a3\r\n]+\u00a3|\u00a7.|\\n|\\t|\\\"|\\\\"
)
PLACEHOLDER_RE = re.compile(r"__PROT_[0-9]{4}__")

UNESCAPED_INTERNAL_QUOTE_MESSAGE = "Unescaped internal quote inside localization value."


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
    entry_index: int
    key_occurrence_index: int


@dataclass
class OccurrenceReplacement:
    file: str | None
    key: str
    entry_index: int
    key_occurrence_index: int
    line: int | None
    value: str


@dataclass
class ParsedLocalisationFile:
    path: Path
    text: str
    bom_present: bool
    leading_bom_count: int
    text_starts_with_hidden_bom: bool
    header_found: bool
    entries: list[LocalisationEntry]
    issues: list[ParseIssue]


def normalize_header_line(line: str) -> str:
    """Normalize localisation header line to tolerate BOM and surrounding spaces."""
    return line.lstrip("\ufeff").strip()


def count_leading_utf8_boms(raw: bytes) -> int:
    """Count only leading UTF-8 BOM sequences at file start."""
    bom_len = len(UTF8_BOM)
    count = 0
    while raw.startswith(UTF8_BOM, count * bom_len):
        count += 1
    return count


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
    clean_text = text.lstrip("\ufeff")
    path.write_text(clean_text, encoding="utf-8-sig")


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


def _is_escaped_quote(value: str, index: int) -> bool:
    backslash_count = 0
    cursor = index - 1
    while cursor >= 0 and value[cursor] == "\\":
        backslash_count += 1
        cursor -= 1
    return backslash_count % 2 == 1


def _find_lenient_closing_quote(remainder: str) -> int | None:
    for index in range(len(remainder) - 1, 0, -1):
        if remainder[index] != '"':
            continue
        if _is_escaped_quote(remainder, index):
            continue

        tail = remainder[index + 1 :].strip()
        if not tail or tail.startswith("#"):
            return index
    return None


def _parse_lenient_entry(line: str) -> tuple[str, str | None, str] | None:
    prefix = ENTRY_PREFIX_RE.match(line)
    if prefix is None:
        return None

    remainder = line[prefix.end() :]
    if not remainder.startswith('"'):
        return None

    closing_idx = _find_lenient_closing_quote(remainder)
    if closing_idx is None:
        return None

    value = remainder[1:closing_idx]
    if _find_unescaped_quote(value, 0) is None:
        return None

    return prefix.group(1), prefix.group(2), value


def _parse_rewrite_entry(line: str) -> dict[str, str | None] | None:
    prefix = ENTRY_REWRITE_PREFIX_RE.match(line)
    if prefix is None:
        return None

    remainder = line[prefix.end() :]
    if not remainder.startswith('"'):
        return None

    closing_idx = _find_lenient_closing_quote(remainder)
    if closing_idx is None:
        return None

    return {
        "lead": prefix.group("lead"),
        "key": prefix.group("key"),
        "marker": prefix.group("marker"),
        "space": prefix.group("space"),
        "value": remainder[1:closing_idx],
        "trail": remainder[closing_idx + 1 :],
    }


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
            return [UNESCAPED_INTERNAL_QUOTE_MESSAGE]
        return ["Unexpected trailing content after closing quote."]

    return ["Localization entry does not match safe format."]


def parse_localisation_file(path: Path, expected_header: str | None = None) -> ParsedLocalisationFile:
    """Parse localisation file and return entries plus parse issues."""
    leading_bom_count = 0
    text_starts_with_hidden_bom = False
    try:
        raw = path.read_bytes()
    except OSError:
        raw = None
    if raw is not None:
        leading_bom_count = count_leading_utf8_boms(raw)
        try:
            text_sig = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text_sig = raw.decode("utf-8-sig", errors="replace")
        text_starts_with_hidden_bom = text_sig.startswith("\ufeff")

    text, bom_present, decode_error = read_utf8(path)
    issues: list[ParseIssue] = []
    if decode_error:
        issues.append(ParseIssue(message=decode_error, line=1))

    header_found = expected_header is None
    entries: list[LocalisationEntry] = []
    entry_index = 0
    key_occurrence_counts: dict[str, int] = {}

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
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
            key_occurrence_index = key_occurrence_counts.get(key, 0)
            key_occurrence_counts[key] = key_occurrence_index + 1

            entries.append(
                LocalisationEntry(
                    key=key,
                    marker=marker,
                    value=value,
                    line=line_no,
                    entry_index=entry_index,
                    key_occurrence_index=key_occurrence_index,
                )
            )
            entry_index += 1
            continue

        lenient_entry = _parse_lenient_entry(parse_line)
        if lenient_entry is not None:
            key, marker, value = lenient_entry
            key_occurrence_index = key_occurrence_counts.get(key, 0)
            key_occurrence_counts[key] = key_occurrence_index + 1

            entries.append(
                LocalisationEntry(
                    key=key,
                    marker=marker,
                    value=value,
                    line=line_no,
                    entry_index=entry_index,
                    key_occurrence_index=key_occurrence_index,
                )
            )
            issues.append(
                ParseIssue(
                    message=UNESCAPED_INTERNAL_QUOTE_MESSAGE,
                    line=line_no,
                    key=key,
                )
            )
            entry_index += 1
            continue

        if ":" in parse_line or '"' in parse_line:
            prefix = ENTRY_PREFIX_RE.match(parse_line)
            issue_key = prefix.group(1) if prefix is not None else None
            for message in diagnose_nonmatching_entry(parse_line):
                issues.append(ParseIssue(message=message, line=line_no, key=issue_key))

    if expected_header and not header_found:
        issues.append(ParseIssue(message=f"Missing expected header: {expected_header}", line=1))

    return ParsedLocalisationFile(
        path=path,
        text=text,
        bom_present=bom_present,
        leading_bom_count=leading_bom_count,
        text_starts_with_hidden_bom=text_starts_with_hidden_bom,
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


def apply_occurrence_replacements(
    text: str,
    replacements: list[OccurrenceReplacement],
) -> tuple[str, set[tuple[str, int, int]]]:
    """Replace localisation values by exact entry/key occurrence identity."""
    lines = text.splitlines(keepends=True)
    replacement_map: dict[tuple[str, int, int], OccurrenceReplacement] = {}
    for item in replacements:
        replacement_map[(item.key, item.entry_index, item.key_occurrence_index)] = item

    replaced_ids: set[tuple[str, int, int]] = set()
    entry_index = 0
    key_occurrence_counts: dict[str, int] = {}

    for idx, line in enumerate(lines):
        body = line.rstrip("\r\n")
        eol = line[len(body) :]

        parse_body = body.lstrip("\ufeff")
        bom_prefix = body[: len(body) - len(parse_body)]
        parsed = _parse_rewrite_entry(parse_body)
        if parsed is None:
            continue

        key = str(parsed["key"])
        key_occurrence_index = key_occurrence_counts.get(key, 0)
        key_occurrence_counts[key] = key_occurrence_index + 1

        replacement_key = (key, entry_index, key_occurrence_index)
        entry_index += 1

        replacement = replacement_map.get(replacement_key)
        if replacement is None:
            continue

        marker = parsed["marker"]
        marker_part = marker if marker is not None else ""
        lines[idx] = (
            f"{bom_prefix}{parsed['lead']}{key}:{marker_part}{parsed['space']}"
            f"\"{replacement.value}\"{parsed['trail']}{eol}"
        )
        replaced_ids.add(replacement_key)

    return "".join(lines), replaced_ids


def apply_value_replacements(
    text: str,
    replacements_by_key: dict[str, str],
) -> tuple[str, set[str]]:
    """Backward-compatible key-based replacement (unsafe for duplicate keys)."""
    lines = text.splitlines(keepends=True)
    replaced_keys: set[str] = set()

    for idx, line in enumerate(lines):
        body = line.rstrip("\r\n")
        eol = line[len(body) :]

        parse_body = body.lstrip("\ufeff")
        bom_prefix = body[: len(body) - len(parse_body)]
        parsed = _parse_rewrite_entry(parse_body)
        if parsed is None:
            continue

        key = str(parsed["key"])
        if key not in replacements_by_key:
            continue

        marker = parsed["marker"]
        marker_part = marker if marker is not None else ""
        new_value = replacements_by_key[key]
        lines[idx] = (
            f"{bom_prefix}{parsed['lead']}{key}:{marker_part}{parsed['space']}"
            f"\"{new_value}\"{parsed['trail']}{eol}"
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
