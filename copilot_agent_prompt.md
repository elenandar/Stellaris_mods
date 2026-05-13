## Copilot Agent Prompt

Переведи данный Stellaris mod на русский язык в Copilot Agent режиме.

Мод:
`fresh_mods/<MOD_ID>`

Выход:
`output/<MOD_ID>`

Рабочая папка:
`work/<MOD_ID>`

Не используй `tools/stellaris_loc_translate_batches.py`.
Не используй `tools/stellaris_loc_translate_mod.py`.
Не используй `tools/stellaris_loc_translate_collection.py`.
Не используй LLM API.
Не требуй `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`.
Перевод выполняй сам как GitHub Copilot Agent.

Используй tools только для:
- scan
- rebuild skeleton
- validate
- extract_todo
- batch_format
- apply_translations

Перед переводом прочитай:
- `glossary_ru.md`
- `translation_rules.md`
- `known_issues.md`

Правила работы:
- Переводи только `text` в batch JSON.
- Всегда сохраняй `id` без изменений.
- Всегда сохраняй placeholders, включая `__PROT_0000__`, точно как в источнике.
- Никогда не меняй localisation keys.
- Не переводи catalogue names: `P4T-257-a`, `PXT-947`, `P57J-657-b`, `XJ-9`, `3V-0L`.
- Proper names можно кириллизировать, если это не ломает узнаваемость и соответствует glossary/rules.
- Не используй Unicode quotes.
- Не создавай multiline strings.
- Не добавляй markdown в translation JSON.
- Не вставляй `TODO`, `TRUNCATED`, `FIXME`, `остальное аналогично`.

Порядок работы:
1. Запусти scan.
2. Пересобери Russian skeleton files.
3. Проверь validator после rebuild.
4. Извлеки TODO в `work/<MOD_ID>/todo.jsonl`.
5. Сформируй batch files в `work/<MOD_ID>/batches/`.
6. Переведи batch files сам и сохрани translation JSON files в `work/<MOD_ID>/translations/`.
7. Примени переводы через `tools/stellaris_loc_apply_translations.py --translations-dir`.
8. Запусти финальный validator.

Критерий завершения:
- финальный validator должен показать `Errors: 0`.
- `Source warnings` допустимы только если они относятся к проблемам английского source.