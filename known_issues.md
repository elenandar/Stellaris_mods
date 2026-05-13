# Journal of Known Issues

Purpose:
- track real validator and workflow defects;
- capture fixes and related regression tests.

## Maintenance rules

- Each issue gets a unique ID.
- Status must be `open` or `resolved`.
- Each fix must list at least one regression test.
- Validator changes without tests are incomplete.

## Entry template

### ISSUE-XXXX
- Date detected:
- Status: open|resolved
- Summary:
- Affected files:
- Root cause:
- Fix:
- Regression test:
- Notes:

## Entries

### ISSUE-0001
- Date detected: 2026-05-13
- Status: resolved
- Summary: Validator did not flag extra protected tokens newly introduced in Russian values.
- Affected files: tools/stellaris_loc_validate.py
- Root cause: Validation checked only missing protected tokens, not suspicious extras.
- Fix: Added strict exact-token checks for `$...$`, `[...]`, `U+00A3...U+00A3`, `U+00A7X`, and escape sequences.
- Regression test: tests/test_stellaris_loc_batch_pipeline.py
- Notes: Extras are treated as issues for this project.

### ISSUE-0002
- Date detected: 2026-05-13
- Status: resolved
- Summary: Validator behavior diverged from tests and README because it was checking missing protected tokens but not all extra-token cases by count.
- Affected files: tools/stellaris_loc_validate.py
- Root cause: Subset-style token comparison allows suspicious extra tokens to pass.
- Fix: Switched to count-aware missing and extra checks for dollar, bracket, resource icon, formatting, and escape tokens.
- Regression test: tests/test_stellaris_loc_batch_pipeline.py
- Notes: Error messages now include Extra ... token strings expected by tests.

### ISSUE-0003
- Date detected: 2026-05-13
- Status: resolved
- Summary: Scanner and skeleton builder used inconsistent header normalization; files with BOM/hidden marker before l_english: could be scanned but skipped during skeleton rebuild.
- Affected files: tools/stellaris_loc_common.py, tools/stellaris_loc_scan.py, tools/stellaris_loc_rebuild_skeleton.py
- Root cause: Header parsing logic handled BOM differently between scan and header replacement paths.
- Fix: Added normalize_header_line and reused it in has_header, parse_localisation_file, and replace_english_header_with_russian with clean l_russian: output.
- Regression test: tests/test_stellaris_loc_tools.py
- Notes: Rebuild now accepts header line forms like \ufeffl_english: and does not leak \ufeff into l_russian: line text.

### ISSUE-0004
- Date detected: 2026-05-13
- Status: resolved
- Summary: Real Workshop mods can contain duplicate localisation keys; validator previously treated them as fatal even when Russian preserved source structure.
- Affected files: tools/stellaris_loc_validate.py
- Root cause: Duplicate keys were not classified separately as source-origin issues.
- Fix: Added duplicate-key policy with separated findings: source_warnings for source-preserved duplicates, errors for Russian-only or sequence-breaking duplicates.
- Regression test: tests/test_stellaris_loc_tools.py
- Notes: If duplicate exists in English and Russian keeps the same full ordered key sequence, this is source_warning; Russian-only duplicate is error.

### ISSUE-0005
- Date detected: 2026-05-13
- Status: resolved
- Summary: Applying translations by key is unsafe when localisation files contain duplicate keys.
- Affected files: tools/stellaris_loc_common.py, tools/stellaris_loc_extract_todo.py, tools/stellaris_loc_apply_translations.py
- Root cause: Key-based replacement can overwrite multiple occurrences of the same key with a single translation unit.
- Fix: Added occurrence identity (`entry_index`, `key_occurrence_index`) in parsing/extraction and switched apply to occurrence-targeted replacement.
- Regression test: tests/test_stellaris_loc_batch_pipeline.py
- Notes: Legacy TODO rows without occurrence identity are rejected for duplicate keys; fallback works only for unique keys.

### ISSUE-0006
- Date detected: 2026-05-13
- Status: resolved
- Summary: Copilot/VS Code agent cannot reliably read generated ignored batch files through chat workflow; manual copy is not scalable.
- Affected files: tools/stellaris_loc_llm_client.py, tools/stellaris_loc_translate_batches.py, tools/stellaris_loc_translate_mod.py, tools/stellaris_loc_translate_collection.py
- Root cause: Batch translation required manual copy/paste of generated JSON into chat instead of direct file processing.
- Fix: Added automatic OpenAI-compatible LLM runner for batch directories, single-mod orchestration, and collection orchestration.
- Regression test: tests/test_stellaris_loc_llm_runner.py
- Notes: Runner reads batch files directly, validates JSON/id/placeholders, retries on malformed responses, and writes translation JSON files without chat copy.

### ISSUE-0007
- Date detected: 2026-05-13
- Status: resolved
- Summary: Main workflow documentation implied that an external OpenAI-compatible API was required, but the user works through GitHub Copilot Agent without `LLM_API_KEY`.
- Affected files: README.md, .env.example, copilot_agent_prompt.md
- Root cause: API-runner commands were documented as the primary workflow instead of an optional advanced mode.
- Fix: Documentation now separates the Copilot Agent semi-automatic workflow from optional API automation and provides a dedicated Copilot Agent prompt.
- Regression test: not applicable (documentation-only change)
- Notes: GitHub Copilot subscription is not the same as an external OpenAI-compatible API subscription.

### ISSUE-0008
- Date detected: 2026-05-13
- Status: resolved
- Summary: Copilot Agent/manual file writes can create Russian localisation files with double BOM or hidden `U+FEFF` before `l_russian:` header.
- Affected files: tools/stellaris_loc_validate.py, tools/stellaris_loc_common.py, tests/test_stellaris_loc_tools.py, translation_rules.md
- Root cause: Manual/agent writes may preserve an existing BOM marker in text and then write the file again as UTF-8 with BOM.
- Fix: Validator now detects multiple leading UTF-8 BOM markers and hidden `U+FEFF` before `l_russian:`; common helper counts leading BOM sequences; instructions require clean header and exactly one UTF-8 BOM.
- Regression test: tests/test_stellaris_loc_tools.py
- Notes: Correct file has one byte-level UTF-8 BOM and text read with `utf-8-sig` starts with `l_russian:`.

### ISSUE-0009
- Date detected: 2026-05-13
- Status: resolved
- Summary: Safety-only instructions produced stylistically flat Russian localisation for diplomatic/lore-heavy mod text.
- Affected files: translation_rules.md, copilot_agent_prompt.md, README.md
- Root cause: Prompt/rules emphasized parser safety but lacked explicit quality style guidance for tone and natural phrasing.
- Fix: Added style quality rules for Copilot Agent translation (tone, lexicon, thematic mappings, and anti-calque guidance) while keeping parser safety constraints mandatory.
- Regression test: not applicable (documentation-only change)
- Notes: Style quality guidance is additive and must never override token/key/parser safety rules.
