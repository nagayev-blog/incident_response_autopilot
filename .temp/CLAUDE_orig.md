# Incident Response Autopilot — CLAUDE.md

## Что это за проект

Multi-Agent System (MAS) на LangGraph для автоматической диагностики и реагирования на инциденты.
Синтетические данные имитируют Alertmanager-алерты, метрики Prometheus и базу знаний (runbooks, postmortems, playbooks).

Цель: демо-проект для демонстрации навыков AI/Agents/MAS на интервью. Приоритет — работающий MVP с нетривиальной архитектурой.

---

## Архитектура графа (LangGraph StateGraph)

### Маршрутизация по severity

```
CRITICAL → Triage → [Diagnosis + History параллельно] → Response → HumanApproval → Postmortem
HIGH     → Triage → [Diagnosis + History параллельно] → Response → Postmortem
LOW      → Triage → History → Suggestion
```

### Три ключевых паттерна

1. **Conditional Routing** — ветвление графа по `severity` из `IncidentState`
2. **Fan-out / Fan-in** — `DiagnosisAgent` и `HistoryAgent` запускаются параллельно, `ResponseAgent` ждёт обоих
3. **Human-in-the-loop** — для CRITICAL граф останавливается через `interrupt_before` и ждёт подтверждения оператора

### IncidentState (src/graph/state.py)

```python
class IncidentState(TypedDict):
    alert: dict              # исходный алерт (Alertmanager JSON)
    severity: str            # CRITICAL / HIGH / LOW
    incident_type: str       # performance / availability / data
    diagnosis: str           # результат DiagnosisAgent
    similar_incidents: list  # результат HistoryAgent (RAG)
    response_plan: str       # план реагирования
    human_approved: bool     # флаг подтверждения (Human-in-the-loop)
    postmortem: str          # черновик постмортема
    metrics: dict            # latency, tokens, cost per agent
```

---

## Структура репозитория

```
incident-response-autopilot/
├── CLAUDE.md
├── pyproject.toml
├── data/  
│   └── sample_data/                         # Синтетические данные
│       ├── incidents/                       # Alertmanager webhook JSON
│       ├── metrics/                         # Временные ряды CSV (1 точка = 1 мин)
│       └── knowledge_base/
│           ├── runbooks/                    # Пошаговые инструкции (Markdown)
│           ├── postmortems/                 # Постмортемы прошлых инцидентов
│           ├── playbooks/                   # Playbook'и по типам инцидентов
│           └── baseline/                   # Нормальные метрики и пороги
├── src/
│   ├── agents/
│   │   ├── triage_agent.py             # Классификация severity и типа инцидента
│   │   ├── diagnosis_agent.py          # Анализ метрик и аномалий
│   │   ├── history_agent.py            # RAG-поиск по базе знаний
│   │   ├── response_agent.py           # План реагирования + черновик постмортема
│   │   └── postmortem_agent.py         # Финализация и сохранение постмортема
│   ├── rag/
│   │   ├── ingestion.py                # Загрузка knowledge_base в ChromaDB
│   │   └── retriever.py                # Семантический поиск
│   ├── graph/
│   │   ├── state.py                    # IncidentState TypedDict
│   │   ├── routing.py                  # Логика conditional edges
│   │   └── workflow.py                 # LangGraph StateGraph — основной граф
│   └── monitoring/
│       └── metrics.py                  # Latency per agent, token usage, cost
├── ui/
│   └── app.py                          # Streamlit: human approval интерфейс
├── tests/
│   ├── test_triage.py
│   ├── test_routing.py
│   └── test_graph.py
└── notebooks/
    └── exploration.ipynb
```

---

## Технологический стек

| Компонент | Технология |
|-----------|------------|
| Граф агентов | `langgraph` — StateGraph, conditional edges, interrupt_before |
| LLM | Anthropic Claude API (`anthropic` SDK) |
| Structured output | Pydantic v2 — каждый агент возвращает типизированную модель |
| Векторная БД | ChromaDB (локально, без инфраструктуры) |
| Embeddings | `sentence-transformers` или Anthropic embeddings |
| UI | Streamlit |
| Трассировка | LangSmith |
| Тесты | pytest |
| Python | 3.11, venv в `.venv/` |

