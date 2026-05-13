# Stellaris Localisation Safety Tools

This repository contains safe tooling for Stellaris `.yml` localisation workflows.

Important:
- Fresh English localisation files are the only source of truth.
- Old translations and translation memory are not used.
- The pipeline prepares, translates, validates, and applies translations safely.

## Workspace layout

```text
StellarisTranslationWorkspace/
  fresh_mods/
  output/
  tools/
  tests/
  glossary_ru.md
  glossary_candidates.md
  translation_rules.md
  known_issues.md
```

## Mandatory reading before translation

Before any translation run, the agent must read:
- [glossary_ru.md](glossary_ru.md)
- [translation_rules.md](translation_rules.md)
- [known_issues.md](known_issues.md)

Quality policy:
- Every newly discovered validator error must become a regression test.
- Every validator change must include a test in `tests/`.
- Disputed terms go only to [glossary_candidates.md](glossary_candidates.md) until user approval.

## Core tools

- `tools/stellaris_loc_common.py`: shared parser/token/path/BOM helpers
- `tools/stellaris_loc_scan.py`: scan fresh mod for English localisation files
- `tools/stellaris_loc_rebuild_skeleton.py`: create Russian skeleton files from English files
- `tools/stellaris_loc_extract_todo.py`: extract deduplicated translation TODO units as JSONL
- `tools/stellaris_loc_batch_format.py`: split TODO units into JSON batches for translation
- `tools/stellaris_loc_translation_cache.py`: SQLite cache for deduplicated source strings
- `tools/stellaris_loc_apply_translations.py`: apply translated masked text back to Russian files
- `tools/stellaris_loc_validate.py`: validate EN/RU pairs and parser safety

## Batch translation notes

- Keys must never be translated or changed.
- Values inside quotes may localize proper names to Cyrillic when appropriate.
- Catalogue names like `P4T-257-a`, `PXT-947`, `P57J-657-b`, `XJ-9`, and `3V-0L` should remain unchanged.
- Replacements are applied by occurrence identity (`entry_index` + `key_occurrence_index`), not only by key.
- Legacy key-only apply is allowed only for unique keys; duplicate keys require occurrence identity.

## Placeholder safety for model responses

Warning:
- The model must preserve masked placeholders exactly, e.g. `__PROT_0000__`.
- Do not remove, duplicate, rename, or invent placeholders.
- The translated output must target the `text` field only.

If placeholder validation fails during apply:
- that translation unit is rejected;
- Russian files are not modified for that unit;
- CLI exits with non-zero status;
- cache row is marked with `status=error` and an error message (if cache is enabled).

## Batch item format

`tools/stellaris_loc_batch_format.py` creates JSON batches:

```json
[
  {
    "id": "unique-id",
    "key": "localisation_key",
    "file": "localisation/russian/mod_l_russian.yml",
    "source": "Hello $PLANET$",
    "text": "Hello __PROT_0000__",
    "entry_index": 13,
    "key_occurrence_index": 1
  }
]
```

- `text` is the only field to translate.
- `source`, `key`, `file`, and occurrence identity are context only.
- Model responses must still be only:

```json
[
  {
    "id": "unique-id",
    "translation": "Привет, __PROT_0000__"
  }
]
```

## Validator checks

`tools/stellaris_loc_validate.py` validates:
- required headers (`l_english:`, `l_russian:`)
- UTF-8 with BOM for Russian files
- key count, key order, key identity
- numeric marker consistency (`:0`, `:1`, ...)
- exact protected-token preservation (missing and extra are issues):
  - `$...$`
  - `[...]`
  - `U+00A3...U+00A3` resource icon tokens
  - `U+00A7X` formatting tags
  - escape tokens: `\\n`, `\\t`, `\\\\`, `\\"`
- no multiline values
- no unclosed quotes
- no unescaped internal quotes
- no Unicode quotes
- no TODO/TRUNCATED/FIXME/"ostalnoe analogichno" placeholders
- safe localisation entry format

Validator findings are separated into:
- `errors`
- `source_warnings`

Exit code policy:
- exit code `1` if there is at least one `error`
- exit code `0` if there are only `source_warnings`
- exit code `0` if there are no findings

Duplicate key policy:
- duplicate keys in English source are `source_warnings` if Russian preserves the same full ordered key sequence
- duplicate keys that appear only in Russian are `errors`
- duplicate keys in Russian that do not preserve English full ordered key sequence are `errors`
- duplicate-safe apply targets exact occurrences, so repeated keys are not overwritten wholesale

## Fully automated LLM translation

Environment variables:

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-key
LLM_MODEL=gpt-5.4-xhigh
```

See [.env.example](.env.example) for a minimal template.

Never commit API keys.

### Translate one mod

```bash
python3 tools/stellaris_loc_translate_mod.py \
  --fresh-root fresh_mods/2638108246 \
  --russian-root output/2638108246 \
  --work-dir work/2638108246 \
  --cache-db cache/translation_cache.sqlite3 \
  --batch-size 20 \
  --glossary-version v1
```

### Translate a collection

```bash
python3 tools/stellaris_loc_translate_collection.py \
  --fresh-root fresh_mods \
  --output-root output \
  --work-root work \
  --cache-db cache/translation_cache.sqlite3 \
  --batch-size 20 \
  --workers 1 \
  --glossary-version v1
```

### Translate prepared batch files directly

```bash
python3 tools/stellaris_loc_translate_batches.py \
  --batches-dir work/2638108246/batches \
  --translations-dir work/2638108246/translations \
  --cache-db cache/translation_cache.sqlite3 \
  --provider openai-compatible \
  --glossary-version v1 \
  --limit 1
```

Recommendations:
- Use `--limit-batches 1` or `--limit 1` for the first test.
- Always check the final validator report.
- Generated folders should remain gitignored.

## Quick manual pipeline

```bash
python tools/stellaris_loc_scan.py --root fresh_mods/SomeMod
python tools/stellaris_loc_rebuild_skeleton.py --fresh-root fresh_mods/SomeMod --russian-root output/SomeMod
python tools/stellaris_loc_extract_todo.py --fresh-root fresh_mods/SomeMod --russian-root output/SomeMod --out todo.jsonl
python tools/stellaris_loc_batch_format.py --todo todo.jsonl --batch-size 100 --out batches/
python tools/stellaris_loc_apply_translations.py --todo todo.jsonl --translations-dir translations --russian-root output/SomeMod
python tools/stellaris_loc_validate.py --fresh-root fresh_mods/SomeMod --russian-root output/SomeMod
```

## Optional cache usage

- pass `--cache-db cache/translation_cache.sqlite3`
- completed cache entries are skipped by default in batch formatting
- use `--include-cached-complete` to include them again

## Tests

Run all tests:

```bash
python3 -m pytest -q
```

## Git hygiene

Do not commit generated/runtime data:
- `fresh_mods/`
- `output/`
- `batches/`
- `translations/`
- `cache/`
- `work/`
- `reports/`
- `validation_reports/`
- `todo.jsonl`
- `.env`
- cache DB files (`translation_cache.*`, `*.sqlite`, `*.sqlite3`, `*.db`)