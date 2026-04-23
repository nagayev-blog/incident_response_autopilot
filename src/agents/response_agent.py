import logging
import time
from typing import Any

from src.graph.state import IncidentState

logger = logging.getLogger(__name__)


def response_node(state: IncidentState) -> dict[str, Any]:
    """Формирует план реагирования. Заглушка возвращает фейковые данные."""
    start = time.monotonic()

    logger.info("response_node: severity=%s", state.get("severity"))

    # --- заглушка ---
    response_plan = (
        "[MOCK] План реагирования:\n"
        "1. Масштабировать реплики БД (x2).\n"
        "2. Очистить connection pool.\n"
        "3. Включить circuit breaker на downstream-сервисах.\n"
        "4. Уведомить команду DBA."
    )
    # ----------------

    latency = time.monotonic() - start
    return {
        "response_plan": response_plan,
        "metrics": {"response": {"latency_s": round(latency, 3)}},
    }
