from typing import Any
from typing_extensions import TypedDict


class IncidentState(TypedDict, total=False):
    alert: dict[str, Any]               # исходный алерт от Alertmanager / JSON-файла
    severity: str                        # CRITICAL | HIGH | LOW; заполняет triage
    incident_type: str                   # performance | availability | data; заполняет triage
    diagnosis: str                       # текстовый вывод DiagnosisAgent
    similar_incidents: list[dict[str, Any]]  # результат RAG-поиска; заполняет history
    response_plan: str                   # план реагирования; заполняет response / suggestion
    human_approved: bool                 # True после подтверждения инженером
    postmortem: str                      # финальный текст постмортема
    metrics: dict[str, Any]             # latency/tokens/cost per agent
