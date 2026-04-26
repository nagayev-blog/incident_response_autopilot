from langgraph.graph import END

from src.graph.state import IncidentState


def routing_by_severity(state: IncidentState) -> list[str]:
    """Conditional edge после triage. Fan-out для CRITICAL/HIGH, прямой путь для LOW."""
    severity = state["severity"]

    if severity in ("CRITICAL", "HIGH"):
        return ["diagnosis", "history"]

    if severity == "LOW":
        return ["history"]

    raise ValueError(f"Unknown severity: {severity!r}")


def routing_after_response(state: IncidentState) -> str:
    """Conditional edge после response."""
    if state["severity"] == "CRITICAL":
        return "human_approval"
    return "postmortem"


def routing_after_history(state: IncidentState) -> str:
    """Conditional edge после history.

    В LOW-ветке history → suggestion.
    В CRITICAL/HIGH LangGraph сам направит в response через fan-in.
    """
    if state.get("severity") == "LOW":
        return "suggestion"
    return "response"


def routing_after_human_approval(state: IncidentState) -> str:
    """Conditional edge после human_approval.

    Если инженер отклонил план, но оставил фидбек — перегенерируем response.
    """
    if state.get("human_approved"):
        return "postmortem"
    if state.get("engineer_feedback"):
        return "response"
    return END  # type: ignore[return-value]
