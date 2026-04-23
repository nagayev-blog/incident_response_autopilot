import logging
import time
from typing import Any

from src.graph.state import IncidentState

logger = logging.getLogger(__name__)


def suggestion_node(state: IncidentState) -> dict[str, Any]:
    """Формирует простую рекомендацию для LOW-инцидентов. Заглушка."""
    start = time.monotonic()

    logger.info("suggestion_node: LOW incident")

    # --- заглушка ---
    response_plan = (
        "[MOCK] Рекомендация (LOW):\n"
        "Инцидент не требует немедленного реагирования.\n"
        "Рекомендуется: проверить дисковое пространство, настроить алерт при >85%."
    )
    # ----------------

    latency = time.monotonic() - start
    return {
        "response_plan": response_plan,
        "metrics": {"suggestion": {"latency_s": round(latency, 3)}},
    }
