from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from src.agents.diagnosis_agent import diagnosis_node
from src.agents.history_agent import history_node
from src.agents.postmortem_agent import postmortem_node
from src.agents.response_agent import response_node
from src.agents.suggestion_agent import suggestion_node
from src.agents.triage_agent import triage_node
from src.graph.routing import (
    routing_after_history,
    routing_after_human_approval,
    routing_after_response,
    routing_by_severity,
)
from src.graph.state import IncidentState


def human_approval_node(state: IncidentState) -> dict[str, Any]:
    """Interrupt-узел: граф останавливается здесь для CRITICAL.

    Возобновление — через graph.update_state(thread_id, {"human_approved": True/False}).
    """
    return {}


def build_graph(checkpointer: MemorySaver | None = None) -> Any:
    builder: StateGraph = StateGraph(IncidentState)

    builder.add_node("triage", triage_node)
    builder.add_node("diagnosis", diagnosis_node)
    builder.add_node("history", history_node)
    builder.add_node("response", response_node)
    builder.add_node("human_approval", human_approval_node)
    builder.add_node("postmortem", postmortem_node)
    builder.add_node("suggestion", suggestion_node)

    builder.add_edge(START, "triage")

    # После triage: fan-out для CRITICAL/HIGH, прямой путь для LOW
    builder.add_conditional_edges("triage", routing_by_severity)

    # После history: LOW → suggestion, CRITICAL/HIGH → response (fan-in)
    builder.add_conditional_edges("history", routing_after_history)

    # diagnosis всегда идёт в response (fan-in)
    builder.add_edge("diagnosis", "response")

    # После response: CRITICAL → human_approval, HIGH → postmortem
    builder.add_conditional_edges("response", routing_after_response)

    # После human_approval: approved → postmortem, rejected → END
    builder.add_conditional_edges("human_approval", routing_after_human_approval)

    builder.add_edge("postmortem", END)
    builder.add_edge("suggestion", END)

    return builder.compile(
        interrupt_before=["human_approval"],
        checkpointer=checkpointer or MemorySaver(),
    )


# Синглтон для UI и скриптов
graph = build_graph()
