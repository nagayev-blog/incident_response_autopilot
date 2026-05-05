"""Тесты LLM-агентов с замоканным _llm.

Реальный API не вызывается — мокаем внутреннюю функцию _llm каждого модуля.
Проверяем:
  1. Возвращаемые ключи state соответствуют архитектурной таблице (architecture.md §3)
  2. Данные из LLM-ответа корректно маппируются в state-поля
  3. metrics["<agent>"] содержит latency_s / input_tokens / output_tokens
  4. Узел читает правильные поля из входящего state
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from src.graph.state import IncidentState

# ── Общие фиктивные ответы _llm ───────────────────────────────────────────────

_FAKE_TRIAGE = {
    "severity": "CRITICAL",
    "incident_type": "availability",
    "reasoning": "Connection pool exhausted → full outage.",
    "_input_tokens": 120,
    "_output_tokens": 40,
}

_FAKE_DIAGNOSIS = {
    "root_cause": "Thread pool starvation due to slow queries.",
    "affected_components": ["payments-db", "api-gateway"],
    "evidence": "p99 latency 8s, connection refused errors.",
    "recommended_checks": ["check slow query log", "check pool size"],
    "_input_tokens": 500,
    "_output_tokens": 180,
}

_FAKE_RESPONSE = {
    "immediate_actions": ["restart connection pool", "alert on-call DBA"],
    "runbook_steps": ["step 1: kill idle connections", "step 2: scale pool"],
    "escalation": "Notify #incident-critical via PagerDuty",
    "estimated_resolution_time": "30–60 minutes",
    "_input_tokens": 800,
    "_output_tokens": 260,
}

_FAKE_POSTMORTEM = {
    "title": "DB Pool Exhaustion — 2026-04-27",
    "impact": "100% error rate on payment endpoints for 12 minutes.",
    "root_cause": "Thread pool starvation caused by long-running transactions.",
    "timeline": ["10:00 alert fired", "10:05 on-call engaged", "10:12 resolved"],
    "resolution": "Killed idle connections, increased pool size.",
    "action_items": ["Add pool exhaustion alert", "Review slow query threshold"],
    "_input_tokens": 1000,
    "_output_tokens": 380,
}

_FAKE_SUGGESTION = {
    "summary": "Disk usage approaching 80% threshold.",
    "recommendations": ["archive old logs", "review retention policy"],
    "priority": "можно в рабочее время",
    "_input_tokens": 300,
    "_output_tokens": 90,
}


# ── Вспомогательные фикстуры state ────────────────────────────────────────────

@pytest.fixture
def critical_state() -> IncidentState:
    return IncidentState(
        alert={"id": "a-001", "service": "payments-db", "message": "DB pool exhausted"},
        severity="CRITICAL",
        incident_type="availability",
    )


@pytest.fixture
def high_state() -> IncidentState:
    return IncidentState(
        alert={"id": "a-002", "service": "api-gateway", "message": "p99 > 2s"},
        severity="HIGH",
        incident_type="performance",
    )


@pytest.fixture
def low_state() -> IncidentState:
    return IncidentState(
        alert={"id": "a-003", "service": "storage", "message": "Disk 78%"},
        severity="LOW",
        incident_type="data",
    )


@pytest.fixture
def full_state(critical_state: IncidentState) -> IncidentState:
    """State после прохождения всех узлов — нужен для postmortem."""
    s = dict(critical_state)
    s.update(
        diagnosis="Root cause: pool starvation.",
        similar_incidents=[{"id": "inc-99", "title": "prev outage", "score": 0.85, "resolution": "fixed"}],
        response_plan="1. Kill idle conns\n2. Scale pool",
        human_approved=True,
        engineer_feedback="",
    )
    return IncidentState(**s)  # type: ignore[arg-type]


# ── triage_node ───────────────────────────────────────────────────────────────

class TestTriageNode:
    def test_returns_severity_and_incident_type(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.triage_agent._llm", return_value=dict(_FAKE_TRIAGE))
        from src.agents.triage_agent import triage_node

        result = triage_node(critical_state)

        assert result["severity"] == "CRITICAL"
        assert result["incident_type"] == "availability"

    def test_metrics_keys_present(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.triage_agent._llm", return_value=dict(_FAKE_TRIAGE))
        from src.agents.triage_agent import triage_node

        result = triage_node(critical_state)
        m = result["metrics"]["triage"]

        assert "latency_s" in m
        assert m["input_tokens"] == 120
        assert m["output_tokens"] == 40

    def test_does_not_write_extra_keys(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.triage_agent._llm", return_value=dict(_FAKE_TRIAGE))
        from src.agents.triage_agent import triage_node

        result = triage_node(critical_state)
        # Узел пишет только severity, incident_type, metrics — не весь state
        assert set(result.keys()) == {"severity", "incident_type", "metrics"}

    @pytest.mark.parametrize("sev", ["CRITICAL", "HIGH", "LOW"])
    def test_all_severity_values_pass_through(
        self, mocker: Any, critical_state: IncidentState, sev: str
    ) -> None:
        fake = {**_FAKE_TRIAGE, "severity": sev}
        mocker.patch("src.agents.triage_agent._llm", return_value=fake)
        from src.agents.triage_agent import triage_node

        result = triage_node(critical_state)
        assert result["severity"] == sev


# ── diagnosis_node ────────────────────────────────────────────────────────────

class TestDiagnosisNode:
    def test_returns_diagnosis_string(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.diagnosis_agent._llm", return_value=dict(_FAKE_DIAGNOSIS))
        from src.agents.diagnosis_agent import diagnosis_node

        result = diagnosis_node(critical_state)

        assert "diagnosis" in result
        assert isinstance(result["diagnosis"], str)

    def test_diagnosis_contains_root_cause(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.diagnosis_agent._llm", return_value=dict(_FAKE_DIAGNOSIS))
        from src.agents.diagnosis_agent import diagnosis_node

        result = diagnosis_node(critical_state)

        # Формат: "**Первопричина:** <root_cause>"
        assert _FAKE_DIAGNOSIS["root_cause"] in result["diagnosis"]

    def test_diagnosis_contains_components(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.diagnosis_agent._llm", return_value=dict(_FAKE_DIAGNOSIS))
        from src.agents.diagnosis_agent import diagnosis_node

        result = diagnosis_node(critical_state)

        assert "payments-db" in result["diagnosis"]
        assert "api-gateway" in result["diagnosis"]

    def test_metrics_tokens(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.diagnosis_agent._llm", return_value=dict(_FAKE_DIAGNOSIS))
        from src.agents.diagnosis_agent import diagnosis_node

        result = diagnosis_node(critical_state)
        m = result["metrics"]["diagnosis"]

        assert m["input_tokens"] == 500
        assert m["output_tokens"] == 180

    def test_reads_severity_from_state(
        self, mocker: Any, high_state: IncidentState
    ) -> None:
        """Узел передаёт severity в _llm — проверяем что читает из state, а не дефолт."""
        spy = mocker.patch(
            "src.agents.diagnosis_agent._llm", return_value=dict(_FAKE_DIAGNOSIS)
        )
        from src.agents.diagnosis_agent import diagnosis_node

        diagnosis_node(high_state)

        # _llm вызван ровно один раз
        assert spy.call_count == 1


# ── response_node ─────────────────────────────────────────────────────────────

class TestResponseNode:
    def _state_with_diagnosis(self, critical_state: IncidentState) -> IncidentState:
        s = dict(critical_state)
        s["diagnosis"] = "Root cause: pool starvation."
        s["similar_incidents"] = [
            {"id": "inc-99", "title": "prev", "score": 0.9, "resolution": "restarted"}
        ]
        s["engineer_feedback"] = ""
        return IncidentState(**s)  # type: ignore[arg-type]

    def test_returns_response_plan(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.response_agent._llm", return_value=dict(_FAKE_RESPONSE))
        from src.agents.response_agent import response_node

        result = response_node(self._state_with_diagnosis(critical_state))

        assert "response_plan" in result
        assert isinstance(result["response_plan"], str)

    def test_response_plan_contains_actions(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.response_agent._llm", return_value=dict(_FAKE_RESPONSE))
        from src.agents.response_agent import response_node

        result = response_node(self._state_with_diagnosis(critical_state))

        assert "restart connection pool" in result["response_plan"]
        assert "Notify #incident-critical" in result["response_plan"]

    def test_resets_engineer_feedback(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        """После использования фидбека узел сбрасывает его в пустую строку."""
        mocker.patch("src.agents.response_agent._llm", return_value=dict(_FAKE_RESPONSE))
        from src.agents.response_agent import response_node

        s = self._state_with_diagnosis(critical_state)
        s["engineer_feedback"] = "Please add DB replica failover step"  # type: ignore[typeddict-unknown-key]
        result = response_node(s)

        assert result["engineer_feedback"] == ""

    def test_metrics_keys(
        self, mocker: Any, critical_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.response_agent._llm", return_value=dict(_FAKE_RESPONSE))
        from src.agents.response_agent import response_node

        result = response_node(self._state_with_diagnosis(critical_state))
        m = result["metrics"]["response"]

        assert "latency_s" in m
        assert m["input_tokens"] == 800
        assert m["output_tokens"] == 260


# ── postmortem_node ───────────────────────────────────────────────────────────

class TestPostmortemNode:
    def test_returns_postmortem_string(
        self, mocker: Any, full_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.postmortem_agent._llm", return_value=dict(_FAKE_POSTMORTEM))
        from src.agents.postmortem_agent import postmortem_node

        result = postmortem_node(full_state)

        assert "postmortem" in result
        assert isinstance(result["postmortem"], str)

    def test_postmortem_starts_with_title(
        self, mocker: Any, full_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.postmortem_agent._llm", return_value=dict(_FAKE_POSTMORTEM))
        from src.agents.postmortem_agent import postmortem_node

        result = postmortem_node(full_state)

        # Формат: "# <title>\n\n## Влияние\n..."
        assert result["postmortem"].startswith(f"# {_FAKE_POSTMORTEM['title']}")

    def test_postmortem_contains_timeline(
        self, mocker: Any, full_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.postmortem_agent._llm", return_value=dict(_FAKE_POSTMORTEM))
        from src.agents.postmortem_agent import postmortem_node

        result = postmortem_node(full_state)

        for event in _FAKE_POSTMORTEM["timeline"]:
            assert event in result["postmortem"]

    def test_postmortem_contains_action_items(
        self, mocker: Any, full_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.postmortem_agent._llm", return_value=dict(_FAKE_POSTMORTEM))
        from src.agents.postmortem_agent import postmortem_node

        result = postmortem_node(full_state)

        for item in _FAKE_POSTMORTEM["action_items"]:
            assert item in result["postmortem"]

    def test_metrics_tokens(
        self, mocker: Any, full_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.postmortem_agent._llm", return_value=dict(_FAKE_POSTMORTEM))
        from src.agents.postmortem_agent import postmortem_node

        result = postmortem_node(full_state)
        m = result["metrics"]["postmortem"]

        assert m["input_tokens"] == 1000
        assert m["output_tokens"] == 380

    def test_written_keys(
        self, mocker: Any, full_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.postmortem_agent._llm", return_value=dict(_FAKE_POSTMORTEM))
        from src.agents.postmortem_agent import postmortem_node

        result = postmortem_node(full_state)
        assert set(result.keys()) == {"postmortem", "metrics"}


# ── suggestion_node ───────────────────────────────────────────────────────────

class TestSuggestionNode:
    def test_returns_response_plan(
        self, mocker: Any, low_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.suggestion_agent._llm", return_value=dict(_FAKE_SUGGESTION))
        from src.agents.suggestion_agent import suggestion_node

        result = suggestion_node(low_state)

        assert "response_plan" in result
        assert isinstance(result["response_plan"], str)

    def test_response_plan_contains_summary(
        self, mocker: Any, low_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.suggestion_agent._llm", return_value=dict(_FAKE_SUGGESTION))
        from src.agents.suggestion_agent import suggestion_node

        result = suggestion_node(low_state)

        assert _FAKE_SUGGESTION["summary"] in result["response_plan"]

    def test_response_plan_contains_priority(
        self, mocker: Any, low_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.suggestion_agent._llm", return_value=dict(_FAKE_SUGGESTION))
        from src.agents.suggestion_agent import suggestion_node

        result = suggestion_node(low_state)

        assert _FAKE_SUGGESTION["priority"] in result["response_plan"]

    def test_response_plan_contains_all_recommendations(
        self, mocker: Any, low_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.suggestion_agent._llm", return_value=dict(_FAKE_SUGGESTION))
        from src.agents.suggestion_agent import suggestion_node

        result = suggestion_node(low_state)

        for rec in _FAKE_SUGGESTION["recommendations"]:
            assert rec in result["response_plan"]

    def test_metrics_keys(
        self, mocker: Any, low_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.suggestion_agent._llm", return_value=dict(_FAKE_SUGGESTION))
        from src.agents.suggestion_agent import suggestion_node

        result = suggestion_node(low_state)
        m = result["metrics"]["suggestion"]

        assert "latency_s" in m
        assert m["input_tokens"] == 300
        assert m["output_tokens"] == 90

    def test_written_keys(
        self, mocker: Any, low_state: IncidentState
    ) -> None:
        mocker.patch("src.agents.suggestion_agent._llm", return_value=dict(_FAKE_SUGGESTION))
        from src.agents.suggestion_agent import suggestion_node

        result = suggestion_node(low_state)
        assert set(result.keys()) == {"response_plan", "metrics"}
