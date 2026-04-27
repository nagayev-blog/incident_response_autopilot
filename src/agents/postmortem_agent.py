import logging
import time
from typing import Any

import anthropic
from langsmith import traceable

from src.agents.postmortem_prompts import SYSTEM_PROMPT, build_user_prompt
from src.agents.postmortem_schema import PostmortemOutput
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
        output_format=PostmortemOutput,
    )
    return {
        **response.parsed_output.model_dump(),
        "_input_tokens": response.usage.input_tokens,
        "_output_tokens": response.usage.output_tokens,
    }


@traceable(name="PostmortemAgent")
def postmortem_node(state: IncidentState) -> dict[str, Any]:
    """Финализирует постмортем инцидента."""
    start = time.monotonic()

    logger.info("postmortem_node: human_approved=%s", state.get("human_approved"))

    user_prompt = build_user_prompt(
        alert=state["alert"],
        severity=state.get("severity", "HIGH"),
        diagnosis=state.get("diagnosis", ""),
        response_plan=state.get("response_plan", ""),
        similar_incidents=state.get("similar_incidents", []),
        human_approved=state.get("human_approved", False),
    )

    raw = _llm(SYSTEM_PROMPT, user_prompt)
    input_tokens = raw.pop("_input_tokens")
    output_tokens = raw.pop("_output_tokens")
    result = PostmortemOutput(**raw)
    latency = time.monotonic() - start

    postmortem = (
        f"# {result.title}\n\n"
        f"## Влияние\n{result.impact}\n\n"
        f"## Первопричина\n{result.root_cause}\n\n"
        f"## Хронология\n" + "\n".join(f"- {e}" for e in result.timeline) + "\n\n"
        f"## Устранение\n{result.resolution}\n\n"
        f"## Задачи\n" + "\n".join(f"- {a}" for a in result.action_items)
    )

    logger.info("postmortem_node: done (%.2fs)", latency)

    return {
        "postmortem": postmortem,
        "metrics": {
            "postmortem": {
                "latency_s": round(latency, 3),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }
        },
    }