---

## Соглашения по коду

### Агенты

- Каждый агент — отдельный класс или функция в `src/agents/`
- Каждый агент принимает `IncidentState` и возвращает `dict` с обновлением состояния
- Structured output обязателен: агент не возвращает сырой текст, только Pydantic-модель
- Промпты хранятся внутри агента (не выносить в отдельные файлы до рефакторинга)

### LLM-вызовы

- Использовать Anthropic Claude API через официальный SDK (`anthropic`)
- Включать prompt caching там, где system prompt повторяется (runbooks, baseline)
- Модель по умолчанию: `claude-sonnet-4-6` (баланс качества и стоимости)

### RAG

- ChromaDB коллекция инициализируется через `src/rag/ingestion.py`
- Загружаются все `.md` файлы из `sample_data/knowledge_base/`
- `src/rag/retriever.py` возвращает top-k документов с метаданными (тип: runbook/postmortem/playbook)

### Тесты

- `test_routing.py` — unit-тесты маршрутизации: проверять все три ветки (CRITICAL, HIGH, LOW)
- `test_triage.py` — тест с реальным алертом из `sample_data/incidents/`
- `test_graph.py` — интеграционный тест полного прогона графа на одном инциденте
- Не мокать LLM в интеграционных тестах без явной необходимости

### Мониторинг

- `IncidentState.metrics` обновляется после каждого агента: `{"agent_name": {"latency_ms": ..., "tokens": ..., "cost_usd": ...}}`
- Streamlit UI отображает эти метрики в sidebar

---

## Данные

### Синтетические алерты (sample_data/incidents/)

Формат Alertmanager webhook. Поля: `alerts[].labels.severity`, `alerts[].labels.alertname`, `alerts[].annotations.summary`.

Файлы: `critical_db_connection_pool.json`, `critical_kafka_consumer_lag.json`, `high_etl_pipeline_failure.json`, `high_keycloak_auth_degradation.json`, `high_pod_oomkilled.json`, `low_cdn_cache_miss.json`, `low_disk_usage_warning.json`

### Метрики (sample_data/metrics/)

CSV, колонки: `timestamp`, метрики сервиса. Каждый файл — один инцидент, 1 точка в минуту.

### База знаний (sample_data/knowledge_base/)

- `runbooks/rb_*.md` — пошаговые инструкции по устранению (7 штук)
- `postmortems/pm_*.md` — постмортемы 2024–2025 (5 штук)
- `playbooks/pb_*.md` — playbook'и по типам: database, kafka, kubernetes, auth (4 штуки)
- `baseline/` — нормальные значения метрик и пороги алертов

---

## MVP-чеклист

- [ ] `src/graph/state.py` — IncidentState
- [ ] `src/graph/routing.py` — conditional routing по severity
- [ ] `src/agents/triage_agent.py` — severity + incident_type из алерта
- [ ] `src/agents/diagnosis_agent.py` — анализ метрик
- [ ] `src/agents/history_agent.py` — RAG по knowledge_base
- [ ] `src/agents/response_agent.py` — план реагирования
- [ ] `src/graph/workflow.py` — полный граф с fan-out/fan-in
- [ ] `ui/app.py` — human approval для CRITICAL
- [ ] `src/monitoring/metrics.py` — latency + cost per agent
- [ ] `tests/` — routing + triage + граф

---

## Важные решения

- **Anthropic вместо OpenAI**: Claude лучше держит structured output в JSON-схемах — критично для типизированных ответов агентов
- **ChromaDB вместо Pinecone/Weaviate**: локально, нет инфраструктуры, достаточно для демо
- **LangGraph вместо LangChain LCEL**: нужен stateful граф с ветвлением и interrupt — именно для этого LangGraph
- **MVP-принцип**: сначала заставить работать с захардкоженными условиями, рефакторинг потом
