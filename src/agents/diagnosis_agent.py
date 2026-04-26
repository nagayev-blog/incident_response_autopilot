import logging
import time
from typing import Any

import anthropic

from src.agents.diagnosis_prompts import SYSTEM_PROMPT, build_user_prompt
from src.agents.diagnosis_schema import DiagnosisOutput
from src.config import settings
from src.graph.state import IncidentState

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)


def diagnosis_node(state: IncidentState) -> dict[str, Any]:
    """Анализирует алерт и формирует структурированный диагноз через Claude."""
    start = time.monotonic()
    alert = state["alert"]
    severity = state.get("severity", "HIGH")
    incident_type = state.get("incident_type", "performance")

    logger.info("diagnosis_node: severity=%s type=%s", severity, incident_type)

    response = _client.messages.parse(
        model=settings.agent_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(alert, severity, incident_type)}],
        output_format=DiagnosisOutput,
    )

    result: DiagnosisOutput = response.parsed_output
    latency = time.monotonic() - start

    diagnosis = (
        f"**Первопричина:** {result.root_cause}\n\n"
        f"**Затронутые компоненты:** {', '.join(result.affected_components)}\n\n"
        f"**Признаки:** {result.evidence}\n\n"
        f"**Проверить:**\n" + "\n".join(f"- {c}" for c in result.recommended_checks)
    )

    logger.info("diagnosis_node: done (%.2fs)", latency)

    return {
        "diagnosis": diagnosis,
        "metrics": {
            "diagnosis": {
                "latency_s": round(latency, 3),
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        },
    }
