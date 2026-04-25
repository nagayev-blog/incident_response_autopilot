from typing import Annotated, Any
from typing_extensions import TypedDict


def _merge_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Редьюсер для metrics: мёржит словари из параллельных узлов."""
    return {**a, **b}


class IncidentState(TypedDict, total=False):
    alert: dict[str, Any]                        # исходный алерт от Alertmanager / JSON-файла
    severity: str                                 # CRITICAL | HIGH | LOW; заполняет triage
    incident_type: str                            # performance | availability | data; заполняет triage
    diagnosis: str                                # текстовый вывод DiagnosisAgent
    similar_incidents: list[dict[str, Any]]       # результат RAG-поиска; заполняет history
    response_plan: str                            # план реагирования; заполняет response / suggestion
    human_approved: bool                          # True после подтверждения инженером
    postmortem: str                               # финальный текст постмортема
    metrics: Annotated[dict[str, Any], _merge_dicts]  # latency/tokens/cost; мёрж из параллельных узлов
