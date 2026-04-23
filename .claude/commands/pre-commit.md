---
description: Прогнать ruff + mypy + pytest перед коммитом и показать сводку
---

Выполни последовательно и покажи краткий итог по каждому шагу:

1. `uv run ruff format .`
2. `uv run ruff check . --fix`
3. `uv run mypy src`
4. `uv run pytest -q`

Если на каком-то шаге есть ошибки — остановись, покажи их и предложи фикс. Не двигайся дальше, пока шаг не прошёл чисто.

В конце — `git status` и предложение сообщения для коммита по conventional commits (feat: / fix: / refactor: / test: / docs:), основанного на `git diff --staged`.
