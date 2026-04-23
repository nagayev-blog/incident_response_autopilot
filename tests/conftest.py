import pytest

from src.graph.state import IncidentState


@pytest.fixture
def critical_alert() -> dict:
    return {
        "id": "alert-001",
        "service": "payments-db",
        "message": "DB connection pool exhausted",
        "_mock_severity": "CRITICAL",
        "_mock_incident_type": "availability",
    }


@pytest.fixture
def high_alert() -> dict:
    return {
        "id": "alert-002",
        "service": "api-gateway",
        "message": "p99 latency > 2s",
        "_mock_severity": "HIGH",
        "_mock_incident_type": "performance",
    }


@pytest.fixture
def low_alert() -> dict:
    return {
        "id": "alert-003",
        "service": "storage",
        "message": "Disk usage at 78%",
        "_mock_severity": "LOW",
        "_mock_incident_type": "data",
    }


@pytest.fixture
def critical_state(critical_alert: dict) -> IncidentState:
    return IncidentState(alert=critical_alert, severity="CRITICAL", incident_type="availability")


@pytest.fixture
def high_state(high_alert: dict) -> IncidentState:
    return IncidentState(alert=high_alert, severity="HIGH", incident_type="performance")


@pytest.fixture
def low_state(low_alert: dict) -> IncidentState:
    return IncidentState(alert=low_alert, severity="LOW", incident_type="data")
