"""Streamlit UI для Incident Response Autopilot.

Флоу:
  1. Пользователь заполняет форму алерта и нажимает «Run Analysis».
  2. Граф выполняется до точки interrupt (или до END для LOW/HIGH).
  3. Для CRITICAL — показывается панель Human Approval.
  4. После апрува/отклонения — граф возобновляется, показывается постмортем.
"""

import json
import uuid

import streamlit as st

from src.graph.state import IncidentState
from src.graph.workflow import graph

# ── Константы ────────────────────────────────────────────────────────────────

SEVERITY_COLORS = {
    "CRITICAL": "🔴",
    "HIGH": "🟠",
    "LOW": "🟡",
}

SAMPLE_ALERTS = {
    "CRITICAL — DB down": {
        "id": "alert-001",
        "service": "payments-db",
        "message": "DB connection pool exhausted, 0 connections available",
        "_mock_severity": "CRITICAL",
        "_mock_incident_type": "availability",
    },
    "HIGH — Latency spike": {
        "id": "alert-002",
        "service": "api-gateway",
        "message": "p99 latency 2400ms, threshold 500ms",
        "_mock_severity": "HIGH",
        "_mock_incident_type": "performance",
    },
    "LOW — Disk usage": {
        "id": "alert-003",
        "service": "storage-01",
        "message": "Disk usage at 78%, warning threshold",
        "_mock_severity": "LOW",
        "_mock_incident_type": "data",
    },
}

# ── Инициализация session_state ───────────────────────────────────────────────

