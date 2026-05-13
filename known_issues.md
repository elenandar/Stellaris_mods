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
