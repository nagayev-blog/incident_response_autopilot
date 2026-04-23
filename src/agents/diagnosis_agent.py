import logging
import time
from typing import Any

from src.graph.state import IncidentState

logger = logging.getLogger(__name__)


def diagnosis_node(state: IncidentState) -> dict[str, Any]:
    """Анализирует метрики и аномалии. Заглушка возвращает фейковые данные."""
    start = time.monotonic()

    logger.info("diagnosis_node: severity=%s type=%s", state.get("severity"), state.get("incident_type"))

    # --- заглушка ---
    diagnosis = (
        f"[MOCK] Диагноз для {state.get('incident_type', 'unknown')} инцидента: "
        "повышенная задержка на уровне БД, p99 latency > 2s, CPU spike до 90%."
    )
    # ----------------

    latency = time.monotonic() - start
    return {
        "diagnosis": diagnosis,
        "metrics": {"diagnosis": {"latency_s": round(latency, 3)}},
    }
