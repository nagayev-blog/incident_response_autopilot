# Sample Data — Incident Response Autopilot

Синтетический датасет для разработки и тестирования MAS-системы автоматической диагностики инцидентов.

## Стек целевой системы

Spring Boot · PostgreSQL · Kafka · React · OpenShift (K8s) · Keycloak · Prometheus + Grafana

## Структура

```
sample_data/
├── incidents/               # Алерты в формате Alertmanager webhook (JSON)
├── metrics/                 # Временные ряды метрик (CSV, 1 точка = 1 минута)
└── knowledge_base/
    ├── runbooks/            # Пошаговые инструкции по устранению инцидентов
    ├── postmortems/         # Постмортемы прошлых инцидентов
    ├── playbooks/           # Playbook'и по типам + baseline метрики
    └── baseline/            # (см. playbooks_and_baseline.md)
```

## Сценарии инцидентов

| Файл | Severity | Тип | Покрывает ветку графа |
|------|----------|-----|-----------------------|
| `critical_db_connection_pool.json` | CRITICAL | Performance / DB | Human Approval |
| `critical_kafka_consumer_lag.json` | CRITICAL | Availability / Queue | Human Approval |
| `high_pod_oomkilled.json` | HIGH | Infrastructure / Memory | Parallel agents |
| `high_keycloak_auth_degradation.json` | HIGH | Performance / Auth | Parallel agents |
| `high_etl_pipeline_failure.json` | HIGH | Data / Pipeline | Parallel agents |
| `low_disk_usage_warning.json` | LOW | Infrastructure / Disk | History only |
| `low_cdn_cache_miss.json` | LOW | Performance / CDN | History only |

## Формат алерта (Alertmanager webhook)

Каждый JSON содержит:
- Стандартные поля Alertmanager: `version`, `status`, `alerts[]`, `commonLabels`, `commonAnnotations`
- Расширенный `incident_context`: `recent_changes`, `current_metrics`, `business_impact`

```python
import json

with open("incidents/critical_db_connection_pool.json") as f:
    alert = json.load(f)

severity = alert["commonLabels"]["severity"]          # "critical"
service  = alert["commonLabels"]["service"]           # "payment-processing-service"
metrics  = alert["incident_context"]["current_metrics"]
changes  = alert["incident_context"]["recent_changes"]
```

## Формат метрик (CSV)

```python
import pandas as pd

df = pd.read_csv("metrics/inc001_db_connection_pool.csv", parse_dates=["timestamp"])
# Columns: timestamp, pg_connections_active, http_5xx_rate, latency_p99_ms, jvm_heap_percent
```

Каждый CSV содержит временной ряд вокруг инцидента: ~30 минут до + продолжительность инцидента.
`baseline_normal_24h.csv` — 24 часа нормальной работы для сравнения.

## База знаний (RAG ingestion)

Все `.md` файлы в `knowledge_base/` предназначены для загрузки в ChromaDB:

```python
from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader

loader = DirectoryLoader(
    "data/sample_data/knowledge_base/",
    glob="**/*.md",
    loader_cls=UnstructuredMarkdownLoader
)
docs = loader.load()
```
