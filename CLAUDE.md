# Incident Response Autopilot

MAS-система автоматической диагностики инцидентов на LangGraph.
Полное описание архитектуры: @docs/architecture.md
Паттерны промптов: @docs/prompting.md

## Стек (фиксированный, не предлагать альтернатив без явного запроса)

- **Python 3.12+**, package manager — `uv` (не pip, не poetry)
- **LangGraph** — оркестрация графа (StateGraph + conditional_edges + interrupt_before)
- **Anthropic Claude API** — LLM провайдер (модель: `claude-sonnet-4-5`, для Triage можно `claude-haiku-4-5`)
- **Pydantic v2** — structured output из всех агентов, без исключений
- **ChromaDB** — локальная векторная БД для RAG
- **Streamlit** — UI для human-in-the-loop
- **LangSmith** — трассировка
- **pytest + pytest-asyncio** — тесты
- **ruff** — линт + формат, **mypy --strict** — типы

## Команды

```bash
uv sync                          # установка зависимостей
uv run pytest                    # все тесты
uv run pytest tests/test_routing.py -v   # конкретный модуль
uv run ruff check . --fix        # линт
uv run ruff format .             # формат
uv run mypy src                  # типы
uv run streamlit run ui/app.py   # UI
```

## Архитектурные инварианты (нарушать нельзя)

1. **Агент = чистая функция** `(state: IncidentState) -> dict[str, Any]`. Возвращает только свой кусок state. Никаких side-effects кроме LLM-вызова и логирования.
2. **Агенты не вызывают друг друга напрямую.** Связи только через граф в `src/graph/workflow.py`.
3. **State — единственный канал передачи данных.** Глобальных переменных и singletons для бизнес-данных нет. LLM-клиент — единственный допустимый singleton (через DI).
4. **Каждый агент возвращает Pydantic-модель**, не raw dict и не строку. Схемы лежат рядом с агентом: `agents/triage_agent.py` + `agents/triage_schema.py`.
5. **Промпты вынесены** в отдельные модули `agents/<name>_prompts.py`. В коде агента — только сборка промпта и вызов LLM.
6. **Параллельность через LangGraph fan-out**, а не через `asyncio.gather` руками. Граф знает про параллелизм лучше нас.
7. **Human-in-the-loop через `interrupt_before`**, не через ручной polling в коде.

## Правила кода

- **Type hints обязательны** на всех публичных функциях. `mypy --strict` должен проходить.
- **TypedDict для LangGraph State**, Pydantic — для I/O агентов и валидации внешних данных (алертов).
- **Никаких `print`** — только `logging` (структурный, JSON-формат) и LangSmith tracing.
- **Никаких magic numbers** — все таймауты, retry, top_k для RAG в `src/config.py` через `pydantic-settings`.
- **Async везде, где есть I/O** (LLM, ChromaDB через async-обёртку, HTTP). Синхронный код — только для CPU-bound утилит и Streamlit-обработчиков.
- Длинные функции (>50 строк) — сигнал к декомпозиции, особенно в агентах.
- Комментарии — только там, где объясняют **почему**, а не **что**. Код должен быть самодокументирующимся.

## Workflow разработки

1. Новый агент / узел графа → сначала эксперимент в `notebooks/exploration.ipynb`.
2. Когда работает — переносим в `src/`, **сначала пишем Pydantic-схему**, потом промпт, потом сам агент.
3. К каждому агенту — тест с замоканным LLM (`pytest-mock` + фикстуры в `tests/conftest.py`). Реальный LLM в тестах — никогда.
4. Изменения в графе → обязательно тест маршрутизации в `tests/test_routing.py`.
5. Перед коммитом: `uv run ruff check . --fix && uv run mypy src && uv run pytest`.

## Что НЕ надо делать

- Не предлагать LangChain Agents / AgentExecutor — мы намеренно используем LangGraph низкого уровня.
- Не использовать OpenAI SDK или другие провайдеры — только Anthropic. Если нужен fallback — обсудить отдельно.
- Не добавлять FastAPI / Flask / прочие веб-фреймворки в MVP — UI делается на Streamlit.
- Не пытаться парсить JSON из LLM регулярками — только через `response_model` Pydantic (нативный structured output Anthropic).
- Не разворачивать ChromaDB как сервер — используем embedded режим, БД лежит в `./data/chroma_db/`.
- Не хардкодить ключи API — только через `.env` и `pydantic-settings`.
- Не делать docstrings на каждую функцию — только на публичные API модулей.

## Специализированные subagents

При задачах конкретного слоя — делегируй профильному subagent (см. `.claude/agents/`):

- **langgraph-architect** — всё, что касается графа: узлы, conditional_edges, interrupt_before, state, sub-graphs.
- **rag-engineer** — всё про ChromaDB: ingestion, chunking, embeddings, retriever, ранжирование.
- **agent-builder** — построение нового LLM-агента: Pydantic schema + prompt + вызов API + тест с моком.

## Контекстные документы (подгружай по необходимости)

- `@docs/architecture.md` — полная схема графа, состояние, маршрутизация по severity
- `@docs/prompting.md` — паттерны системных промптов для агентов, формат few-shot
- `@docs/data_model.md` — формат алертов, runbooks, постмортемов в RAG
- `@docs/eval.md` — план evaluation (LLM-as-judge, RAGAS) — актуально для Version 2.0
