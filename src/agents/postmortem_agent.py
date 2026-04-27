import logging
import time
from typing import Any

import anthropic
from langsmith import traceable
from langsmith.wrappers import wrap_anthropic

from src.agents.postmortem_prompts import SYSTEM_PROMPT, build_user_prompt
from src.agents.postmortem_schema import PostmortemOutput
from src.config import settings
from src.graph.state import IncidentState

logger = logging.getLogger(__name__)

_client = wrap_anthropic(anthropic.Anthropic(api_key=settings.anthropic_api_key or None))


@traceable(name="PostmortemAgent")
def postmortem_node(state: IncidentState) -> dict[str, Any]:
    """Финализирует постмортем инцидента."""
    start = time.monotonic()

    logger.info("postmortem_node: human_approved=%s", state.get("human_approved"))

    response = _client.messages.parse(
        model=settings.triage_model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": build_user_prompt(
                alert=state["alert"],
                severity=state.get("severity", "HIGH"),
                diagnosis=state.get("diagnosis", ""),
                response_plan=state.get("response_plan", ""),
                similar_incidents=state.get("similar_incidents", []),
                human_approved=state.get("human_approved", False),
            ),
        }],
        output_format=PostmortemOutput,
    )

    result: PostmortemOutput = response.parsed_output
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
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }
        },
    }