def _init_state() -> None:
    defaults = {
        "thread_id": None,
        "graph_state": None,
        "stage": "idle",       # idle | running | awaiting_approval | done | rejected
        "error": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ── Вспомогательные рендер-функции ───────────────────────────────────────────

def _render_triage(state: IncidentState) -> None:
    severity = state.get("severity", "—")
    inc_type = state.get("incident_type", "—")
    icon = SEVERITY_COLORS.get(severity, "⚪")
    st.markdown(f"**Severity:** {icon} `{severity}`  &nbsp;&nbsp; **Type:** `{inc_type}`")


def _render_diagnosis(state: IncidentState) -> None:
    diagnosis = state.get("diagnosis")
    if diagnosis:
        st.markdown(diagnosis)
    else:
        st.caption("_Diagnosis не запускался (LOW-ветка)_")


def _render_history(state: IncidentState) -> None:
    incidents = state.get("similar_incidents", [])
    if not incidents:
        st.caption("_Похожих инцидентов не найдено_")
        return
    for inc in incidents:
        score = inc.get("score", 0)
        st.markdown(
            f"**{inc.get('id', '?')}** — {inc.get('title', '')}"
            f"  \n_Score: {score:.2f}_ | {inc.get('resolution', '')}"
        )


def _render_response_plan(state: IncidentState) -> None:
    plan = state.get("response_plan", "")
    if plan:
        st.markdown(plan)


def _render_postmortem(state: IncidentState) -> None:
    pm = state.get("postmortem", "")
    if pm:
        st.code(pm, language="markdown")


def _render_metrics(state: IncidentState) -> None:
    metrics = state.get("metrics", {})
    if not metrics:
        return
    cols = st.columns(len(metrics))
    for col, (agent, data) in zip(cols, metrics.items()):
        latency = data.get("latency_s", "—") if isinstance(data, dict) else "—"
        col.metric(label=agent, value=f"{latency}s")


# ── Логика запуска графа ──────────────────────────────────────────────────────

def _run_graph(alert: dict) -> None:
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = IncidentState(alert=alert)

    with st.spinner("Запускаю анализ инцидента…"):
        try:
            result = graph.invoke(initial_state, config)
        except Exception as exc:
            st.session_state.error = str(exc)
            st.session_state.stage = "idle"
            return

    st.session_state.thread_id = thread_id
    st.session_state.graph_state = result

    # Проверяем — граф остановился на interrupt или завершился
    snapshot = graph.get_state(config)
    if snapshot.next and "human_approval" in snapshot.next:
        st.session_state.stage = "awaiting_approval"
    else:
        st.session_state.stage = "done"


def _resume_graph(approved: bool) -> None:
    config = {"configurable": {"thread_id": st.session_state.thread_id}}

    with st.spinner("Возобновляю граф…"):
        try:
            graph.update_state(config, {"human_approved": approved})
            result = graph.invoke(None, config)
        except Exception as exc:
            st.session_state.error = str(exc)
            return

    st.session_state.graph_state = result
    st.session_state.stage = "done" if approved else "rejected"


# ── Главный UI ────────────────────────────────────────────────────────────────

def main() -> None:
    _init_state()

    st.set_page_config(
        page_title="Incident Response Autopilot",
        page_icon="🚨",
        layout="wide",
    )
    st.title("🚨 Incident Response Autopilot")
    st.caption("MAS-система автоматической диагностики инцидентов · Mock-режим")

    # ── Боковая панель: ввод алерта ──────────────────────────────────────────
    with st.sidebar:
        st.header("Alert Input")

        preset = st.selectbox("Пресет алерта", ["— кастомный —", *SAMPLE_ALERTS.keys()])

        if preset != "— кастомный —":
            default_json = json.dumps(SAMPLE_ALERTS[preset], ensure_ascii=False, indent=2)
        else:
            default_json = json.dumps(
                {"id": "alert-000", "service": "my-service", "message": "Something went wrong",
                 "_mock_severity": "HIGH", "_mock_incident_type": "performance"},
                ensure_ascii=False, indent=2,
            )

        alert_json = st.text_area("Alert JSON", value=default_json, height=220)

        run_clicked = st.button("▶ Run Analysis", type="primary", use_container_width=True)

        if run_clicked:
            # Сбрасываем предыдущий прогон
            st.session_state.graph_state = None
            st.session_state.stage = "idle"
            st.session_state.error = None

            try:
                alert = json.loads(alert_json)
            except json.JSONDecodeError as exc:
                st.error(f"Невалидный JSON: {exc}")
                st.stop()

            _run_graph(alert)
            st.rerun()

        if st.session_state.stage != "idle":
            st.divider()
            if st.button("🔄 Сбросить", use_container_width=True):
                for key in ["thread_id", "graph_state", "stage", "error"]:
                    st.session_state[key] = None if key != "stage" else "idle"
                st.rerun()

    # ── Основная панель: результаты ──────────────────────────────────────────
    if st.session_state.error:
        st.error(f"Ошибка: {st.session_state.error}")
        st.stop()

    if st.session_state.stage == "idle":
        st.info("Выберите алерт в боковой панели и нажмите **▶ Run Analysis**.")
        st.stop()

    state: IncidentState = st.session_state.graph_state or {}

    # ── Шаг 1: Triage ────────────────────────────────────────────────────────
    with st.expander("**Шаг 1 — Triage** ✅", expanded=True):
        _render_triage(state)

    # ── Шаг 2: Diagnosis + History ───────────────────────────────────────────
    severity = state.get("severity", "")
    if severity in ("CRITICAL", "HIGH"):
        with st.expander("**Шаг 2 — Diagnosis + History** ✅ _(параллельно)_", expanded=True):
            col_diag, col_hist = st.columns(2)
            with col_diag:
                st.subheader("Diagnosis")
                _render_diagnosis(state)
            with col_hist:
                st.subheader("Similar Incidents")
                _render_history(state)
    else:
        with st.expander("**Шаг 2 — History** ✅", expanded=True):
            _render_history(state)

    # ── Шаг 3: Response / Suggestion ─────────────────────────────────────────
    label = "Response Plan" if severity in ("CRITICAL", "HIGH") else "Suggestion"
    with st.expander(f"**Шаг 3 — {label}** ✅", expanded=True):
        _render_response_plan(state)

    # ── Human Approval (только CRITICAL) ─────────────────────────────────────
    if st.session_state.stage == "awaiting_approval":
        st.divider()
        st.warning("### ⚠️ Human Approval Required")
        st.markdown(
            "Инцидент классифицирован как **CRITICAL**. "
            "Подтвердите или отклоните план реагирования перед запуском постмортема."
        )
        col_approve, col_reject = st.columns(2)
        with col_approve:
            if st.button("✅ Approve", type="primary", use_container_width=True):
                _resume_graph(approved=True)
                st.rerun()
        with col_reject:
            if st.button("❌ Reject", type="secondary", use_container_width=True):
                _resume_graph(approved=False)
                st.rerun()

    # ── Шаг 4: Postmortem ────────────────────────────────────────────────────
    if st.session_state.stage == "done" and state.get("postmortem"):
        with st.expander("**Шаг 4 — Postmortem** ✅", expanded=True):
            _render_postmortem(state)

    if st.session_state.stage == "rejected":
        st.error("Инцидент отклонён инженером. Постмортем не создан.")

    # ── Метрики ───────────────────────────────────────────────────────────────
    if state.get("metrics"):
        st.divider()
        st.caption("**Latency per agent (s)**")
        _render_metrics(state)


if __name__ == "__main__":
    main()
