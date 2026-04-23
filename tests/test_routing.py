import pytest

from src.graph.routing import (
    routing_after_history,
    routing_after_human_approval,
    routing_after_response,
    routing_by_severity,
)
from src.graph.state import IncidentState


class TestRoutingBySeverity:
    def test_critical_returns_fan_out(self, critical_state: IncidentState) -> None:
        result = routing_by_severity(critical_state)
        assert set(result) == {"diagnosis", "history"}

    def test_high_returns_fan_out(self, high_state: IncidentState) -> None:
        result = routing_by_severity(high_state)
        assert set(result) == {"diagnosis", "history"}

    def test_low_returns_history_only(self, low_state: IncidentState) -> None:
        result = routing_by_severity(low_state)
        assert result == ["history"]

    def test_unknown_severity_raises(self) -> None:
        state = IncidentState(alert={}, severity="UNKNOWN")
        with pytest.raises(ValueError, match="Unknown severity"):
            routing_by_severity(state)


class TestRoutingAfterResponse:
    def test_critical_goes_to_human_approval(self, critical_state: IncidentState) -> None:
        assert routing_after_response(critical_state) == "human_approval"

    def test_high_goes_to_postmortem(self, high_state: IncidentState) -> None:
        assert routing_after_response(high_state) == "postmortem"


class TestRoutingAfterHistory:
    def test_low_goes_to_suggestion(self, low_state: IncidentState) -> None:
        assert routing_after_history(low_state) == "suggestion"

    def test_critical_goes_to_response(self, critical_state: IncidentState) -> None:
        assert routing_after_history(critical_state) == "response"

    def test_high_goes_to_response(self, high_state: IncidentState) -> None:
        assert routing_after_history(high_state) == "response"


class TestRoutingAfterHumanApproval:
    def test_approved_goes_to_postmortem(self, critical_state: IncidentState) -> None:
        state = IncidentState(**{**critical_state, "human_approved": True})
        assert routing_after_human_approval(state) == "postmortem"

    def test_rejected_goes_to_end(self, critical_state: IncidentState) -> None:
        from langgraph.graph import END

        state = IncidentState(**{**critical_state, "human_approved": False})
        assert routing_after_human_approval(state) == END
