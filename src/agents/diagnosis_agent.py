import logging
import time
from typing import Any

import anthropic
from langsmith import traceable

from src.agents.diagnosis_prompts import SYSTEM_PROMPT, build_user_prompt
from src.agents.diagnosis_schema import DiagnosisOutput
from src.config import settings
from src.graph.state import IncidentState

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)


@traceable(run_type="llm", name=f"anthropic/{settings.agent_model}")
def _llm(system: str, user: str, model: str = settings.agent_model, max_tokens: int = 1024, temperature: float = settings.agent_temperature) -> dict[str, Any]:
    response = _client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=DiagnosisOutput,
    )
    return {
        **response.parsed_output.model_dump(),
        "_input_tokens": response.usage.input_tokens,
        "_output_tokens": response.usage.output_tokens,
    }


@traceable(name="DiagnosisAgent")
def diagnosis_node(state: IncidentState) -> dict[str, Any]:
    """Анализирует алерт и формирует структурированный диагноз через Claude."""
    start = time.monotonic()
    alert = state["alert"]
    severity = state.get("severity", "HIGH")
    incident_type = state.get("incident_type", "performance")

    logger.info("diagnosis_node: severity=%s type=%s", severity, incident_type)

    raw = _llm(SYSTEM_PROMPT, build_user_prompt(alert, severity, incident_type))
    input_tokens = raw.pop("_input_tokens")
    output_tokens = raw.pop("_output_tokens")
    result = DiagnosisOutput(**raw)
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
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        },
    }
