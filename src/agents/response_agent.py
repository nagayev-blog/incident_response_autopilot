import logging
import time
from typing import Any

import anthropic
from langsmith import traceable

from src.agents.response_prompts import SYSTEM_PROMPT, build_user_prompt
from src.agents.response_schema import ResponseOutput
from src.config import settings
from src.graph.state import IncidentState

logger = logging.getLogger(__name__)

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key or None)


@traceable(run_type="llm", name=f"anthropic/{settings.triage_model}")
def _llm(system: str, user: str, model: str = settings.triage_model, max_tokens: int = 2048, temperature: float = 1.0) -> dict[str, Any]:
    response = _client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
        output_format=ResponseOutput,
    )
    return {
        **response.parsed_output.model_dump(),
        "_input_tokens": response.usage.input_tokens,
        "_output_tokens": response.usage.output_tokens,
    }


@traceable(name="ResponseAgent")
def response_node(state: IncidentState) -> dict[str, Any]:
    """Формирует план реагирования на основе диагноза и истории инцидентов."""
    start = time.monotonic()

    logger.info("response_node: severity=%s", state.get("severity"))

    user_prompt = build_user_prompt(
        alert=state["alert"],
        severity=state.get("severity", "HIGH"),
        diagnosis=state.get("diagnosis", ""),
        similar_incidents=state.get("similar_incidents", []),
        engineer_feedback=state.get("engineer_feedback", ""),
    )

    raw = _llm(SYSTEM_PROMPT, user_prompt)
    input_tokens = raw.pop("_input_tokens")
    output_tokens = raw.pop("_output_tokens")
    result = ResponseOutput(**raw)
    latency = time.monotonic() - start

    response_plan = (
        f"**Немедленные действия:**\n" + "\n".join(f"- {a}" for a in result.immediate_actions) + "\n\n"
        f"**Runbook:**\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(result.runbook_steps)) + "\n\n"
        f"**Эскалация:** {result.escalation}\n\n"
        f"**Ожидаемое время восстановления:** {result.estimated_resolution_time}"
    )

    logger.info("response_node: done (%.2fs)", latency)

    return {
        "response_plan": response_plan,
        "engineer_feedback": "",
        "metrics": {
            "response": {
                "latency_s": round(latency, 3),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        },
    }
