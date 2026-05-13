# Stellaris Localisation Safety Tools

This repository contains safe tooling for Stellaris `.yml` localisation workflows.

Important:
- Fresh English localisation files are the only source of truth.
- Old translations and translation memory are not used.
- The main workflow for this repository is Copilot Agent semi-automatic translation.
- GitHub Copilot subscription does not require `LLM_API_KEY` for the main workflow.

## Mandatory reading before translation

Before any translation run, read:
- [glossary_ru.md](glossary_ru.md)
- [translation_rules.md](translation_rules.md)
- [known_issues.md](known_issues.md)

Quality policy:
- Every newly discovered validator error must become a regression test.
- Every validator change must include a test in `tests/`.
- Disputed terms go only to [glossary_candidates.md](glossary_candidates.md) until user approval.

## Core tools

- `tools/stellaris_loc_scan.py`: scan a fresh mod for English localisation files
- `tools/stellaris_loc_rebuild_skeleton.py`: create Russian skeleton files from English files
- `tools/stellaris_loc_validate.py`: validate EN/RU pairs and parser safety
- `tools/stellaris_loc_extract_todo.py`: extract translation TODO units as JSONL
- `tools/stellaris_loc_batch_format.py`: split TODO units into batch JSON files
- `tools/stellaris_loc_apply_translations.py`: apply translated masked text back to Russian files
- `tools/stellaris_loc_translation_cache.py`: optional SQLite cache for deduplicated source strings
- `tools/stellaris_loc_common.py`: shared parser/token/path/BOM helpers

## Copilot Agent semi-automatic translation workflow

This is the main workflow for the user.

How it works:
- GitHub Copilot Agent translates the batch JSON files directly in VS Code.
- Python tools handle the safe mechanical steps:
  - scan
  - skeleton rebuild
  - validation
  - TODO extraction
  - batch formatting
  - apply translations
  - final validation

Important constraints for the main workflow:
- No API key is needed.
- Do not use `tools/stellaris_loc_translate_batches.py` in the main workflow.
- Do not use `tools/stellaris_loc_translate_mod.py` in the main workflow.
- Do not use `tools/stellaris_loc_translate_collection.py` in the main workflow.
- Do not require `LLM_BASE_URL`, `LLM_API_KEY`, or `LLM_MODEL`.
- Copilot Agent performs the translation itself.

### One-mod command sequence

Example mod id: `2638108246`

```bash
python3 -m pytest -q

rm -rf output/2638108246 work/2638108246
mkdir -p work/2638108246/batches work/2638108246/translations cache

python3 tools/stellaris_loc_scan.py --root fresh_mods/2638108246

python3 tools/stellaris_loc_rebuild_skeleton.py \
  --fresh-root fresh_mods/2638108246 \
  --russian-root output/2638108246

python3 tools/stellaris_loc_validate.py \
  --fresh-root fresh_mods/2638108246 \
  --russian-root output/2638108246

python3 tools/stellaris_loc_extract_todo.py \
  --fresh-root fresh_mods/2638108246 \
  --russian-root output/2638108246 \
  --out work/2638108246/todo.jsonl \
  --cache-db cache/translation_cache.sqlite3

python3 tools/stellaris_loc_batch_format.py \
  --todo work/2638108246/todo.jsonl \
  --batch-size 10 \
  --out work/2638108246/batches \
  --cache-db cache/translation_cache.sqlite3
```

After these commands:
- Ask Copilot Agent to translate the batch files in `work/2638108246/batches/`.
- Save the resulting translation JSON files in `work/2638108246/translations/`.

Then apply translations:

```bash
python3 tools/stellaris_loc_apply_translations.py \
  --todo work/2638108246/todo.jsonl \
  --translations-dir work/2638108246/translations \
  --russian-root output/2638108246 \
  --cache-db cache/translation_cache.sqlite3 \
  --model GitHub-Copilot-Agent \
  --glossary-version v1
```

Then run final validation:

```bash
python3 tools/stellaris_loc_validate.py \
  --fresh-root fresh_mods/2638108246 \
  --russian-root output/2638108246
```

Expected outcome:
- `Errors: 0`
- `Source warnings` are acceptable only when they describe English source issues.

### Copilot Agent translation prompt

Use the ready prompt from [copilot_agent_prompt.md](copilot_agent_prompt.md).

Operational notes:
- Translate only the `text` field.
- Keep `id` unchanged.
- Preserve placeholders exactly, including `__PROT_0000__` style tokens.
- Never change localisation keys.
- Do not use Unicode quotes.
- Do not create multiline strings.
- Catalogue names such as `P4T-257-a`, `PXT-947`, `P57J-657-b`, `XJ-9`, and `3V-0L` must remain unchanged.
- Proper names may be localized to Cyrillic where appropriate.
- Always check the final validator report.

## Validator checks

`tools/stellaris_loc_validate.py` validates:
- required headers (`l_english:`, `l_russian:`)
- UTF-8 with BOM for Russian files
- key count, key order, key identity
- numeric marker consistency (`:0`, `:1`, ...)
- exact protected-token preservation:
  - `$...$`
  - `[...]`
  - `U+00A3...U+00A3` resource icon tokens
  - `U+00A7X` formatting tags
  - escape tokens: `\\n`, `\\t`, `\\\\`, `\\"`
- no multiline values
- no unclosed quotes
- no unescaped internal quotes
- no Unicode quotes
- no TODO/TRUNCATED/FIXME placeholders
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
- apply targets exact occurrences using `entry_index` and `key_occurrence_index`

## Advanced: OpenAI-compatible API automation

This mode is optional.

Use it only if you have access to an external OpenAI-compatible API endpoint.

Important:
- GitHub Copilot subscription itself does not provide `LLM_API_KEY`.
- The API automation tools stay in the repository for optional advanced usage.
- This is not the main workflow for the user.

Optional environment variables:

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-key
LLM_MODEL=gpt-5.4-xhigh
```

See [.env.example](.env.example) for the optional template.

Optional one-mod API automation:

```bash
python3 tools/stellaris_loc_translate_mod.py \
  --fresh-root fresh_mods/2638108246 \
  --russian-root output/2638108246 \
  --work-dir work/2638108246 \
  --cache-db cache/translation_cache.sqlite3 \
  --base-url "$LLM_BASE_URL" \
  --api-key "$LLM_API_KEY" \
  --model "$LLM_MODEL" \
  --batch-size 20 \
  --glossary-version v1
```

Optional collection API automation:

```bash
python3 tools/stellaris_loc_translate_collection.py \
  --fresh-root fresh_mods \
  --output-root output \
  --work-root work \
  --cache-db cache/translation_cache.sqlite3 \
  --base-url "$LLM_BASE_URL" \
  --api-key "$LLM_API_KEY" \
  --model "$LLM_MODEL" \
  --batch-size 20 \
  --workers 1 \
  --glossary-version v1
```

Optional direct batch translation with API automation:

```bash
python3 tools/stellaris_loc_translate_batches.py \
  --batches-dir work/2638108246/batches \
  --translations-dir work/2638108246/translations \
  --cache-db cache/translation_cache.sqlite3 \
  --provider openai-compatible \
  --base-url "$LLM_BASE_URL" \
  --api-key "$LLM_API_KEY" \
  --model "$LLM_MODEL" \
  --glossary-version v1 \
  --limit 1
```

Recommendations for optional API mode:
- use `--limit 1` or `--limit-batches 1` for the first test
- do not commit API keys
- generated folders should remain gitignored
- always check the final validator report

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